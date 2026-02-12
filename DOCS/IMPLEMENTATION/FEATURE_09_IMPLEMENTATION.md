# FEATURE 09: ATTACK TIMELINE - TECHNICAL IMPLEMENTATION

## 1. SYSTEM ARCHITECTURE

**Feature Name:** Attack Timeline Reconstruction
**Namespace:** `src.feature9`
**Status:** Production (v2.0)
**Execution Entry:** `feature_09.py` -> `analyze_attack_timeline()`

### 1.1 Technical Components
1.  **`TimelineBuilder`**: The core engine that orchestrates queries.
2.  **`WazuhConnector`**: Provides access to the Indexer (via Dashboard Proxy).
    *   *Note*: Feature 9 heavily relies on the Dashboard Proxy (Port 443) because it needs to execute complex aggregations and "Lateral Movement" searches across all agents, which the Standard Manager API (Port 55000) does not support efficiently.

### 1.2 Data Flow Pipeline
```mermaid
graph TD
    A[Feature 7/8 Output] --> B[Calculate Time Window]
    B --> C[Query Primary Agent Events]
    B --> D[Query Lateral Movement (All Agents)]
    
    subgraph Wazuh Indexer
        C -- Pagination --> E[Fetch 10k+ Events]
        D -- Aggregation --> F[Correlation]
    end
    
    E & F --> G[Merge & Deduplicate]
    G --> H[Enrich with MITRE IDs]
    H --> I[Sort Chronologically]
    I --> J[Return Timeline JSON]
```

---

## 2. KEY ALGORITHMS & LOGIC

### 2.1 Time Window Calculation
To capture the full context of an attack, the feature expands the detection window:
*   **Start**: `First Seen Timestamp` - 60 minutes.
*   **End**: `Last Seen Timestamp` + 30 minutes.

### 2.2 Deep Pagination (`search_after`)
Standard Elasticsearch/Opensearch queries are limited to 10,000 hits (`from` + `size`).
*   **Algorithm**: We use the `search_after` parameter with a stable sort (`@timestamp` + `_id`) to cursor through unlimited results efficiently.
*   **Logic**:
    1.  Fetch 1000 events.
    2.  Read `sort` value of last event.
    3.  Pass to next query as `search_after`.
    4.  Repeat until hits < 1000.

### 2.3 Lateral Movement Detection
This heuristic detects if the compromised host was targeted by *others* or moving *to* others.
*   **Scope**: Queries **ALL** events in the index (not scoped to Agent ID).
*   **Filters**:
    *   MITRE ID: `T1021` (Remote Services).
    *   Descriptions: "SMB session", "RDP connection".
*   **Result**: Merged into the main timeline to show "Incoming" or "Outgoing" attacks.

---

## 3. CONFIGURATION

### 3.1 `config.yaml`
Located at `src/feature9/config.yaml`.
*   **max_events_fetch**: 10000 (Safety cap)
*   **lateral_movement_rules**:
    *   `mitre_ids`: ["T1021"]
    *   `descriptions`: ["SMB session", "RDP"]

### 3.2 Output Schema
```json
{
  "target_host": "WIN-LSEFVDVVGRA",
  "lateral_hosts": ["WEB-01"],
  "timeline": [
    {
      "timestamp": "2025-01-01T12:00:00Z",
      "rule_description": "PowerShell Execution",
      "mitre_technique": "T1059",
      "source_ip": "10.0.0.5"
    }
  ]
}
```
