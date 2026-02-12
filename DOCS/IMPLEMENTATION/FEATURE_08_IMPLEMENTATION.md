# FEATURE 08: CONTEXTUAL SCORING - TECHNICAL IMPLEMENTATION

## 1. SYSTEM ARCHITECTURE

**Feature Name:** Contextual Scoring
**Namespace:** `src.feature8`
**Status:** Production (v2.0)
**Execution Entry:** `feature_08.py` -> `analyze_ransomware_context()`

### 1.1 Technical Components
1.  **`ContextScorer`**: The core class responsible for applying business logic.
2.  **`ConfigLoader`**: Loads externalized profiles (Roles, Criticality, Weights).
3.  **`WazuhConnector`**: Used to query the Indexer for "Unpatched Vulnerabilities" context.

### 1.2 Data Flow Pipeline
```mermaid
graph TD
    A[Feature 7 Output] --> B["Input Validation (Pydantic)"]
    B --> C[Check Low Confidence Guardrail]
    C -- Skip --> D[Return Unmodified]
    C -- Proceed --> E{Apply Business Context}
    
    E --> F["Check Server Criticality (Config)"]
    E --> G[Check User Role (Config)]
    E --> H[Check Time of Day (Timezone Aware)]
    E --> I[Check Patch Status (Wazuh Indexer)]
    
    F --> J[Calculate Adjusted Score]
    G --> J
    H --> J
    I --> J
    J --> K[Return Contextualized Result]
```

---

## 2. KEY ALGORITHMS & LOGIC

### 2.1 Context Factors
The feature enriches the technical detection (F7) with organizational context to reduce false negatives and prioritize real threats.

| Context Factor | Source | Logic | Weight |
| :--- | :--- | :--- | :--- |
| **Asset Value** | `config.yaml` | Tier 1 (20pts) or Tier 2 (10pts) | +10 / +20 |
| **User Role** | `config.yaml` | Role in [Finance, Admin, HR, Exec] | +15 |
| **Time of Day** | System Time | `Off-Hours` (<09:00 or >17:00) | +15 |
| **Vulnerability State** | Wazuh Indexer | CVSS >= 7.0 found on host | +10 |

### 2.2 Patch Status Check (`get_patch_status`)
*   **Query**: Queries `wazuh-states-vulnerabilities-*` index via the shared Connector.
*   **Criteria**: `vulnerability.score.base >= 7.0`.
*   **Optimization**: Returns boolean (True/False representation via count 0/1) rather than distinct list to save performance.

### 2.3 Timezone Handling
*   Input timestamps are normalized to ISO8601 UTC.
*   Business Hours (09:00-17:00) are evaluated against the Agent's configured Timezone (default UTC).

### 2.4 Guardrails
*   **Min Confidence**: If Feature 7 Raw Confidence < 70 (configurable), F8 skips processing and returns the input logic to avoid amplifying noise.

---

## 3. CONFIGURATION

### 3.1 `config.yaml`
Located at `src/feature8/config.yaml`.
Stores sensitive business logic maps:
```yaml
feature8:
  server_criticality:
    "WIN-LSEFVDVVGRA": 1 (Critical)
  user_role_profiles:
    "j.smith": "Finance"
  weights:
    tier_1: 20
    high_impact_role: 15
```
