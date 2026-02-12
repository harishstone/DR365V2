
"""
Feature 07: Ransomware Detection - Core Implementation
Implements ransomware detection logic following exact specifications.
Uses shared WazuhConnector from src.shared.
"""

import json
from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, validator, Field
import sys
import os

# Add project root to path to allow importing from src.shared
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.common.wazuh_connector import WazuhConnector, ConfigLoader

# --- Input Models ---
class RansomwareDetectionInput(BaseModel):
    agent_name: str
    time_window_hours: int = Field(default=24, ge=1, le=168)

# --- Core Feature Logic ---

def detect_ransomware(input_data: RansomwareDetectionInput, config_path: str = "src/feature7/config.yaml") -> Dict:
    # 1. Load Config
    config = ConfigLoader.load_config(config_path)
    
    # 2. Initialize Connector
    connector = WazuhConnector(config)
    if not connector.authenticate():
        return {"status": "error", "message": "Authentication failed for all channels"}
        
    # 3. Resolve Agent
    agent = connector.get_agent(input_data.agent_name)
    if not agent:
        return {"status": "error", "message": f"Agent '{input_data.agent_name}' not found"}
    
    agent_id = agent['id']
        
    # 4. Data Gathering (Indexer)
    hours = input_data.time_window_hours
    
    # A. File Changes (FIM)
    fim_query = {
        "size": 1000,
        "query": {
            "bool": {
                "must": [
                    {"match": {"agent.id": agent_id}},
                    {"match": {"rule.groups": "syscheck"}},
                    {"range": {"@timestamp": {"gte": f"now-{hours}h"}}}
                ]
            }
        },
        "_source": ["@timestamp", "syscheck.path", "syscheck.entropy", "syscheck.event"]
    }
    file_changes = connector.query_indexer(fim_query)
    
    # B. Security Events
    sec_query = {
        "size": 1000,
        "query": {
            "bool": {
                "must": [
                    {"match": {"agent.id": agent_id}},
                    {"range": {"@timestamp": {"gte": f"now-{hours}h"}}},
                    {
                        "bool": {
                            "should": [
                                {"match_phrase": {"rule.description": "Shadow copy"}},
                                {"match_phrase": {"rule.description": "Windows Defender"}},
                                {"match_phrase": {"rule.description": "backup"}}
                            ]
                        }
                    }
                ]
            }
        }
    }
    sec_events = connector.query_indexer(sec_query)
    
    # C. Processes
    processes = connector.get_syscollector_processes(agent_id)
    
    # 5. Analysis Logic (Exact Spec)
    file_count = len(file_changes)
    
    high_entropy_files = []
    encrypted_files = []
    entropy_threshold = 7.5
    excluded_exts = ['.mp4', '.mkv', '.avi', '.zip', '.tar.gz', '.iso', '.rar', '.7z']
    ransom_exts = ['.encrypted', '.locked', '.crypto', '.crypt', '.enc', '.crypted']
    timestamps = []
    
    for event in file_changes:
        ts = event.get('@timestamp')
        if ts: timestamps.append(ts)
        path = event.get('syscheck', {}).get('path', '')
        entropy = event.get('syscheck', {}).get('entropy')
        if isinstance(entropy, str): 
            try: entropy = float(entropy)
            except: entropy = 0.0
            
        if entropy and entropy > entropy_threshold:
            if not any(path.lower().endswith(x) for x in excluded_exts):
                high_entropy_files.append(path)
                
        if any(path.lower().endswith(x) for x in ransom_exts):
            encrypted_files.append(path)

    suspicious_procs = []
    keywords = ['crypt', 'ransom', 'lock']
    for p in processes:
        name = p.get('name', '').lower()
        cmd = p.get('cmd', '').lower()
        if any(k in name or k in cmd for k in keywords):
            suspicious_procs.append(name)
            
    shadow_deletion = False
    defender_stopped = False
    for e in sec_events:
        desc = e.get('rule', {}).get('description', '').lower()
        if 'shadow copy' in desc and 'delete' in desc:
            shadow_deletion = True
        if 'defender' in desc and 'stop' in desc:
            defender_stopped = True
            
    # 6. Scoring
    score = 0
    indicators = []
    
    if file_count > 1000:
        score += 25
        indicators.append(f"High File Mod Rate ({file_count})")
    elif file_count > 500:
        score += 10
        indicators.append(f"Elevated File Mod Rate ({file_count})")
        
    if len(encrypted_files) > 50:
        score += 20
        indicators.append(f"Mass Encryption Detected ({len(encrypted_files)})")
    elif len(encrypted_files) > 0:
        score += 10
        indicators.append(f"Encryption Extension Detected")
        
    if len(high_entropy_files) > 50:
        score += 30
        indicators.append(f"Mass High Entropy ({len(high_entropy_files)})")
    elif len(high_entropy_files) > 10:
        score += 15
        indicators.append(f"Elevated Entropy")
        
    if suspicious_procs:
        score += 20
        indicators.append(f"Suspicious Processes: {', '.join(suspicious_procs)}")
        
    if shadow_deletion:
        score += 10
        indicators.append("Shadow Copy Deletion")
        
    if defender_stopped:
        score += 10
        indicators.append("AV Tampering")
        
    final_score = min(score, 100)
    detected = final_score >= 70
    
    first_seen = min(timestamps) if timestamps else None
    last_seen = max(timestamps) if timestamps else None
    
    result = {
        "status": "success",
        "agent_id": agent_id,
        "agent_name": agent['name'],
        "detected": detected,
        "confidence": final_score,
        "indicators": indicators,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "stats": {
            "file_count": file_count,
            "high_entropy": len(high_entropy_files),
            "encrypted_files": len(encrypted_files)
        }
    }
    
    if not detected:
        result['guardrail_skip_downstream'] = True
        
    return result

def list_wazuh_agents(config_path: str = "src/feature7/config.yaml") -> List[Dict]:
    """
    List all active Wazuh agents.
    Returns: List of dicts with id, name, ip, status, os.
    """
    config = ConfigLoader.load_config(config_path)
    connector = WazuhConnector(config)
    if not connector.authenticate():
        return [{"status": "error", "message": "Authentication failed"}]
        
    # Get all agents
    agents = connector.get_all_agents()
    return agents

if __name__ == "__main__":
    try:
        print("--- Listing All Agents ---")
        agents = list_wazuh_agents()
        print(json.dumps(agents, indent=2))
        
        print("\n--- Checking Agent: WIN-LSEFVDVVGRA ---")
        sample_input = RansomwareDetectionInput(
            agent_name="WIN-LSEFVDVVGRA", # Real agent from discovery
            time_window_hours=24
        )
        report = detect_ransomware(sample_input)
        print(json.dumps(report, indent=2))
    except Exception as e:
        print(f"Error: {e}")
