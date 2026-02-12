"""
Feature 09 Verification Suite
Tests Attack Timeline logic.
"""
import sys
import os
import json
import logging
from datetime import datetime, timedelta

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.feature9.feature_09 import analyze_attack_timeline

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("F9_Verify")

def run_test(name, func):
    print(f"\n--- TEST: {name} ---")
    try:
        func()
        print("[PASS]")
    except Exception as e:
        print(f"[FAIL]: {e}")

def test_1_guardrail():
    """Verify clean agent is skipped."""
    input_data = {
        "agent_id": "006",
        "agent_name": "WIN-LSEFVDVVGRA",
        "first_seen": datetime.utcnow().isoformat() + "Z",
        "last_seen": datetime.utcnow().isoformat() + "Z",
        "detected": False
    }
    res = analyze_attack_timeline(input_data)
    assert res['guardrail_skip_downstream'] == True, "Guardrail failed"
    logger.info("Guardrail works.")

def test_2_query_logic():
    """Verify query structure works (even if 0 events found)."""
    # Mock detection
    input_data = {
        "agent_id": "006",
        "agent_name": "WIN-LSEFVDVVGRA",
        "first_seen": (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z",
        "last_seen": datetime.utcnow().isoformat() + "Z",
        "detected": True
    }
    
    res = analyze_attack_timeline(input_data)
    
    # We expect 'guardrail_skip_downstream' to be True IF no events found.
    # But status should be 'success'.
    assert res['status'] == 'success', "Query crashed"
    
    if res.get('total_events', 0) > 0:
        logger.info(f"Found {res['total_events']} events! Timeline built.")
    else:
        logger.info("No events found in window (Expected for clean agent). Logic ran successfully.")

def main():
    run_test("Guardrail Logic", test_1_guardrail)
    run_test("Timeline Logic", test_2_query_logic)

if __name__ == "__main__":
    main()
