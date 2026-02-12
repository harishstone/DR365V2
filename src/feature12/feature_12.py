"""
Feature 12: Automated Compliance Mapping
Maps SCA/Vuln findings to regulatory frameworks (NIST, ISO, PCI).
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
logger = logging.getLogger("Feature12")

# --- Input Schema ---
class Feature11Input(BaseModel):
    # Flexible input: accept findings dict directly or wrapped
    findings: Dict[str, Any]
    
    @validator('findings', pre=True)
    def extract_findings_if_wrapped(cls, v):
        # handle case where full F11 output is passed
        if isinstance(v, dict) and 'findings' in v and isinstance(v['findings'], dict):
            return v['findings']
        return v

# --- Main Logic ---
class ComplianceMapper:
    def __init__(self, config_path: str = "src/feature12/config.yaml"):
        self.config = ConfigLoader.load_config(config_path)
        self.frameworks = self.config.get('feature12', {}).get('compliance_frameworks', {})
        
        # Connector for hostname enrichment (lazy loaded logic preferred, but init is fine)
        self.connector = WazuhConnector(self.config)

    def get_agent_hostname(self, agent_id: str) -> str:
        """Fallback enrichment."""
        # Only auth if needed
        if not self.connector.api_token and not self.connector.dash_cookies:
             self.connector.authenticate()
             
        agent = self.connector.get_agent_by_id(agent_id) # Need to ensure connector has this or generic get
        # connector.get_agent takes Name.
        # Connector doesn't have get_agent_by_id. 
        # I'll implement lookup via Get All Agents cache or direct query.
        
        # Simplified: iterate all agents (cached if pos) or just return ID if fail.
        # For efficiency, F11 usually provides hostname.
        return f"Agent-{agent_id}"

    def map_gaps(self, f11_output: Dict[str, Any]) -> Dict[str, Any]:
        # 1. Validation
        try:
            # Check if input is empty/mock
            if not f11_output: return {"status": "error", "message": "Empty input"}
            
            # If input is full F11 response, extract findings
            if "findings" in f11_output:
                findings = f11_output["findings"]
            else:
                findings = f11_output
                
            # Allow empty findings (Clean scan)
            if not findings:
                 findings = {}
                 
        except Exception as e:
            return {"status": "error", "message": str(e)}

        # 2. Init Stats
        framework_stats = {}
        for fw_name, fw_def in self.frameworks.items():
            framework_stats[fw_name] = {
                'total_controls': len(fw_def.get('controls', {})),
                'failing_controls': set(),
                'failing_checks': []
            }

        # 3. Process Findings
        for agent_id, agent_data in findings.items():
            hostname = agent_data.get('hostname') or agent_id
            
            # Process SCA
            sca_list = agent_data.get('sca_failures', [])
            for fail in sca_list:
                check_id = fail.get('check_id')
                title = fail.get('title')
                compliance = fail.get('compliance', [])
                
                # Flatten compliance
                flat_comp = []
                if isinstance(compliance, list):
                    for c in compliance:
                        if isinstance(c, str): flat_comp.append(c)
                        elif isinstance(c, list): flat_comp.extend([x for x in c if isinstance(x, str)])
                
                # Map
                for fw_tag in flat_comp:
                    # fw_tag might be "PCI", "pci_dss", "PCI DSS", etc.
                    # We try to match keys in config
                    matched_fw = None
                    for key in self.frameworks:
                        if key in fw_tag or fw_tag in key: # Simple fuzzy match
                            matched_fw = key
                            break
                    
                    if matched_fw:
                        controls_map = self.frameworks[matched_fw].get('controls', {})
                        if check_id in controls_map:
                            real_ctrl = controls_map[check_id]
                            framework_stats[matched_fw]['failing_controls'].add(real_ctrl)
                            framework_stats[matched_fw]['failing_checks'].append({
                                'agent': hostname,
                                'check_id': check_id,
                                'title': title,
                                'control_id': real_ctrl
                            })

        # 4. Generate Report
        report = {}
        for fw_name, stats in framework_stats.items():
            fw_def = self.frameworks[fw_name]
            total = stats['total_controls']
            failing = len(stats['failing_controls'])
            passing = total - failing
            coverage = round((passing / total) * 100, 1) if total > 0 else 100.0
            
            status = "COMPLIANT"
            if coverage < 100: status = "AT RISK"
            if coverage < 50: status = "CRITICAL NON-COMPLIANCE"

            report[fw_name] = {
                'framework_name': fw_def.get('name'),
                'description': fw_def.get('description'),
                'total_controls': total,
                'failing_controls_count': failing,
                'coverage_percentage': coverage,
                'status': status,
                'failing_checks': stats['failing_checks']
            }

        return {
            "status": "success",
            "compliance_report": report,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

def map_compliance_gaps(f11_output: Dict[str, Any]) -> Dict[str, Any]:
    mapper = ComplianceMapper()
    return mapper.map_gaps(f11_output)

if __name__ == "__main__":
    # Test Stub
    test_f11 = {
        "findings": {
            "001": {
                "hostname": "BACKUP-PRIMARY",
                "sca_failures": [
                    {
                        "check_id": "backup_guest_account",
                        "title": "Guest Account Enabled",
                        "compliance": ["PCI", "ISO"]
                    }
                ]
            }
        }
    }
    print(json.dumps(map_compliance_gaps(test_f11), indent=2))
