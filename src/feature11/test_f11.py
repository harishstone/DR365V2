
import sys
import os
import json
sys.path.append(os.getcwd())
from src.feature11.feature_11 import scan_backup_security

print("--- Testing Feature 11: Backup Security Scan ---")
try:
    # This will fail on real auth if 'backup-servers' group doesnt exist or FIM check fails
    # But we want to ensure Code Logic runs.
    # Note: it calls endpoint.
    res = scan_backup_security("backup-servers")
    print("Result Status:", res.get('status'))
    print("Message:", res.get('message', ''))
    if res.get('status') == 'success':
        print(f"Risk Score: {res.get('risk_score')}")
except Exception as e:
    print(f"Failed: {e}")
