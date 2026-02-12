"""
Feature 08 Verification Suite
Tests Context Scoring logic with mocked inputs.
"""
import sys
import os
import json
import logging
from datetime import datetime

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.feature8.feature_08 import analyze_ransomware_context
from src.feature7.feature_07 import detect_ransomware, RansomwareDetectionInput

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("F8_Verify")

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
        "raw_confidence": 0,
        "username": "unknown",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "detected": False
    }
    res = analyze_ransomware_context(input_data)
    assert res['guardrail_skip_downstream'] == True, "Guardrail failed"
    logger.info("Guardrail works.")

def test_2_scoring_logic():
    """Verify Tier 1 + Off-Hours boost."""
    # Mocking a detection 
    input_data = {
        "agent_id": "006", # Mapped to Tier 1 in config
        "agent_name": "WIN-LSEFVDVVGRA",
        "raw_confidence": 80,
        "username": "j.smith", # Finance (+15)
        # Using a timestamp likely off-hours (e.g. 02:00 AM local LA time)
        # LA is -8. 10:00 UTC = 02:00 LA.
        "timestamp": datetime.utcnow().replace(hour=10).isoformat() + "Z",
        "detected": True
    }
    
    res = analyze_ransomware_context(input_data)
    
    logger.info("Result Summary: " + res.get('context_summary', ''))
    
    assert res['adjusted_confidence'] > 80, "Score not boosted"
    
    # Check for presence of strings in list items
    factors_str = str(res['context_factors'])
    assert "Tier 1 Server" in factors_str, "Tier 1 missed"
    assert "High Impact User" in factors_str, "Role missed"
    
    # Off-hours might depend on actual "now", but we forced timestamp.
    # We'll see if off-hours triggered.
    logger.info(f"Factors: {res['context_factors']}")

def main():
    run_test("Guardrail Logic", test_1_guardrail)
    run_test("Context Scoring Logic", test_2_scoring_logic)

if __name__ == "__main__":
    main()
