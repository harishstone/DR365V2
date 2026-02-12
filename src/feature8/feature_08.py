"""
Feature 08: Confidence Scoring with Context
Applies business context (Criticality, Roles, Time, Patches) to Ransomware Alerts.
"""

import sys
import os
import pytz
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, validator, Field
import yaml
import logging

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.common.wazuh_connector import WazuhConnector, ConfigLoader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Feature08")

# --- Input Schema ---
class Feature07Input(BaseModel):
    agent_id: str
    agent_name: str
    raw_confidence: int = Field(ge=0, le=100)
    username: str
    timestamp: str # ISO 8601
    detected: bool

    @validator('timestamp')
    def normalize_timestamp(cls, v):
        if v.endswith('Z'):
            return v
        if '+' not in v and '-' not in v[10:]: # No offset
            return v + '+00:00'
        return v

# --- Main Logic ---
class ContextScorer:
    def __init__(self, config_path: str = "src/feature8/config.yaml"):
        self.config = ConfigLoader.load_config(config_path)
        self.connector = WazuhConnector(self.config) # Reuses auth from env
        self.profiles = self.config.get('feature8', {})
        
        # Authenticate connector
        if not self.connector.authenticate():
            logger.warning("Feature 8 failed to authenticate to Wazuh. Patch checks will fail.")

    def get_patch_status(self, agent_id: str) -> int:
        """Count vulnerabilities with CVSS >= 7.0 via Indexer."""
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"agent.id": agent_id}},
                        {"range": {"vulnerability.score.base": {"gte": 7.0}}}
                    ]
                }
            },
            "size": 0, # We only need count
            "track_total_hits": True
        }
        
        try:
            # Use Indexer Query (supports both API/Dashboard fallback via connector)
            # Connector.query_indexer expects raw query body
            # Wait, query_indexer in common/wazuh_connector returns List[Dict] (hits options).
            # I need the TOTAL hits value.
            # The connector abstraction returns [hit['_source']...].
            # It abstracts away the 'total' count. 
            
            # I need to modify or bypass connector.query_indexer slightly to get 'total'.
            # Or I can just request size=1 and check response...
            # But connector class hides the response object.
            
            # Let's inspect connector again.
            # It returns [h['_source'] for h in hits]
            
            # WORKAROUND: If I specific size=100 and get 100, I know it's >= 100.
            # Better: I'll stick to semantic check. If logic requires COUNT, strict logic requires raw response.
            # But let's look at `query_indexer` implementation.
            # It returns list of sources.
            # If I ask for size=0, it returns empty list.
            
            # I will invoke `_proxy_request` directly if I can, OR add `count_indexer` to connector?
            # Or just accept that I might need to fetch IDs. 
            # Given pagination overhead, let's fetch IDs (source=False) with size=500. 
            # If len > 0 -> Unpatched.
            # The spec says "Unpatched System: High Vulns > 0".
            # So if I find ANY, that's enough for +10 score. I don't need exact count.
            pass
        except Exception:
            pass
            
        # Re-implementation using connector
        query["size"] = 1
        query["_source"] = False
        
        results = self.connector.query_indexer(query)
        # If results list is not empty, it means we found hits.
        # Wait, if size=1, we get 1 hit.
        # But `query_indexer` returns hits list.
        # If total=0, hits=[].
        # If total=5, size=1 -> hits=[...].
        
        return len(results) # Returns 0 or 1 (indicates >0 vulns)

    def apply_context_scoring(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply business context scoring to a filtered alert."""
        
        # 1. Validation
        try:
            inp = Feature07Input(**alert_data)
        except Exception as e:
            return {"status": "error", "message": f"Validation failed: {e}"}
            
        # 2. Guardrails
        min_conf = self.profiles.get('min_confidence_to_process', 70)
        if not inp.detected or inp.raw_confidence < min_conf:
            return {
                "status": "success",
                "adjusted_confidence": inp.raw_confidence,
                "context_summary": "Skipped due to low confidence/no detection.",
                "guardrail_skip_downstream": True
            }
            
        score = inp.raw_confidence
        factors = []
        weights = self.profiles.get('weights', {})
        
        # 3. Server Criticality
        crit_map = self.profiles.get('server_criticality', {})
        tier = crit_map.get(inp.agent_name, 3) # Default Tier 3
        if tier == 1:
            score += weights.get('tier_1', 20)
            factors.append("Tier 1 Server (Critical Asset)")
        elif tier == 2:
            score += weights.get('tier_2', 10)
            factors.append("Tier 2 Server (Important Asset)")
            
        # 4. User Role
        role_map = self.profiles.get('user_role_profiles', {})
        role = role_map.get(inp.username)
        if role in ["Finance", "HR", "Admin", "Executive"]:
            score += weights.get('high_impact_role', 15)
            factors.append(f"High Impact User Role: {role}")
            
        # 5. Time of Day
        tz_map = self.profiles.get('agent_timezones', {})
        tz_str = tz_map.get(inp.agent_id, "UTC")
        try:
            tz = pytz.timezone(tz_str)
            # Parse timestamp
            dt = datetime.fromisoformat(inp.timestamp.replace('Z', '+00:00'))
            local_dt = dt.astimezone(tz)
            
            start = self.profiles.get('business_hours_start', 9)
            end = self.profiles.get('business_hours_end', 17)
            
            if not (start <= local_dt.hour < end):
                score += weights.get('off_hours', 15)
                factors.append(f"Off-Hours Activity ({local_dt.strftime('%H:%M')} {tz_str})")
        except Exception as e:
            logger.warning(f"Timezone analysis failed: {e}")
            
        # 6. Patch Status
        try:
            # Check if ANY high severities exist
            if self.get_patch_status(inp.agent_id) > 0:
                score += weights.get('unpatched', 10)
                factors.append("Unpatched System (CVSS >= 7.0 detected)")
        except Exception as e:
            logger.warning(f"Patch check failed: {e}")
            
        # 7. Finalize
        final_score = min(100, score)
        
        summary = f"Confidence adjusted from {inp.raw_confidence}% to {final_score}%."
        if factors:
            summary += " Context Factors: " + "; ".join(factors) + "."
        else:
            summary += " No additional context factors active."
            
        return {
            "status": "success",
            "agent_name": inp.agent_name,
            "base_confidence": inp.raw_confidence,
            "adjusted_confidence": final_score,
            "context_summary": summary,
            "context_factors": factors,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "guardrail_skip_downstream": False
        }

# Helper function for external callers
def analyze_ransomware_context(alert_data: Dict[str, Any]) -> Dict[str, Any]:
    scorer = ContextScorer()
    return scorer.apply_context_scoring(alert_data)

if __name__ == "__main__":
    # Test Run
    test_alert = {
        "agent_id": "006",
        "agent_name": "WIN-LSEFVDVVGRA", # Tier 1 in config
        "raw_confidence": 80,
        "username": "j.smith",  # Finance in config
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "detected": True
    }
    print(analyze_ransomware_context(test_alert))
