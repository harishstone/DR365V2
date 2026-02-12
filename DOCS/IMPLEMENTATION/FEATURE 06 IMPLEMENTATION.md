# FEATURE 06: ACTIONABLE RECOMMENDATIONS & GUIDANCE SYSTEM - IMPLEMENTATION DETAILS

## 1. SYSTEM OVERVIEW

**Feature Name:** Actionable Recommendations & Guidance System
**Namespace:** `src.feature6`
**Status:** Production (v2.0) - Verified with Dual Database Architecture
**Core Responsibility:** To function as the "Architect's Advisor" by converting high-priority risks identified by Feature 5 into structured, actionable remediation plans without ever executing changes against the infrastructure.

### 1.1 Architectural Philosophy: "Zero-Touch Guidance"
Feature 6 is architected with a strict **Read-Only / No-Execution** mandate. It separates the *planning* of remediation from the *execution* of remediation.
*   **Input**: Read-only consumption of consolidated risk data from Feature 5's PostgreSQL database (`dr365v.metrics_risk_analysis_consolidated`).
*   **Processing**: Applies expert system rules and strategy patterns to generate guidance.
*   **Output**: Writes structured remediation plans (JSON) to the database (`dr365v.remediation_plans`) for human consumption.
*   **Boundary**: It explicitly **DOES NOT** connect to the Veeam VBR server to make changes.

---

## 2. COMPONENT ARCHITECTURE

The system is built around a central engine that orchestrates the data retrieval, logic application, and plan persistence.

### 2.1 Core Classes (`feature6.py`)

#### `Feature6GuidanceEngine`
The main controller class responsible for the entire workflow:
1.  **Data Retrieval**: Connects to the database and fetches high-risk records (Score >= 40, Confidence >= MODERATE).
2.  **Plan Generation**: Iterates through each risk and delegates to internal strategy logic to build `RemediationPlan` objects.
3.  **Persistence**: Serializes generated plans and stores them in the `dr365v.remediation_plans` table.

#### `RemediationPlan` (Data Class)
A structured container representing a single guidance document.
*   **Metadata**: `plan_id`, `job_name`, `generated_at`.
*   **Context**: `risk_context` (Snapshot of the Feature 5 input).
*   **Body**: `investigation_steps` (List), `remediation_options` (List), `success_criteria`.
*   **Estimates**: `urgency`, `complexity`, `estimated_effort_hours`.

#### Support Data Classes
*   **`InvestigationStep`**: Describes a diagnostic action (e.g., "Check VSS logs").
*   **`RemediationOption`**: Describes a potential fix (e.g., "Increase retry count").
*   **`SuccessCriteria`**: Defines "Definition of Done" metrics.
*   **`RiskType` (Enum)**: `JOB_FAILURE`, `CAPACITY`, `EFFICIENCY`, `RECOVERY`, `DATA_QUALITY`.

---

## 3. REMEDIATION STRATEGY LOGIC

The engine uses a conditional strategy pattern based on `RiskType` to determine the specific content of the plan.

### 3.1 Guidance Strategies

#### A. Job Failure Strategy (`JOB_FAILURE`)
*   **Focus**: Stability and Configuration.
*   **Investigation**:
    1.  Review job configuration and retry settings.
    2.  Analyze failure logs for patterns (VSS, Network).
    3.  Check infrastructure health during windows.
*   **Options**:
    *   **Config Tuning**: Adjust retry counts (typical: 3-5), timeouts.
    *   **Infrastructure Fix**: Address underlying VSS/Storage I/O issues.
    *   **Architecture**: Split large jobs to reduce window duration.
*   **Success Criteria**: Failure rate < 10% for 7 consecutive days.

#### B. Capacity Strategy (`CAPACITY`)
*   **Focus**: Sustainability and Growth Management.
*   **Investigation**:
    1.  Analyze growth rate drivers (new VMs vs data churn).
    2.  Audit retention policies vs compliance needs.
*   **Options**:
    *   **Efficiency**: Enable/Tune Deduplication & Compression.
    *   **Policy**: Reduce retention or move to GFS (Grandfather-Father-Son).
    *   **Hardware**: Expand repository storage.
*   **Success Criteria**: Growth rate reduced by 30-50% OR Time-to-full increased by 60 days.

#### C. Efficiency Strategy (`EFFICIENCY`)
*   **Focus**: Optimization of Resources.
*   **Options**:
    *   **Compression**: Change compression level (Optimize vs Extreme).
    *   **Deduplication**: Enable repository-backed deduplication.
    *   **Backup Mode**: Switch to Forward Incremental with synthetic fulls.
*   **Success Criteria**: Dedup ratio improved by 20%+, Backup duration stable.

#### D. Recovery Strategy (`RECOVERY`)
*   **Focus**: RTO Compliance and Trust.
*   **Options**:
    *   **Automation**: Implement SureBackup jobs.
    *   **Manual**: Conduct controlled manual restore tests.
    *   **Process**: Update and validate 'Run Books'.
*   **Success Criteria**: Test coverage > 80%, Test success > 95%.

### 3.2 Scoring & Estimation Logic

*   **Urgency Calculation**:
    *   **CRITICAL**: Risk Score >= 80 OR Impact >= 80.
    *   **HIGH**: Risk Score >= 60 OR Impact >= 60.
    *   **MEDIUM**: Risk Score >= 40.
    *   **LOW**: Score < 40.

*   **Complexity Level**:
    *   **HIGH**: Jobs with Risk Score >= 70.
    *   **MEDIUM**: Risk Type is CAPACITY or RECOVERY (inherently complex).
    *   **LOW**: Simple configuration changes.

*   **Effort Estimation Algorithm**:
    ```python
    InvestigationTime = sum(step.duration for step in investigation_steps)
    RemediationTime = min(option.typical_hours for option in options) # Conservative
    TotalEstimate = (InvestigationTime + RemediationTime) * 1.3 # 30% Contingency
    ```

---

## 4. DATABASE SCHEMA

The output is persisted in the `dr365v` schema.

### Table: `dr365v.remediation_plans`
| Column | Type | Description |
| :--- | :--- | :--- |
| `plan_id` | UUID | Unique identifier for this specific plan instance. |
| `risk_id` | VARCHAR | Link to the Feature 5 source risk. |
| `job_id` | VARCHAR | Link to the specific backup job (if applicable). |
| `risk_type` | VARCHAR | Enum value (`job_failure`, `capacity`, etc.). |
| `urgency` | VARCHAR | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`. |
| `plan_json` | JSONB | **The Core Artifact**. Contains the full structured guidance, steps, options, and notes. |
| `status` | VARCHAR | Workflow state (Default: `GENERATED`). |
| `estimated_effort_hours` | DECIMAL | Calculated effort estimate. |
| `generated_at` | TIMESTAMP | Creation time. |

*Note: The table uses a unique constraint on `(job_id, risk_type)` to support "Upsert" behavior—updating an existing plan if the risk persists, rather than spamming duplicate plans.*

---

## 5. CONFIGURATION (`src/feature6/config.yaml`)

### Key Parameters
*   **`feature_6.safety`**:
    *   `no_execution_guarantee`: `true` (Hardcoded enforcement).
    *   `read_only_api_only`: `true`.
*   **`risk_filtering`**:
    *   `min_risk_score`: `40` (Filters out noise).
    *   `confidence_threshold`: `MODERATE` (Ignores low-confidence risks).
*   **`plan_generation`**:
    *   `remediation_options_count`: `3` (Max options per plan).
    *   `estimate_effort`: `true`.

---

## 6. DATA FLOW PIPELINE

1.  **Schedule Trigger**: Windows Task Scheduler executes `feature6.py` via `run_feature6.bat`.
2.  **Validation**: Script validates `config.yaml` and safety flags.
3.  **Fetch**: Connects to DB, runs SQL query for `metrics_risk_analysis_consolidated`.
4.  **Process Loop**: 
    *   For each Risk Item:
        *   Determine Strategy based on `risk_type`.
        *   Instantiate `RemediationPlan` object.
        *   Populate Steps/Options/Success definitions.
        *   Calculate Metadata (Urgency, Effort).
5.  **Persist**: Upsert `RemediationPlan` into `remediation_plans` table.
6.  **Complete**: Metrics logged to console/log file.

---

## 7. SAFETY GUARANTEES

Feature 6 is designed to be safe by default and design.

1.  **Architecture-Level Isolation**: The Python code does not import or use any Veeam PowerShell cmdlets or Write-capable API libraries.
2.  **Configuration Enforcement**: The `safety` section in `config.yaml` explicitly flags the system as "planning_only".
3.  **Language Design**: The output text uses advisory language ("Consider...", "Evaluated...", "Recommended...") rather than imperative commands ("Set...", "Delete...").
4.  **Database Separation**: It writes to its own table, ensuring it never overwrites metric data.

This implementation acts as a highly intelligent, automated consultant—providing the roadmap for resolution while leaving the steering wheel in the hands of the human administrator.

---

## 8. OPERATION

### 8.1 Manual Execution
```powershell
python src\feature6\feature6.py
```

### 8.2 Security Configuration
*   **Credentials**: Loaded from `.env` file (DB_HOST, DB_USER, DB_PASSWORD).
*   **Database**: Connects to `dr365v` (Risk database) to read risk scores and write remediation plans.
*   **Safety**: All safety flags in `config.yaml` must be set to `true` (enforced at runtime).
*   **Read-Only**: Feature 6 has NO network access to Veeam API for write operations.

