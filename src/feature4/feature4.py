#!/usr/bin/env python3
"""
Feature 4: Recovery Verification & RTO Calculation
Production-ready implementation with SureBackup integration and optimized VBR API filtering.
"""

import requests
import psycopg2
import numpy as np
from scipy import stats
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
import subprocess
import os
import json
import yaml
import collections

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("feature4")

# Load Configuration
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    if not os.path.exists(config_path):
        # Fallback to local directory
        config_path = 'config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # [SECURITY FIX] Override with Environment Variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        # Ensure sections exist
        if 'veeam' not in config: config['veeam'] = {}
        if 'database' not in config: config['database'] = {}
        
        # Veeam
        if os.getenv('VEEAM_SERVER'): config['veeam']['api_url'] = f"https://{os.getenv('VEEAM_SERVER')}:9419"
        if os.getenv('VEEAM_USERNAME'): config['veeam']['username'] = os.getenv('VEEAM_USERNAME')
        if os.getenv('VEEAM_PASSWORD'): config['veeam']['password'] = os.getenv('VEEAM_PASSWORD')

        # Database
        if os.getenv('DB_HOST'): config['database']['host'] = os.getenv('DB_HOST')
        if os.getenv('DB_PORT'): config['database']['port'] = int(os.getenv('DB_PORT'))
        if os.getenv('DB_NAME'): config['database']['database'] = os.getenv('DB_NAME')
        if os.getenv('DB_USER'): config['database']['user'] = os.getenv('DB_USER')
        if os.getenv('DB_PASSWORD'): config['database']['password'] = os.getenv('DB_PASSWORD')
    except Exception as e:
        logger.warning(f"Failed to load environment variables: {e}")

    return config

CONFIG = load_config()

@dataclass
class SureBackupResult:
    """SureBackup test result from PowerShell"""
    vm_id: str
    vm_name: str
    test_result: str  # "Success", "Partial", "Failed"
    boot_time_ms: int
    verified_drives: int
    failed_drives: int

def fetch_surebackup_results_via_powershell(
    script_path: str, 
    timeout_seconds: int = 300, 
    reject_symlinks: bool = True
) -> Dict[str, SureBackupResult]:
    """
    Execute PowerShell script to get SureBackup results with path validation
    """
    if not script_path:
        return {}
    
    try:
        # Resolve absolute path
        script_path = os.path.abspath(script_path)

        # Validate script path exists
        if not os.path.isfile(script_path):
            logger.error(f"PowerShell script not found: {script_path}")
            return {}
        
        # Validate symlinks if configured
        if reject_symlinks and os.path.islink(script_path):
             logger.error("Script path is a symbolic link (rejected per config)")
             return {}
        
        # Validate it's a PowerShell file
        if not script_path.lower().endswith('.ps1'):
             logger.error(f"Script must be a .ps1 file: {script_path}")
             return {}
        
        cmd = [
            'pwsh',
            '-NoProfile',
            '-ExecutionPolicy', 'Bypass',
            '-File', script_path,
            '-VBRServer', 'localhost',
            '-TimeoutSeconds', str(timeout_seconds)
        ]
        
        logger.info(f"Executing PowerShell script: {script_path}")
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=timeout_seconds + 10
        )
        
        if result.returncode != 0:
            logger.error(f"PowerShell failed: {result.stderr}")
            return {}
        
        output = result.stdout.strip()
        if not output:
             logger.warning("PowerShell script returned no output")
             return {}

        results_list = json.loads(output)
        results_dict = {}
        
        if not isinstance(results_list, list):
            results_list = [results_list]

        for item in results_list:
            if 'vmId' in item:
                results_dict[item['vmId']] = SureBackupResult(
                    vm_id=item['vmId'],
                    vm_name=item.get('vmName', ''),
                    test_result=item.get('testResult', 'Unknown'),
                    boot_time_ms=item.get('bootTime', 0),
                    verified_drives=item.get('verifiedDrives', 0),
                    failed_drives=item.get('failedDrives', 0)
                )
        
        logger.info(f"Retrieved SureBackup results for {len(results_dict)} VMs")
        return results_dict
        
    except Exception as e:
        logger.error(f"PowerShell execution failed: {e}")
        return {}

def interpret_surebackup_result(result: SureBackupResult) -> float:
    """Convert SureBackup test result to confidence score (0.0–1.0)"""
    test_result = result.test_result
    failed_drives = result.failed_drives
    
    if test_result == 'Success' and failed_drives == 0:
        return 1.0
    elif test_result == 'Partial' or failed_drives > 0:
        return 0.6
    elif test_result == 'Failed':
        return 0.0
    else:
        return 0.5

class VeeamRestoreClient:
    """Veeam API client for restore session data"""
    
    def __init__(self, api_url: str, username: str, password: str, timeout: int = 30):
        self.api_url = api_url.rstrip('/')
        self.token = None
        self.username = username
        self.password = password
        self.timeout = timeout
    
    def authenticate(self) -> bool:
        try:
            requests.packages.urllib3.disable_warnings()
            payload = {
                "grant_type": "password",
                "username": self.username,
                "password": self.password
            }
            
            response = requests.post(
                f"{self.api_url}/api/oauth2/token",
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
                verify=False
            )
            response.raise_for_status()
            self.token = response.json()['access_token']
            logger.info("Authenticated with Veeam API")
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def get_restore_sessions(self, job_ids: List[str], days: int = 30) -> List[Dict]:
        """
        Hybrid collection: Use PowerShell for high-performance historical data,
        consistent with Feature 1's implementation.
        """
        # 1. Attempt PowerShell Collection (Hybrid Mode)
        script_path = os.path.join(os.path.dirname(__file__), 'get_restore_history.ps1')
        if os.path.exists(script_path):
            try:
                logger.info(f"Hybrid Mode: Collecting history via PowerShell Core ({days} days)...")
                cmd = [
                    'pwsh', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                    '-File', script_path, '-Days', str(days)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                if result.returncode == 0 and result.stdout.strip():
                    ps_sessions = json.loads(result.stdout)
                    if not isinstance(ps_sessions, list):
                        ps_sessions = [ps_sessions]
                    
                    logger.info(f"Hybrid Mode: Successfully collected {len(ps_sessions)} relevant sessions")
                    # PowerShell results already containsessionId, jobId, startTime, endTime, result
                    return ps_sessions
                else:
                    logger.warning(f"PowerShell history collection failed or returned no data. Falling back to API.")
            except Exception as e:
                logger.error(f"Hybrid collection error: {e}")

        # 2. Fallback to API Surgical Collection (if PowerShell is unavailable)
        logger.info("Starting surgical API collection (fallback)...")
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        if not start_date.endswith('Z'): start_date += 'Z'
        end_date = datetime.now().isoformat()
        if not end_date.endswith('Z'): end_date += 'Z'
        
        all_sessions = []
        for job_id in job_ids:
            logger.info(f"  Scanning Job: {job_id}")
            offset = 0
            limit = 500
            try:
                while True:
                    params = {
                        'startDate': start_date, 'endDate': end_date,
                        'limit': limit, 'offset': offset,
                        'filter': f"jobId eq '{job_id}'"
                    }
                    response = requests.get(
                        f"{self.api_url}/api/v1/sessions",
                        headers=headers, params=params,
                        timeout=self.timeout, verify=False
                    )
                    response.raise_for_status()
                    batch = response.json().get('data', [])
                    if not batch: break
                    
                    for s in batch:
                        if 'id' in s and 'sessionId' not in s: s['sessionId'] = s['id']
                        if 'creationTime' in s and 'startTime' not in s: s['startTime'] = s['creationTime']
                        if isinstance(s.get('result'), dict):
                             s['result'] = s['result'].get('result', 'Unknown')
                        if s.get('endTime'):
                             all_sessions.append(s)
                    
                    if len(batch) < limit: break
                    offset += limit
            except Exception as e:
                logger.error(f"API fallback failed for job {job_id}: {e}")
                
        return all_sessions

    def get_jobs(self) -> Dict[str, Dict]:
        """Get jobs to map IDs to Names and SLA settings"""
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        try:
            response = requests.get(
                f"{self.api_url}/api/v1/jobs",
                headers=headers,
                timeout=self.timeout,
                verify=False
            )
            response.raise_for_status()
            data = response.json()
            jobs_map = {}
            for j in data.get('data', []):
                jobs_map[j['id']] = j
            return jobs_map
        except Exception as e:
             logger.error(f"Failed to get jobs: {e}")
             return {}

class RTOAnalyzer:
    """Statistical RTO analysis engine"""
    
    def __init__(self, min_tests: int = 5):
        self.min_tests = min_tests
    
    def calculate_rto_percentiles(self, durations: List[float]) -> Optional[Dict[str, float]]:
        if not durations:
            return None
            
        # If we have very few tests, we can't do robust percentiles but we can provide median
        percentiles = {
            'median': np.percentile(durations, 50),
            '90th': np.percentile(durations, 90) if len(durations) >= 5 else np.max(durations),
            '95th': np.percentile(durations, 95) if len(durations) >= 5 else np.max(durations),
            'mean': np.mean(durations),
            'std': np.std(durations) if len(durations) > 1 else 0
        }
        
        return percentiles
    
    def calculate_confidence_interval(self, durations: List[float], confidence: float = 0.95) -> Tuple[float, float]:
        if len(durations) < 2:
            return (0.0, 0.0)
        
        mean = np.mean(durations)
        std_err = stats.sem(durations)
        
        df = len(durations) - 1
        t_critical = stats.t.ppf((1 + confidence) / 2, df)
        
        margin = t_critical * std_err
        return (round(mean - margin, 2), round(mean + margin, 2))

    def classify_confidence(self, sample_count: int, success_rate: float, recency_days: int) -> str:
        """
        Classify confidence based on EXACT SPECIFICATIONS
        - HIGH: min_tests: 10, max_age_days: 30, min_success_rate: 0.95
        - MODERATE: min_tests: 5, max_age_days: 90, min_success_rate: 0.80
        - LOW: anything below
        """
        if sample_count >= 10 and success_rate >= 0.95 and recency_days <= 30:
            return 'HIGH'
        elif sample_count >= 5 and success_rate >= 0.80 and recency_days <= 90:
            return 'MODERATE'
        else:
            return 'LOW'

class TestCoverageAnalyzer:
    """Analyze test restore coverage and recency"""
    
    def calculate_test_recency_score(self, days_since_test: int) -> Tuple[float, str]:
        """
        Continuous interpolation for test recency as per Implementation Guide lines 878-892
        """
        if days_since_test <= 7:
            return 100.0, 'FRESH'
        elif days_since_test <= 30:
            score = 85 + (30 - days_since_test) / 23 * 15
            return round(score, 2), 'FRESH'
        elif days_since_test <= 60:
            score = 60 + (60 - days_since_test) / 30 * 25
            return round(score, 2), 'CURRENT'
        elif days_since_test <= 90:
            score = 30 + (90 - days_since_test) / 30 * 30
            return round(score, 2), 'STALE'
        else:
            score = max(0, 30 - (days_since_test - 90) * 0.5)
            return round(score, 2), 'CRITICAL'
    
    def calculate_test_success_rate_score(self, success_rate: float) -> float:
        """
        Continuous interpolation for success rate as per Implementation Guide lines 894-902
        """
        if success_rate >= 0.95:
            return 100.0
        elif success_rate >= 0.80:
            return 75 + (success_rate - 0.80) / 0.15 * 25
        elif success_rate >= 0.60:
            return 50 + (success_rate - 0.60) / 0.20 * 25
        else:
            return success_rate / 0.60 * 50

class ConcurrentRestoreModeler:
    """Model concurrent restore capacity using simplified queue theory"""
    
    def __init__(self, num_proxies: int = 2):
        self.num_proxies = num_proxies
    
    def calculate_concurrent_rto(self, single_restore_minutes: float, concurrent_count: int) -> float:
        if single_restore_minutes <= 0: return 0.0
        # Simplistic model: overhead increases with concurrency
        overhead = 1.1 ** (concurrent_count / self.num_proxies)
        return round(single_restore_minutes * overhead, 2)
    
    def find_max_concurrent_capacity(self, single_restore_minutes: float, target_rto_minutes: float) -> int:
        if target_rto_minutes <= 0 or single_restore_minutes > target_rto_minutes: return 1
        for c in range(2, 20):
            if self.calculate_concurrent_rto(single_restore_minutes, c) > target_rto_minutes:
                return c - 1
        return 20

class SLAComplianceChecker:
    """Check RTO compliance against SLA targets"""
    
    def check_compliance(self, predicted_rto: float, target_rto: float) -> Tuple[str, float]:
        if target_rto <= 0: return 'COMPLIANT', 100.0
        buffer = ((target_rto - predicted_rto) / target_rto) * 100
        # Clamp buffer to fit in NUMERIC(5,2) e.g. -999.99 to 100.00
        buffer = max(-999.99, min(100.0, buffer))
        
        if buffer >= 20: return 'COMPLIANT', round(buffer, 2)
        elif buffer >= 0: return 'AT_RISK', round(buffer, 2)
        else: return 'NON_COMPLIANT', round(buffer, 2)

class RecoveryConfidenceCalculator:
    """Calculate overall recovery confidence score as per SPEC"""
    
    def calculate_overall_score(self, metrics: Dict) -> float:
        # Weighted components as per spec
        weights = CONFIG['feature4']['component_weights']
        score = (
            metrics['test_success_rate'] * weights['test_success_rate'] +
            metrics['test_recency'] * weights['test_recency'] +
            metrics['rto_predictability'] * weights['rto_predictability'] +
            metrics['sla_compliance'] * weights['sla_compliance'] +
            metrics['test_coverage'] * weights['test_coverage']
        )
        return round(score, 2)

    def blend_surebackup_confidence(self, base_confidence: float, surebackup_confidence: Optional[float]) -> float:
        """Blend base and SureBackup confidence: (base * 0.7) + (sb * 0.3)"""
        if surebackup_confidence is not None:
            return (base_confidence * 0.7) + (surebackup_confidence * 0.3)
        return base_confidence

    def calculate_predictability_score(self, cv: float) -> float:
        """
        Continuous interpolation for predictability as per Implementation Guide lines 983-991
        """
        if cv <= 0.10:
            return 100.0
        elif cv <= 0.25:
            return 75 + (0.25 - cv) / 0.15 * 25
        elif cv <= 0.50:
            return 50 + (0.50 - cv) / 0.25 * 25
        else:
            return max(0, 50 - (cv - 0.50) * 100)
    
    def calculate_sla_compliance_score(self, buffer_pct: float) -> float:
        """
        Continuous interpolation for SLA compliance as per Implementation Guide lines 993-1003
        """
        if buffer_pct >= 50:
            return 100.0
        elif buffer_pct >= 30:
            return 85 + (buffer_pct - 30) / 20 * 15
        elif buffer_pct >= 10:
            return 60 + (buffer_pct - 10) / 20 * 25
        elif buffer_pct >= 0:
            return 30 + buffer_pct / 10 * 30
        else:
            return max(0, 30 + buffer_pct)

    def assign_grade(self, score: float) -> str:
        """
        Assign grade based on Implementation Guide thresholds (lines 1005-1015):
        - >= 90: A
        - >= 80: B
        - >= 70: C
        - >= 60: D
        - < 60: F
        """
        if score >= 90: return 'A'
        elif score >= 80: return 'B'
        elif score >= 70: return 'C'
        elif score >= 60: return 'D'
        else: return 'F'

def store_recovery_test_history(sessions: List[Dict], sb_results: Dict[str, SureBackupResult]):
    """
    Store historical test restore data as per EXACT SPECIFICATIONS.
    This enables Feature 1 long-term trend analysis and Feature 4 historical depth.
    """
    db_config = CONFIG['database']
    conn = None
    try:
        conn = psycopg2.connect(**db_config)
        conn.autocommit = True
        cursor = conn.cursor()
        
        for s in sessions:
            # Skip sessions without required fields
            if not s.get('sessionId') or not s.get('jobId'):
                continue
                
            # Timing calculation
            start_time = datetime.fromisoformat(s['startTime'].split('.')[0].rstrip('Z'))
            end_time = datetime.fromisoformat(s['endTime'].split('.')[0].rstrip('Z'))
            duration = (end_time - start_time).total_seconds() / 60
            
            # Get job_name with fallback
            job_name = s.get('jobName') or f"Job-{s.get('jobId', 'Unknown')[:8]}"
            
            # Check for SureBackup enhancement for THIS session
            sb_match = None
            for sb_id, res in sb_results.items():
                if res.vm_name in job_name or job_name in res.vm_name:
                    sb_match = res
                    break

            cursor.execute("""
                INSERT INTO feature4.recovery_test_history (
                    restore_session_id, job_id, job_name,
                    start_time, end_time, duration_minutes,
                    result, restore_type,
                    surebackup_test_result, surebackup_boot_time_ms,
                    surebackup_verified_drives, surebackup_failed_drives
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (restore_session_id) DO NOTHING
            """, (
                s.get('sessionId'), s.get('jobId'), job_name,
                start_time, end_time, duration,
                s.get('result', 'Unknown'), s.get('restoreType', 'Test'),
                sb_match.test_result if sb_match else None,
                sb_match.boot_time_ms if sb_match else None,
                sb_match.verified_drives if sb_match else 0,
                sb_match.failed_drives if sb_match else 0
            ))
            
    except Exception as e:
        logger.error(f"Failed to store historical test sessions: {e}")
    finally:
        if conn: conn.close()

def store_recovery_verification(report: Dict):
    """Store recovery verification results in database"""
    db_config = CONFIG['database']
    try:
        conn = psycopg2.connect(**db_config)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Convert numpy types to native python types
        for k, v in report.items():
            if hasattr(v, 'item'): 
                 report[k] = v.item()
            elif isinstance(v, (np.float64, np.float32, np.int64, np.int32)):
                 report[k] = float(v) if 'float' in str(type(v)) else int(v)

        # Delete existing row for this job to keep only latest
        cursor.execute("DELETE FROM feature4.metrics_recovery_verification WHERE job_id = %s", (report['job_id'],))

        insert_query = """
        INSERT INTO feature4.metrics_recovery_verification (
            job_id, job_name, job_type,
            rto_median_minutes, rto_90th_percentile_minutes, rto_95th_percentile_minutes,
            rto_confidence_interval_lower, rto_confidence_interval_upper,
            overall_confidence_score, recovery_grade,
            test_success_rate_score, test_recency_score, rto_predictability_score,
            sla_compliance_score, test_coverage_score,
            surebackup_enabled, surebackup_available, surebackup_confidence_score,
            surebackup_vm_boot_time_ms, surebackup_verified_drives, surebackup_failed_drives,
            successful_tests, failed_tests, total_test_attempts, success_rate_percentage,
            last_test_date, days_since_last_test, test_recency_status,
            target_rto_minutes, predicted_rto_minutes, sla_compliance_status, sla_buffer_percentage,
            single_restore_rto_minutes, max_concurrent_restores, recommended_concurrent_limit,
            priority, recommendation, next_test_recommended_date,
            sample_count, confidence_level, quality_flags
        ) VALUES (
            %(job_id)s, %(job_name)s, %(job_type)s,
            %(rto_median_minutes)s, %(rto_90th)s, %(rto_95th)s,
            %(ci_lower)s, %(ci_upper)s,
            %(overall_confidence_score)s, %(recovery_grade)s,
            %(test_success_rate_score)s, %(test_recency_score)s, %(rto_predictability_score)s,
            %(sla_compliance_score)s, %(test_coverage_score)s,
            %(surebackup_enabled)s, %(surebackup_available)s, %(surebackup_confidence_score)s,
            %(surebackup_vm_boot_time_ms)s, %(surebackup_verified_drives)s, %(surebackup_failed_drives)s,
            %(successful_tests)s, %(failed_tests)s, %(total_test_attempts)s, %(success_rate_percentage)s,
            %(last_test_date)s, %(days_since_last_test)s, %(test_recency_status)s,
            %(target_rto_minutes)s, %(predicted_rto_minutes)s, %(sla_compliance_status)s, %(sla_buffer_percentage)s,
            %(single_restore_rto_minutes)s, %(max_concurrent_restores)s, %(recommended_concurrent_limit)s,
            %(priority)s, %(recommendation)s, %(next_test_recommended_date)s,
            %(sample_count)s, %(confidence_level)s, %(quality_flags)s
        )
        """
        cursor.execute(insert_query, report)
        logger.info(f"Stored recovery verification for Job: {report['job_name']}")
    except Exception as e:
        logger.error(f"Failed to store results: {e}")
    finally:
        if 'conn' in locals() and conn: conn.close()

def main():
    logger.info("Starting Feature 4 Recovery Verification & RTO Analysis")
    
    client = VeeamRestoreClient(
        api_url=CONFIG['veeam']['api_url'],
        username=CONFIG['veeam']['username'],
        password=CONFIG['veeam']['password']
    )
    
    if not client.authenticate(): return
    
    # Load all jobs for metadata
    jobs_map = client.get_jobs()
    if not jobs_map:
        logger.warning("No jobs found. Cannot perform per-job recovery analysis.")
        return
        
    job_ids = list(jobs_map.keys())
    logger.info(f"Found {len(job_ids)} jobs. Starting surgical session collection ({CONFIG['feature4']['max_test_age_days']} days)...")
    
    # Fetch relevant sessions (Restores, SureBackups) surgically
    sessions = client.get_restore_sessions(
        job_ids=job_ids,
        days=CONFIG['feature4']['max_test_age_days']
    )
    
    if not sessions:
        logger.info("No test restore sessions found for the specified jobs.")
        return

    # Group sessions by job
    sessions_by_job = collections.defaultdict(list)
    for s in sessions:
        jid = s.get('jobId')
        if jid:
            sessions_by_job[jid].append(s)
            
    # Analyzers
    rto_analyzer = RTOAnalyzer(min_tests=CONFIG['feature4']['min_successful_tests'])
    test_analyzer = TestCoverageAnalyzer()
    concurrent_modeler = ConcurrentRestoreModeler()
    sla_checker = SLAComplianceChecker()
    calculator = RecoveryConfidenceCalculator()
    
    # Step 1: SureBackup Results (Fetch early for history population)
    sb_results = {}
    if CONFIG['feature4']['surebackup']['enabled']:
        sb_results = fetch_surebackup_results_via_powershell(
            CONFIG['feature4']['surebackup']['script_path']
        )

    # Step 2: Populate Historical Session Tracking
    store_recovery_test_history(sessions, sb_results)

    for job_id, job_sessions in sessions_by_job.items():
        # Identify Job Name and Type robustly
        job_info = jobs_map.get(job_id, {})
        job_name = job_info.get('name') or job_sessions[0].get('jobName') or f"Job-{job_id[:8]}"
        job_type = job_info.get('type', 'Backup')
        
        # Calculate RTO Statistics
        durations = []
        for s in job_sessions:
            start = datetime.fromisoformat(s['startTime'].split('.')[0].rstrip('Z'))
            end = datetime.fromisoformat(s['endTime'].split('.')[0].rstrip('Z'))
            durations.append((end - start).total_seconds() / 60)
            
        stats_rto = rto_analyzer.calculate_rto_percentiles(durations)
        if not stats_rto: continue

        ci_lower, ci_upper = rto_analyzer.calculate_confidence_interval(durations)
        
        # Test Metrics
        success_count = sum(1 for s in job_sessions if s.get('result') == 'Success')
        total_count = len(job_sessions)
        success_rate = success_count / total_count
        
        last_test = max(datetime.fromisoformat(s['endTime'].split('.')[0].rstrip('Z')) for s in job_sessions)
        days_since = (datetime.now() - last_test).days
        
        # Calculate Scores
        success_score = test_analyzer.calculate_test_success_rate_score(success_rate)
        recency_score, recency_status = test_analyzer.calculate_test_recency_score(days_since)
        
        # Component 3: RTO Predictability (20% weight) - Continuous as per Implementation Guide
        cv = stats_rto['std'] / stats_rto['mean'] if stats_rto['mean'] > 0 else 1.0
        predictability_score = calculator.calculate_predictability_score(cv)
        
        # Component 4: SLA Compliance (15% weight) - Continuous as per Implementation Guide
        job_info = jobs_map.get(job_id, {})
        target_rto = job_info.get('slaSettings', {}).get('targetRtoMinutes', 30.0)
        sla_status, sla_buffer = sla_checker.check_compliance(stats_rto['95th'], target_rto)
        sla_compliance_score = calculator.calculate_sla_compliance_score(sla_buffer)
        
        # Component 5: Test Coverage (10% weight) - Continuous as per Implementation Guide
        if total_count >= 10:
            coverage_score = 100.0
        elif total_count >= 5:
            coverage_score = 70.0
        else:
            coverage_score = 40.0
        
        # Final Confidence Score Blending
        overall_score = calculator.calculate_overall_score({
            'test_success_rate': success_score,
            'test_recency': recency_score,
            'rto_predictability': predictability_score,
            'sla_compliance': sla_compliance_score,
            'test_coverage': coverage_score
        })
        
        # SureBackup Blending
        sb_conf_points = None
        sb_available = False
        sb_boot = 0
        sb_verified = 0
        sb_failed = 0
        
        for sb_id, res in sb_results.items():
             if res.vm_name in job_name or job_name in res.vm_name:
                  sb_available = True
                  sb_conf_points = interpret_surebackup_result(res) * 100
                  sb_boot = res.boot_time_ms
                  sb_verified = res.verified_drives
                  sb_failed = res.failed_drives
                  break
        
        if sb_available:
             overall_score = calculator.blend_surebackup_confidence(overall_score, sb_conf_points)
             
        overall_score = round(min(100, overall_score), 2)
        grade = calculator.assign_grade(overall_score)
        
        report = {
            'job_id': job_id,
            'job_name': job_name,
            'job_type': 'Backup',
            'rto_median_minutes': stats_rto['median'],
            'rto_90th': stats_rto['90th'],
            'rto_95th': stats_rto['95th'],
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'overall_confidence_score': overall_score,
            'recovery_grade': grade,
            'test_success_rate_score': success_score,
            'test_recency_score': recency_score,
            'rto_predictability_score': predictability_score,
            'sla_compliance_score': sla_compliance_score,
            'test_coverage_score': coverage_score,
            'surebackup_enabled': CONFIG['feature4']['surebackup']['enabled'],
            'surebackup_available': sb_available,
            'surebackup_confidence_score': sb_conf_points if sb_available else None,
            'surebackup_vm_boot_time_ms': sb_boot,
            'surebackup_verified_drives': sb_verified,
            'surebackup_failed_drives': sb_failed,
            'successful_tests': success_count,
            'failed_tests': total_count - success_count,
            'total_test_attempts': total_count,
            'success_rate_percentage': success_rate * 100,
            'last_test_date': last_test,
            'days_since_last_test': days_since,
            'test_recency_status': recency_status,
            'target_rto_minutes': target_rto,
            'predicted_rto_minutes': stats_rto['95th'],
            'sla_compliance_status': sla_status,
            'sla_buffer_percentage': sla_buffer,
            'single_restore_rto_minutes': stats_rto['median'],
            'max_concurrent_restores': concurrent_modeler.find_max_concurrent_capacity(stats_rto['median'], target_rto),
            'recommended_concurrent_limit': concurrent_modeler.num_proxies,
            'priority': 'HIGH' if grade in ['D', 'F'] else 'LOW',
            'recommendation': "Perform regular SureBackup verification" if not sb_available else "Maintain current verification schedule",
            'next_test_recommended_date': (datetime.now() + timedelta(days=7)).date(),
            'sample_count': total_count,
            'confidence_level': rto_analyzer.classify_confidence(total_count, success_rate, days_since),
            'quality_flags': json.dumps({'surebackup': sb_available})
        }
        
        store_recovery_verification(report)

if __name__ == "__main__":
    main()
