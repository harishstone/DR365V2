"""
Ransomware Simulator
Runs the full intelligence pipeline (F7->F8->F9) using Mock Data.
Simulates Wazuh API responses without touching real infrastructure.
"""

import sys
import os
import json
import logging
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.demo.mock_data import get_scenarios
import src.feature7.feature_07 as f7_module
from src.feature7.feature_07 import RansomwareDetectionInput
from src.feature8.feature_08 import analyze_ransomware_context
from src.feature9.feature_09 import analyze_attack_timeline

# Configure logging to stderr to keep stdout clean for MCP
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("Simulator")

class MockConnector:
    def __init__(self, config=None):
        self.config = config or {}
        self.scenario = None
        self.auth_method = "dashboard" # Pretend we are using Dashboard Fallback to trigger F9 proxy path
        
    def set_scenario(self, scenario_data):
        self.scenario = scenario_data

    def authenticate(self):
        return True
        
    def get_agent(self, agent_name):
        return {
            "id": self.scenario["agent_id"],
            "name": self.scenario["agent_name"],
            "ip": "10.10.10.10",
            "os": {"platform": "windows"}
        }

    # Indexer Query Mock (Used by F7 FIM, F8 Vulnerabilities, F9 Timeline)
    def query_indexer(self, query):
        # We try to infer what is being asked based on query structure
        # 1. FIM/Stats (Feature 7)
        if "syscheck" in str(query) or "audit" in str(query):
            # Return stats to match scenario confidence
            # This is hard because F7 queries raw logs.
            # Simplified: We rely on the fact F7 is already done or we mock detect_ransomware entirely?
            # Ideally we run the real F7 logic.
            # Real F7 queries 'wazuh-alerts-*' for syscheck/edr.
            # Use 'total' hits to derive score.
            return [{} for _ in range(self.scenario.get('f7_stats', {}).get('file_count', 0))]

        # 2. Vulnerabilities (Feature 8)
        # Checks for 'vulnerability.score.base' >= 7.0
        if "vulnerability" in str(query):
            vulns = self.scenario.get("vuln_count", 0)
            return [{} for _ in range(vulns)]
            
        return []

    # Helper for F9 raw search
    def _execute_indexer_search(self, query):
        # Feature 9 calls this. Returns dict with hits.
        # We need to build hits from scenario events.
        
        events = self.scenario.get('events', [])
        now = datetime.utcnow()
        hits = []
        
        # Determine query type: Main or Lateral?
        # Lateral query has "T1021" or "SMB"
        is_lateral_query = "T1021" in str(query) or "SMB" in str(query)
        
        for ev in events:
            # Skip if main query excludes lateral host (simple filter)
            # Lateral query includes everything usually
            
            # Map simplified event to Indexer Format
            # Timeline is relative (offset minutes)
            ts = (now + timedelta(minutes=ev['offset'])).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            
            hit = {
                "_id": f"mock_{ev['rule_id']}_{ev['offset']}",
                "_source": {
                    "@timestamp": ts,
                    "agent": {"name": ev["agent"], "id": "000"},
                    "rule": {
                        "id": ev["rule_id"],
                        "description": ev["desc"],
                        "mitre": {"id": [ev["mitre"]]},
                        "level": ev["level"]
                    },
                    "data": {}
                },
                "sort": [ts, 1]
            }
            hits.append(hit)
            
        return {"hits": {"hits": hits, "total": {"value": len(hits)}}}
        
    def _proxy_request(self, method, path, query):
        # Fallback for F7 FIM or others using proxy
        # Return object with json() method
        class MockResp:
            def __init__(self, data): self.data = data
            @property
            def status_code(self): return 200
            def json(self): return self.data
            
        if "vulnerabilities" in path:
            vulns = self.scenario.get("vuln_count", 0)
            return MockResp({"hits": {"total": {"value": vulns}, "hits": []}})
            
        if "wazuh-alerts" in path:
            # Delegate to search helper
            return MockResp(self._execute_indexer_search(query))
            
        # Default empty
        return MockResp({"hits": {"hits": []}})

    def get_syscollector_processes(self, agent_id):
        return []

# GLOBALS
ACTIVE_SCENARIO = None

def get_mock_connector_instance(config=None):
    """Factory to return a connector populated with active scenario."""
    m = MockConnector(config)
    m.set_scenario(ACTIVE_SCENARIO)
    return m

def run_simulation(scenario_key: str, step: str = "all"):
    """
    Run full pipeline simulation.
    Scenarios: 'clean', 'basic', 'critical'
    Step: 'all', 'detect', 'context', 'timeline'
    """
    global ACTIVE_SCENARIO
    data = get_scenarios()
    
    if scenario_key not in data:
        return {"status": "error", "message": f"Unknown scenario: {scenario_key}. Available: {list(data.keys())}"}
        
    ACTIVE_SCENARIO = data[scenario_key]
    
    with patch('src.feature7.feature_07.detect_ransomware') as mock_f7, \
         patch('src.feature8.feature_08.WazuhConnector', side_effect=get_mock_connector_instance), \
         patch('src.feature9.feature_09.WazuhConnector', side_effect=get_mock_connector_instance):
         
        # Setup F7 Mock Return
        s = ACTIVE_SCENARIO
        now_str = datetime.utcnow().isoformat() + "Z"
        
        # Patch ConfigLoader in F8 to inject scenario-specific Context Map
        mock_f8_config = {
            "feature8": {
                "server_criticality": {s["agent_name"]: s.get("tier", 3)},
                "user_role_profiles": {s.get("username", "user"): "Finance" if s.get("username")=="j.smith" else "User"},
                "agent_timezones": {s["agent_id"]: s.get("timezone", "UTC")},
                "weights": {"tier_1": 20, "high_impact_role": 15, "off_hours": 15, "unpatched": 10},
                "min_confidence_to_process": 70,
                "business_hours_start": 9,
                "business_hours_end": 17
            },
            "wazuh": {"api": {"port":55000}, "dashboard":{"port":443}}
        }
        
        with patch('src.feature8.feature_08.ConfigLoader.load_config', return_value=mock_f8_config):
             
            # 1. Run F7 (Mocked)
            f7_res = {
                "status": "success",
                "agent_id": s["agent_id"],
                "agent_name": s["agent_name"],
                "detected": s["f7_detected"],
                "confidence": s["f7_confidence"],
                "timestamp": now_str,
                "first_seen": (datetime.utcnow() - timedelta(minutes=60)).isoformat() + "Z",
                "last_seen": now_str,
                "stats": s["f7_stats"]
            }
            mock_f7.return_value = f7_res
            
            # Step A: F7 (Technical Detection)
            detected_data = f7_module.detect_ransomware(RansomwareDetectionInput(agent_name=s["agent_name"]))
            
            if step == "detect":
                return {"phase": "Technical Detection (Ransomware)", "result": detected_data}
            
            # Step B: F8 (Business Context)
            f8_input = {
                "agent_id": detected_data["agent_id"],
                "agent_name": detected_data["agent_name"],
                "raw_confidence": detected_data["confidence"],
                "username": s.get("username", "unknown"),
                "timestamp": detected_data["timestamp"],
                "detected": detected_data["detected"]
            }
            context_data = analyze_ransomware_context(f8_input)
            
            if step == "context":
                return {"phase": "Business Context Analysis", "result": context_data}
            
            # Step C: F9 (Attack Timeline)
            f9_input = {
                "agent_id": detected_data["agent_id"],
                "agent_name": detected_data["agent_name"],
                "first_seen": detected_data["first_seen"],
                "last_seen": detected_data["last_seen"],
                "detected": detected_data["detected"]
            }
            timeline_data = analyze_attack_timeline(f9_input)
            
            if step == "timeline":
                return {"phase": "Attack Timeline Reconstruction", "result": timeline_data}
            
            return {
                "status": "success",
                "simulation_scenario": s["description"],
                "pipeline_report": {
                    "technical_detection_report": detected_data,
                    "business_risk_assessment": context_data,
                    "chronological_attack_timeline": timeline_data
                }
            }

if __name__ == "__main__":
    import json
    # Self-test
    res = run_simulation("critical")
    print(json.dumps(res, indent=2))
