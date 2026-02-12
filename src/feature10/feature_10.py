"""
Feature 10: Automated Response Playbooks Advisory
Generates human-readable, MITRE-aligned response playbooks.
"""

import sys
import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, validator, Field

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.common.wazuh_connector import WazuhConnector, ConfigLoader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Feature10")

# --- Input Schema (Matches Feature 09 Output) ---
class Feature09Input(BaseModel):
    target_host: str
    lateral_hosts: List[str] = Field(default_factory=list)
    timeline: List[Dict] = Field(default_factory=list)
    total_events: int = 0
    # Optional context fields
    timestamp: Optional[str] = None

    @validator('target_host')
    def validate_target(cls, v):
        if not v or not v.strip():
            # We allow empty for guardrail handling, but we flag it
            return "" 
        return v

# --- Main Logic ---
class PlaybookGenerator:
    def __init__(self, config_path: str = "src/feature10/config.yaml"):
        self.config = ConfigLoader.load_config(config_path)
        self.connector = WazuhConnector(self.config) # Reuses shared auth
        self.templates = self.config.get('feature10', {})
        
        # Authenticate connector (lazy load only if needed? No, usually good to have ready)
        # We only need connector if CMDB fails.

    def resolve_host_details(self, hostname: str) -> Dict[str, Any]:
        """
        Resolve hostname to IP/OS via Config (CMDB Stub) or Wazuh API (Fallback).
        """
        hostname = hostname.strip()
        if not hostname:
            return {'ip': 'UNKNOWN', 'os': 'unknown'}

        # 1. Try Config/CMDB (Fast Path)
        cmdb = self.templates.get('cmdb', {}).get('demo_mappings', {})
        if hostname in cmdb:
            return cmdb[hostname]
            
        # 2. Fallback to Wazuh API
        # Only authenticate if we haven't yet
        if not self.connector.api_token and not self.connector.dash_cookies:
             self.connector.authenticate()
             
        agent = self.connector.get_agent(hostname)
        if agent:
            # Normalize OS
            os_plat = agent.get('os', {}).get('platform', 'unknown').lower()
            if 'windows' in os_plat: os_plat = 'windows'
            elif 'linux' in os_plat or 'ubuntu' in os_plat or 'centos' in os_plat: os_plat = 'linux'
            
            return {
                'ip': agent.get('ip', 'UNKNOWN'),
                'os': os_plat
            }
            
        return {'ip': 'UNKNOWN', 'os': 'unknown'}

    def check_credential_theft(self, timeline: List[Dict]) -> bool:
        """Check for T1003 in timeline."""
        for event in timeline:
            mitre = event.get('mitre_techniques', [])
            # Handle string or list
            if isinstance(mitre, str): 
                 if mitre.startswith('T1003'): return True
            elif isinstance(mitre, list):
                 if any(t.startswith('T1003') for t in mitre): return True
        return False

    def generate_playbook(self, f9_output: Dict[str, Any], user_role: str = "SOC") -> Dict[str, Any]:
        """Generate the advisory playbook."""
        
        # 1. Validation
        try:
            inp = Feature09Input(**f9_output)
        except Exception as e:
            return {"status": "error", "message": f"Validation failed: {e}"}
            
        # 2. Guardrails
        if not inp.target_host:
             return {
                "status": "success",
                "playbook_id": "none",
                "requires_approval": True,
                "steps": [],
                "guardrail_skip_downstream": True,
                "message": "No target host specified"
            }
            
        total_affected = 1 + len(inp.lateral_hosts)
        if total_affected == 0: 
             # Should be impossible given 1 target, but safe check
             pass

        # 3. Resolve Hosts
        all_hosts = [inp.target_host] + inp.lateral_hosts
        host_details = {}
        for h in all_hosts:
            host_details[h] = self.resolve_host_details(h)

        # 4. Check Triggers
        has_cred_theft = self.check_credential_theft(inp.timeline)
        
        # 5. Build Steps
        steps = []
        phases = self.templates.get('phases', {})
        
        # Phase 1: Containment
        p_cont = phases.get('immediate_containment', {})
        actions = []
        for h, det in host_details.items():
            ip = det.get('ip', 'UNKNOWN')
            if ip != 'UNKNOWN':
                cmd_tmpl = p_cont.get('actions', {}).get('network_isolation', {}).get('soar_id_template', 'SOAR: isolate_{ip}')
                actions.append({
                    "action": "Network Isolation",
                    "target": h,
                    "ip": ip,
                    "command": cmd_tmpl.format(ip=ip),
                    "priority": "CRITICAL"
                })
            else:
                actions.append({
                    "action": "Manual Isolation Required",
                    "target": h,
                    "reason": "IP Resolution Failed",
                    "priority": "HIGH"
                })
        
        steps.append({
            "phase": p_cont.get('title', 'Immediate Containment'),
            "description": p_cont.get('description', ''),
            "actions": actions
        })
        
        # Phase 2: Forensic
        p_foren = phases.get('forensic_preservation', {})
        actions = []
        for h, det in host_details.items():
            os_type = det.get('os', 'unknown')
            if os_type == 'windows':
                act_def = p_foren.get('actions', {}).get('memory_dump_windows', {})
                actions.append({
                    "action": act_def.get('name', 'Capture Memory'),
                    "target": h,
                    "tool": act_def.get('tool', 'Unknown'),
                    "note": act_def.get('note', '')
                })
            elif os_type == 'linux':
                act_def = p_foren.get('actions', {}).get('memory_dump_linux', {})
                actions.append({
                    "action": act_def.get('name', 'Capture Memory'),
                    "target": h,
                    "tool": act_def.get('tool', 'Unknown'),
                    "note": act_def.get('note', '')
                })
        
        if actions:
            steps.append({
                "phase": p_foren.get('title', 'Forensics'),
                "description": p_foren.get('description', ''),
                "actions": actions
            })
            
        # Phase 3: Credential Rotation (Optional)
        if has_cred_theft:
            p_cred = phases.get('credential_rotation', {})
            actions = []
            
            # Rotate Service Accounts
            a1 = p_cred.get('actions', {}).get('rotate_service_accounts', {})
            actions.append({
                "action": a1.get('name'),
                "target": inp.target_host,
                "note": a1.get('note')
            })
            
            # Force Pwd Reset
            a2 = p_cred.get('actions', {}).get('force_password_reset', {})
            actions.append({
                "action": a2.get('name'),
                "target": a2.get('target', 'Domain Users'),
                "note": a2.get('note')
            })
            
            steps.append({
                "phase": p_cred.get('title', 'Credential Rotation'),
                "description": p_cred.get('description', ''),
                "actions": actions
            })
            
        # Phase 4: Recovery
        p_rec = phases.get('recovery_guidance', {})
        actions = []
        a_val = p_rec.get('actions', {}).get('validate_backup', {})
        actions.append({"action": a_val.get('name'), "target": inp.target_host, "note": a_val.get('note')})
        
        a_patch = p_rec.get('actions', {}).get('patch_vulnerabilities', {})
        actions.append({"action": a_patch.get('name'), "target": "All Hosts", "note": a_patch.get('note')})
        
        steps.append({
            "phase": p_rec.get('title', 'Recovery'),
            "description": p_rec.get('description', ''),
            "actions": actions
        })

        # 6. Role Filtering
        role_map = self.templates.get('role_permissions', {})
        allowed_phases = role_map.get(user_role, role_map.get('SOC')) # Default to SOC if role unknown
        
        # If user_role not found and no 'SOC', fallback to all? No, secure by default.
        if allowed_phases:
             filtered_steps = [s for s in steps if s['phase'] in allowed_phases]
             steps = filtered_steps

        return {
            "status": "success",
            "playbook_id": f"pb_{inp.target_host}_{int(datetime.utcnow().timestamp())}",
            "target_host": inp.target_host,
            "lateral_hosts": inp.lateral_hosts,
            "total_affected_hosts": total_affected,
            "requires_approval": True,
            "user_role_context": user_role,
            "steps": steps,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

# Helper
def generate_response_playbook(f9_output: Dict[str, Any], user_role: str = "SOC") -> Dict[str, Any]:
    gen = PlaybookGenerator()
    return gen.generate_playbook(f9_output, user_role)

if __name__ == "__main__":
    # Test Stub
    test_f9 = {
        "target_host": "FILESERVER-03",
        "lateral_hosts": ["WEB-SERVER-01"],
        "timeline": [
            {"mitre_techniques": ["T1059.001"]},
            {"mitre_techniques": ["T1003.001"]} # Cred theft
        ],
        "total_events": 2
    }
    print(json.dumps(generate_response_playbook(test_f9, "SOC"), indent=2))
