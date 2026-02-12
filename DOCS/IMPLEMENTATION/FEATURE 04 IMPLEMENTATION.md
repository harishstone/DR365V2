# FEATURE 04: RECOVERY VERIFICATION & RTO ANALYSIS - TECHNICAL IMPLEMENTATION

## 1. SYSTEM ARCHITECTURE

**Feature Name:** Recovery Verification & RTO Analysis (Statistical + SureBackup Hybrid)
**Namespace:** `src.feature4`
**Status:** Production (v1.1)
**Execution Entry:** `feature4.py` -> `main()`

### 1.1 Technical Components
Feature 4 is a **multi-layered** verification engine that combines REST-based historical analysis with (optional) PowerShell-based SureBackup validation.

1.  **`VeeamRestoreClient`**:
    *   Acts as the primary data collector.
    *   **Hybrid Mode**: First attempts to run `get_restore_history.ps1` for high-fidelity session data.
    *   **Fallback Mode**: If PowerShell fails, it performs a surgical REST API scan (`/restoreSessions` with `filter: jobID eq X`).
2.  **`SureBackupCollector`** (`fetch_surebackup_results_via_powershell`):
    *   Executes `get_surebackup_results.ps1`.
    *   Retrieves deep application-level validation metrics (`BootTime`, `VerifiedDrives`, `ApplicationStatus`).
3.  **`RTOAnalyzer`**:
    *   Calculates statistical percentiles (Median/50th, 90th, 95th) from restore durations.
    *   Computes **95% Confidence Intervals** using Student's t-distribution.
4.  **`ConcurrentRestoreModeler`**:
    *   Uses **Queueing Theory (M/M/c)**.
    *   Models the impact of concurrent restores on RTO (e.g., "If we restore 5 VMs at once, will we breach SLA?").

### 1.2 Data Flow Pipeline
```mermaid
graph TD
    A[Start] --> B[Fetch Restore History]
    B --> C{Hybrid Mode?}
    C -- Yes --> D[Run PowerShell Collector]
    C -- No/Fail --> E[Run REST API Fallback]
    
    A --> F[Fetch SureBackup Results]
    F --> G[Run get_surebackup_results.ps1]
    
    D & E --> H[RTOAnalyzer]
    H --> I[Calculate Percentiles & CI]
    
    H & G --> J[RecoveryConfidenceCalculator]
    J --> K[Blend Scores (70% History / 30% SureBackup)]
    K --> L[ConcurrentRestoreModeler]
    L --> M[Calculate Max Concurrent Capacity]
    M --> N[Write to PostgreSQL]
```

---

## 2. KEY ALGORITHMS & LOGIC

### 2.1 RTO Prediction & Confidence Intervals
**Problem:** Simple averages are misleading for RTO.
**Solution:**
*   **Percentiles**: We use the **95th percentile** as the "Predicted RTO" (conservative estimate).
*   **Confidence Interval (CI)**:
    *   `Margin = t_critical * (std_err)`
    *   `CI = [Mean - Margin, Mean + Margin]`
    *   This gives a range (e.g., "15 - 18 minutes") rather than a single number.

### 2.2 SureBackup Confidence Blending
The system calculates a `base_confidence` from restore history (success rate, recency, etc.) and then blends it with SureBackup results if available.

*   `Base Score` components:
    *   Success Rate (30%)
    *   Recency (25%)
    *   Predictability (CV) (20%)
    *   SLA Compliance (15%)
    *   Coverage (10%)
*   `Final Score`:
    *   `If SureBackup Available`: `(Base * 0.7) + (SureBackupScore * 0.3)`
    *   `If Not`: `Base`

### 2.3 Concurrent Restore Modeling (Queue Theory)
Estimates how RTO degrades under load.
*   **Formula**: `Overhead = 1.1 ^ (ConcurrentCount / NumProxies)`
*   `PredictedRTO_Concurrent = SingleRTO * Overhead`
*   The system iterates `ConcurrentCount` from 1 to 20 until `PredictedRTO > TargetSLA`, defining the **Max Concurrent Restores**.

### 2.4 SLA Compliance Logic
*   **Buffer Calculation**: `Buffer% = (TargetRTO - PredictedRTO) / TargetRTO`
*   **Status**:
    *   `COMPLIANT`: Buffer >= 20%
    *   `AT_RISK`: Buffer >= 0% but < 20%
    *   `NON_COMPLIANT`: Buffer < 0% (Predicted > Target)

---

## 3. DATABASE SCHEMA REFERENCE

### 3.1 `feature4.metrics_recovery_verification`
| Column | Type | Purpose |
| :--- | :--- | :--- |
| `rto_95th_percentile_minutes` | NUMERIC | The primary "Predicted RTO" metric. |
| `rto_confidence_interval_upper`| NUMERIC | The worst-case statistical upper bound. |
| `overall_confidence_score` | NUMERIC | The final 0-100 blended score. |
| `surebackup_enabled` | BOOLEAN | Whether SureBackup data was used in this run. |
| `max_concurrent_restores` | INTEGER | Estimated capacity before SLA breach. |
| `visit_priority` | VARCHAR | Criticality level based on grade/SLA status. |

### 3.2 `feature4.recovery_test_history`
| Column | Type | Purpose |
| :--- | :--- | :--- |
| `duration_minutes` | NUMERIC | Actual RTO of the specific test session. |
| `surebackup_boot_time_ms` | INTEGER | (If SureBackup) how long the OS took to boot. |
| `restore_type` | VARCHAR | 'Test' vs 'Production' (only Test used for stats). |

---

## 4. INTEGRATION & OUTPUT INTERFACE

**Dependencies:**
*   `scipy.stats` (t-distribution, SEM).
*   `numpy` (percentiles).
*   `subprocess` (PowerShell execution).

**Metadata Output (for Feature 5):**
Generates detailed `quality_flags` for Risk Analysis:
```json
{
  "surebackup": true,
  "insufficient_sample_size": false,
  "stale_test_data": false
}
```
If `stale_test_data` is true (>90 days), Feature 5 will flag a Risk.

---

## 5. OPERATION

### 5.1 Manual Execution
```powershell
python src\feature4\feature4.py
```
*Note: Automatically attempts hybrid PowerShell collection, falls back to REST API if unavailable.*

### 5.2 Security Configuration
*   **Credentials**: Loaded from `.env` file (VEEAM_SERVER, VEEAM_USERNAME, VEEAM_PASSWORD, DB credentials).
*   **SureBackup**: Optional. Configured via `config.yaml` (`surebackup.enabled: true/false`).

