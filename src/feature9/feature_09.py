"""
Feature 09: Attack Timeline Reconstruction
Builds chronological attack timeline and detects lateral movement.
"""

import sys
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
from pydantic import BaseModel, validator
import logging

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.common.wazuh_connector import WazuhConnector, ConfigLoader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Feature09")

# --- Input Schema ---
class Feature07Input(BaseModel):
    agent_id: str
    first_seen: str
    last_seen: str
    detected: bool

    @validator('first_seen', 'last_seen')
    def validate_timestamp(cls, v):
        try:
            # Handle timestamps (basic check)
            # We'll normalize fully in logic
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except ValueError:
            raise ValueError('Timestamp must be ISO 8601 format')

# --- Main Logic ---
class TimelineBuilder:
    def __init__(self, config_path: str = "src/feature9/config.yaml"):
        self.config = ConfigLoader.load_config(config_path)
        self.connector = WazuhConnector(self.config)
        self.params = self.config.get('feature9', {})
        
        # Authenticate
        if not self.connector.authenticate():
            raise RuntimeError("Feature 9 authentication failed")

    def _execute_indexer_search(self, query: Dict) -> Dict:
        """Helper to execute raw search returning full response (hits+meta)."""
        # We need sort values for pagination, so we can't use connector.query_indexer
        # which strips metadata.
        
        # Try Dashboard Proxy (Fallback) first if active, or API if Indexer API accessible?
        # Connector logic: Authentication determines method.
        # If auth_method is 'dashboard', use _proxy_request.
        # If 'api' (manager), we can't query indexer via manager port 55000 easily (unless forwarded).
        # Actually WazuhConnector assumes 'api' = Manager, 'dashboard' = Indexer Proxy.
        # Ideally we want Indexer Access.
        
        if self.connector.auth_method == 'dashboard':
            resp = self.connector._proxy_request("POST", "wazuh-alerts-*/_search", query)
            if resp and resp.status_code == 200:
                return resp.json()
            else:
                raise RuntimeError(f"Dashboard Query Failed: {resp.status_code if resp else 'No Resp'}")
        
        # If Auth is API, we usually assume Indexer Direct Access on 9200?
        # The connector doesn't implement direct indexer access on 9200 with Basic Auth 
        # unless we add it. 
        # But for this environment (blocked ports), Dashboard is key.
        # I'll rely on Dashboard.
        raise RuntimeError("Feature 9 requires Dashboard access (Port 443) or Indexer Proxy.")

    def query_timeline_events(self, agent_id: str, start: str, end: str) -> List[Dict]:
        """Query main events with pagination."""
        all_events = []
        search_after = None
        limit = self.params.get('max_events_fetch', 10000)
        
        while len(all_events) < limit:
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"agent.id": agent_id}},
                            {"range": {"@timestamp": {"gte": start, "lte": end}}}
                        ]
                    }
                },
                "sort": [{"@timestamp": "asc"}, {"_id": "asc"}],
                "size": 1000
            }
            if search_after:
                query["search_after"] = search_after
                
            try:
                resp = self._execute_indexer_search(query)
                hits = resp.get('hits', {}).get('hits', [])
                if not hits:
                    break
                    
                all_events.extend(hits)
                
                last = hits[-1]
                if 'sort' in last:
                    search_after = last['sort']
                else:
                    break
            except Exception as e:
                logger.error(f"Timeline query error: {e}")
                break
                
        return all_events

    def query_lateral_movement(self, start: str, end: str) -> List[Dict]:
        """Query lateral movement signatures across all agents."""
        rules = self.params.get('lateral_movement_rules', {})
        mitre_ids = rules.get('mitre_ids', ["T1021"])
        descriptions = rules.get('descriptions', ["SMB session", "RDP connection"])
        
        should_clauses = [{"match": {"rule.mitre.id": mid}} for mid in mitre_ids]
        should_clauses.extend([{"match": {"rule.description": d}} for d in descriptions])
        
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"range": {"@timestamp": {"gte": start, "lte": end}}},
                        {"bool": {"should": should_clauses}}
                    ]
                }
            },
            "size": 1000 # Cap lateral search
        }
        
        try:
            resp = self._execute_indexer_search(query)
            return resp.get('hits', {}).get('hits', [])
        except Exception as e:
            logger.error(f"Lateral query error: {e}")
            return []

    def build_timeline(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        # 1. Validation
        try:
            inp = Feature07Input(**input_data)
        except Exception as e:
            return {'status': 'error', 'message': f'Validation failed: {e}'}
            
        # 2. Guardrail
        if not inp.detected:
             return {
                'status': 'success',
                'guardrail_skip_downstream': True,
                'message': 'Skipped due to no detection'
            }
            
        # 3. Parameters
        ts_first = datetime.fromisoformat(inp.first_seen.replace("Z", "+00:00"))
        ts_last = datetime.fromisoformat(inp.last_seen.replace("Z", "+00:00"))
        
        pre_win = self.params.get('pre_window_minutes', 60)
        post_win = self.params.get('post_window_minutes', 30)
        
        start_win = (ts_first - timedelta(minutes=pre_win)).isoformat()
        end_win = (ts_last + timedelta(minutes=post_win)).isoformat()
        
        # 4. Get Hostname (via Connector)
        agent = self.connector.get_agent(input_data.get('agent_name', '')) # We need ID->Name resolution? Input has name.
        # Actually F7 output usually has name. If not, resolve ID.
        # Assuming input has valid agent_name or we resolve.
        host_name = input_data.get('agent_name', 'UNKNOWN')
        if host_name == 'UNKNOWN':
            # Resolve via ID? Connector has get_agent(name). 
            # We need get_agent_by_id?
            # Let's assume name is passed correctly from F7/F8.
            pass

        # 5. Queries
        main_ev = self.query_timeline_events(inp.agent_id, start_win, end_win)
        lat_ev = self.query_lateral_movement(start_win, end_win)
        
        # 6. Process & Deduplicate
        all_raw = main_ev + lat_ev
        timeline = []
        seen_keys = set()
        
        # Filter and Sort
        for hit in all_raw:
            src = hit['_source']
            uniq = (src['@timestamp'], src['agent']['id'], src['rule']['id'])
            if uniq in seen_keys:
                continue
            seen_keys.add(uniq)
            
            # Enrich
            is_lat = (src['agent']['name'] != host_name)
            
            mitre = src.get('rule', {}).get('mitre', {}).get('id', [])
            if isinstance(mitre, str): mitre = [mitre]
            
            timeline.append({
                'timestamp': src['@timestamp'],
                'agent': src['agent']['name'],
                'rule_id': src['rule']['id'],
                'description': src['rule']['description'],
                'mitre_techniques': mitre,
                'severity': src.get('rule', {}).get('level', 0),
                'is_lateral': is_lat
            })
            
        # Sort by timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        
        # 7. Final Guardrail (Empty Timeline)
        if not timeline:
             return {
                'status': 'success',
                'guardrail_skip_downstream': True,
                'message': 'No events found in window'
            }
            
        lateral_hosts = list(set(e['agent'] for e in timeline if e['is_lateral']))
        
        return {
            'status': 'success',
            'target_host': host_name,
            'time_window': {'start': start_win, 'end': end_win},
            'total_events': len(timeline),
            'timeline': timeline,
            'lateral_hosts': lateral_hosts,
            'timestamp': datetime.utcnow().isoformat() + "Z"
        }

def analyze_attack_timeline(alert_data: Dict[str, Any]) -> Dict[str, Any]:
    builder = TimelineBuilder()
    return builder.build_timeline(alert_data)

if __name__ == "__main__":
    # Test Stub
    test_input = {
        "agent_id": "006",
        "agent_name": "WIN-LSEFVDVVGRA",
        "first_seen": datetime.utcnow().isoformat() + "Z", # Now
        "last_seen": datetime.utcnow().isoformat() + "Z",
        "detected": True
    }
    # This might fail on auth if run directly without .env context in terminal, but let's try
    try:
        print(json.dumps(analyze_attack_timeline(test_input), indent=2))
    except Exception as e:
        print(f"Error: {e}")
