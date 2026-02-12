# FEATURE 02: CAPACITY EXHAUSTION FORECASTING - TECHNICAL IMPLEMENTATION

## 1. SYSTEM ARCHITECTURE

**Feature Name:** Capacity Exhaustion Forecasting
**Namespace:** `src.feature2`
**Status:** Production (v2.0)
**Execution Entry:** `feature2.py` -> `orchestrator.run()`

### 1.1 Technical Components
The feature is built on a modular "Analyze -> Model -> Forecast" pipeline:

1.  **`VeeamCapacityClient`**: Fetches raw data from `/api/v1/backupInfrastructure/repositories/states`.
2.  **`DataPreprocessor`**: Handles real-world data issues (gaps, noise) using `pandas`.
3.  **`DedupAnalyzer`**: Adjusts forecasts based on deduplication efficiency trends.
4.  **`PolynomialForecaster`**: The core math engine using `numpy.polyfit` and `scipy.stats`.
5.  **`CapacityOrchestrator`**: Manages the end-to-end flow for each repository.
6.  **`DatabaseOperations`**: Handles persisting high-precision forecast data to PostgreSQL.

### 1.2 Data Flow Pipeline
```mermaid
graph TD
    A[Start] --> B[Fetch Repositories]
    B --> C[Save Current State to DB]
    C --> D[Load 60-Day History]
    D --> E{Data Sufficiency Check}
    E -- "<14 Days" --> F[Abort & Log Warning]
    E -- ">=14 Days" --> G[Data Preprocessing]
    G --> H[Gap Interpolation & Outlier Removal]
    H --> I[Analyze Dedup Trends]
    I --> J["Fit Models (Linear + Quadratic)"]
    J --> K[Statistical Significance Test (p-value)]
    K -- "p < 0.05" --> L[Select Quadratic]
    K -- "p >= 0.05" --> M[Select Linear]
    L --> N["Solve for Thresholds (80/90/100%)"]
    M --> N
    N --> O[Save Forecast to DB]
```

---

## 2. KEY ALGORITHMS & LOGIC

### 2.1 Data Preprocessing (`DataPreprocessor`)
Ensures "Garbage In, Garbage Out" doesn't happen.

*   **Gap Interpolation**:
    *   Logic: `df.interpolate(method='linear', limit=2)`
    *   Constraint: Only fills gaps ≤ 2 days. Larger gaps are left as-is to preserve honesty in the model.
*   **Outlier Removal**:
    *   Logic: Remove points where `abs(value - mean) > 3 * std_dev`.
    *   Purpose: Prevents single-day spikes (e.g., active full backup) from skewing the long-term trend.

### 2.2 Deduplication Analysis (`DedupAnalyzer`)
Adjusts the raw capacity growth rate based on whether deduplication is getting better or worse.

*   **Logic**:
    1.  Split history into First Half vs Second Half.
    2.  Calculate Mean Dedup Ratio for each half.
    3.  `diff = second_avg - first_avg`.
*   **Adjustments**:
    *   **Improving** (`diff > 0.2`): `growth_rate *= 0.95` (Assume 5% slower growth).
    *   **Degrading** (`diff < -0.2`): `growth_rate *= 1.05` (Assume 5% faster growth).
    *   **Stable**: No adjustment.

### 2.3 Polynomial Forecasting Engine (`PolynomialForecaster`)
This is the heart of the feature. It relies on `numpy` for regression and `scipy` for statistical validity.

#### A. Model Fitting
It fits **two** models to every dataset:
1.  **Linear**: `y = bx + c`
2.  **Quadratic**: `y = ax^2 + bx + c`

#### B. Model Selection (The "p-value" Test)
We don't just "guess" if growth is accelerating. We prove it.
*   **Method**: Calculate the **Standard Error** (SE) of the quadratic coefficient `a`.
*   **t-statistic**: `t = abs(a / se_a)`
*   **p-value**: `2 * stats.t.sf(t_stat, df=n-3)`
*   **Decision Rule**:
    *   IF `p_value < 0.05`: The acceleration is statistically significant -> Use **Quadratic**.
    *   ELSE: The acceleration might be noise -> Use **Linear** (Ockham's Razor).

#### C. Threshold Solving
Once the model is selected, we solve for `x` (days) where `y = Capacity Limit`.
*   **Linear**: Simple algebra `x = (Limit - c) / b`.
*   **Quadratic**: Uses the **Quadratic Formula**: `x = (-b +/- sqrt(b^2 - 4ac)) / 2a`.
    *   *Constraint*: Discards complex (imaginary) solutions and solutions in the past.

### 2.4 Confidence & Priority Classification
*   **Confidence Levels**:
    *   `HIGH`: R² ≥ 0.90 (Excellent fit)
    *   `MODERATE`: 0.70 ≤ R² < 0.90
    *   `LOW`: R² < 0.70
*   **Priority Recommendations**:
    *   `URGENT`: Hit 80% in < 14 days.
    *   `HIGH`: Hit 80% in < 30 days.
    *   `MEDIUM`: Hit 80% in < 60 days.

---

## 3. DATABASE SCHEMA REFERENCE

### 3.1 `feature2.metrics_capacity_forecast`
Stores the sophisticated forecast data for every repository.

| Column | Type | Purpose |
| :--- | :--- | :--- |
| `days_to_80_percent` | INTEGER | Primary metric for alerts |
| `days_to_80_ci_lower/upper`| INTEGER | 95% Confidence Interval info |
| `model_type` | VARCHAR | 'LINEAR' or 'QUADRATIC' |
| `growth_pattern` | VARCHAR | 'ACCELERATING', 'STABLE', 'DECLINING' |
| `r_squared` | NUMERIC | Model accuracy score (0.0-1.0) |
| `confidence_level` | VARCHAR | HIGH/MODERATE/LOW |
| `quality_flags` | JSONB | e.g. `{"outliers_removed": 2}` |

### 3.2 `feature2.capacity_history_raw`
Stores the raw daily snapshots used to build the models.

---

## 4. INTEGRATION
*   **Input**: Veeam REST API (`/states` endpoint).
*   **Dependencies**: `numpy`, `scipy`, `pandas`.
*   **Outputs**: 
    *   `metrics_capacity_forecast` table.
    *   Exposed via MCP Tool: `get_capacity_forecast()`.

## 5. CONFIGURATION (`config.yaml`)
```yaml
feature2:
  min_days: 14                 # Minimum history required
  max_gap_days: 2              # Max interpolation
  outlier_threshold: 3.0       # Sigma limit
  r_squared_high: 0.90         # Confidence threshold
  p_value_threshold: 0.05      # Significance threshold
  
  # Procurement Lead Times (affects recommendations)
  urgent_threshold_days: 14
  high_threshold_days: 30
```

---

## 6. OPERATION

### 6.1 Manual Execution
```powershell
python src\feature2\feature2.py
```

### 6.2 Security Configuration
*   **Credentials**: Loaded from `.env` file (VEEAM_SERVER, VEEAM_USERNAME, VEEAM_PASSWORD, DB credentials).
*   **Config Priority**: `.env` variables override `config.yaml` for all sensitive values.

