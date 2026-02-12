# FEATURE 07: RANSOMWARE DETECTION - TECHNICAL IMPLEMENTATION

## 1. SYSTEM ARCHITECTURE

**Feature Name:** Ransomware Detection
**Namespace:** `src.feature7`
**Status:** Production (v2.0)
**Execution Entry:** `feature_07.py` -> `detect_ransomware()`

### 1.1 Technical Components
The feature uses a multi-stage detection pipeline:

1.  **`WazuhConnector`**: Shared component for Indexer/API access (Port 55000/443).
2.  **`ConfigLoader`**: Loads thresholds and weights from `config.yaml`.
3.  **`detect_ransomware`**: Main orchestration function.
4.  **`IndexerQueryBuilder`**: Dynamic DSL generation for FIM and Security Events.

### 1.2 Data Flow Pipeline
```mermaid
graph TD
    A[Start Detection] --> B[Load Config & Auth]
    B --> C{Get Agent ID}
    C -- Not Found --> D[Return Error]
    C -- Found --> E[Parallel Data Gathering]
    
    subgraph Wazuh Indexer
        E --> F[Query FIM (Syscheck)]
        E --> G[Query Security Events]
    end
    
    subgraph Wazuh API
        E --> H[Get Processes (Syscollector)]
    end
    
    F & G & H --> I[Analysis Engine]
    I --> J{Scoring Logic}
    J --> K[Calculate Confidence]
    K --> L[Return Result JSON]
```

---

## 2. KEY ALGORITHMS & LOGIC

### 2.1 Detection Heuristics
The analysis engine correlates indicators within a rolling window. It uses **Tiered Scoring** to distinguish between isolated events and mass attacks.

| Indicator Type | Condition | Weight |
| :--- | :--- | :--- |
| **File Modification** | > 1000 files | +25 (High) |
|                       | > 500 files | +10 (Elevated) |
| **Mass Encryption**   | > 50 encrypted files | +20 |
|                       | > 0 encrypted files | +10 |
| **File Entropy**      | > 50 high entropy files | +30 (Mass) |
|                       | > 10 high entropy files | +15 (Elevated) |
| **Suspicious Process**| Name match (`crypt`, `ransom`) | +20 |
| **Shadow Copy**       | Deletion detected | +10 |
| **AV Tampering**      | Defender Stopped | +10 |

### 2.2 Scoring Engine
*   **Formula**: Sum of max weight per category.
    *   Example: If 2000 files modded (+25) and 60 encrypted (+20), Score = 45.
*   **Threshold**: `Score >= 70` implies **DETECTED**.

### 2.3 File Entropy Calculation
Entropy is pre-calculated by the Wazuh Agent (`syscheck.entropy`). This feature queries the *value* provided by the agent.
*   **Optimization**: We filter out high-entropy *valid* types (approximate check using extensions like `.zip`, `.mp4`) to reduce false positives, though the primary logic relies on the extension exclusion list in `feature_07.py`.

### 2.4 Guardrails
To prevent downstream panic (Playbooks) on low-confidence events:
*   IF `detected == False`: Returns `guardrail_skip_downstream: True`.

---

## 3. CONFIGURATION & SCHEMA

### 3.1 `config.yaml`
Located at `src/feature7/config.yaml`.
*   **Entropy Threshold**: 7.5
*   **Excluded Extensions**: `.zip`, `.rar`, `.7z`, `.mp4`
*   **Ransomware Extensions**: `.encrypted`, `.locked`, `.crypto`

### 3.2 Output JSON Schema
```json
{
  "status": "success",
  "agent_id": "006",
  "detected": true,
  "confidence": 85,
  "indicators": ["Mass High Entropy", "Encryption Extension Detected"],
  "stats": {
    "file_count": 105,
    "high_entropy": 60,
    "encrypted_files": 10
  }
}
```
