"""
Mock Data for Ransomware Simulation (F7, F8, F9).
Defines scenarios for demonstration.
"""
from datetime import datetime, timedelta

def get_scenarios():
    now = datetime.utcnow()
    
    return {
        "clean": {
            "description": "Standard workstation with no threats.",
            "agent_name": "WORKSTATION-05",
            "agent_id": "055",
            "f7_stats": {"file_count": 120, "high_entropy": 0, "encrypted_files": 0},
            "f7_detected": False,
            "f7_confidence": 0,
            "events": []
        },
        
        "basic": {
            "description": "Basic ransomware infection on a standard laptop.",
            "agent_name": "LAPTOP-DEV-02",
            "agent_id": "022",
            "tier": 3,
            "username": "d.developer", # Not high impact
            "timezone": "UTC",
            "f7_stats": {"file_count": 500, "high_entropy": 450, "encrypted_files": 400},
            "f7_detected": True,
            "f7_confidence": 85,
            "events": [
                # Simple execution chain
                {"offset": -10, "rule_id": "1001", "desc": "Suspicious file downloaded", "mitre": "T1105", "agent": "LAPTOP-DEV-02", "level": 7},
                {"offset": -2, "rule_id": "1002", "desc": "Mass file modification detected", "mitre": "T1486", "agent": "LAPTOP-DEV-02", "level": 12}
            ],
            "vuln_count": 0
        },
        
        "critical": {
            "description": "CRITICAL: Finance Server compromised + Lateral Movement.",
            "agent_name": "DB-FINANCE-01",
            "agent_id": "001",
            "tier": 1, 
            "username": "j.smith", # Finance Role
            "timezone": "America/New_York",
            "f7_stats": {"file_count": 2000, "high_entropy": 1800, "encrypted_files": 1500},
            "f7_detected": True,
            "f7_confidence": 90, # High technical confidence
            "vuln_count": 3, # Unpatched
            "events": [
                # Timeline: Phishing -> PowerShell -> Creds -> Lateral -> Encryption
                {"offset": -60, "rule_id": "500", "desc": "Phishing email detected", "mitre": "T1566", "agent": "DB-FINANCE-01", "level": 5},
                {"offset": -45, "rule_id": "501", "desc": "PowerShell Script Execution", "mitre": "T1059.001", "agent": "DB-FINANCE-01", "level": 8},
                {"offset": -30, "rule_id": "502", "desc": "LSASS Memory Dump", "mitre": "T1003.001", "agent": "DB-FINANCE-01", "level": 10},
                # Lateral Movement from compromised host to another
                {"offset": -20, "rule_id": "503", "desc": "SMB Session Opened", "mitre": "T1021.002", "agent": "HR-SERVER-01", "level": 7}, 
                {"offset": -5, "rule_id": "504", "desc": "Volume Shadow Copy Deleted", "mitre": "T1490", "agent": "DB-FINANCE-01", "level": 10},
                {"offset": 0, "rule_id": "550", "desc": "Ransomware Encryption Detected", "mitre": "T1486", "agent": "DB-FINANCE-01", "level": 13}
            ]
        }
    }
