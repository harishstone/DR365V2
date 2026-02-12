#!/usr/bin/env python3
"""
Feature 1: Health Metrics & Historical Analysis
Production-ready implementation with all quality checks and error handling
"""

import requests
import psycopg2
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import json
import logging
from scipy import stats
import yaml
import time
import os
import urllib3
import subprocess

# Suppress InsecureRequestWarning for self-signed certificates (common in Veeam labs)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def collect_hybrid_sessions(days=90):
    """
    Fallback method: Collect sessions via PowerShell if REST API returns insufficient history.
    """
    try:
        script_path = os.path.join(os.path.dirname(__file__), "collect_sessions.ps1")
        output_path = os.path.join(os.path.dirname(__file__), "..", "..", "feature1_sessions_hybrid.json")
        output_path = os.path.abspath(output_path)
        
        logger.info(f"Hybrid Mode: Executing PowerShell collector: {script_path}")
        
        # Determine shell (pwsh or powershell)
        shell_cmd = "pwsh"
        try:
            subprocess.run(["pwsh", "-v"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            shell_cmd = "powershell"
            logger.warning("PowerShell Core (pwsh) not found. Falling back to Windows PowerShell.")

        cmd = [shell_cmd, "-ExecutionPolicy", "Bypass", "-File", script_path, "-OutputFile", output_path, "-Days", str(days)]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"PowerShell collection failed: {result.stderr}")
            return None
            
        if not os.path.exists(output_path):
            logger.error(f"PowerShell script finished but output file missing: {output_path}")
            return None
            
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        logger.info(f"Hybrid Mode: Successfully collected {len(data)} sessions via PowerShell")
        return data
        
    except Exception as e:
        logger.error(f"Hybrid collection error: {e}")
        return None


@dataclass
class HealthScoreConfig:
    """Configuration for health scoring"""
    veeam_api_url: str
    database_config: Dict
    history_days: int = 90
    min_sessions: int = 30
    min_frequency: float = 0.33  # sessions per day
    max_variance: float = 0.50
    max_single_job_pct: float = 0.80
    cache_ttl_hours: int = 12
    component_weights: Dict = None
    
    def __post_init__(self):
        if self.component_weights is None:
            self.component_weights = {
                "failure_rate": 0.35,
                "trend": 0.25,
                "pattern": 0.20,
                "protected_objects": 0.10,
                "repository": 0.10
            }


@dataclass
class QualityValidationResult:
    """Result of data quality validation"""
    status: str  # PASS, DEGRADE, FAIL
    confidence_level: str  # HIGH, MODERATE, LOW, INSUFFICIENT
    confidence_multiplier: float  # 1.0, 0.8, 0.5, 0.0
    validation_flags: List[str]
    sample_count: int
    average_frequency: float
    date_range_days: int
    
    def to_feature5_metadata(self) -> Dict:
        """
        Generate quality metadata for Feature 5 integration
        NEW DOCS Requirement: Feature 05 - Section 4.2 (Quality Inheritance)
        
        This enables Feature 5 to validate data quality and freshness,
        implementing confidence multipliers and staleness cascade detection.
        """
        return {
            "status": self.status,
            "confidence_level": self.confidence_level,
            "confidence_multiplier": self.confidence_multiplier,
            "validation_flags": self.validation_flags,
            "sample_count": self.sample_count,
            "average_frequency": self.average_frequency,
            "date_range_days": self.date_range_days,
            # Quality checks for Feature 5 validation
            "quality_checks": {
                "sample_count_ok": self.sample_count >= 30,
                "frequency_ok": self.average_frequency >= 0.33,
                "timespan_ok": self.date_range_days >= 30,
                "metadata_ok": "INCOMPLETE_METADATA" not in self.validation_flags,
                "variance_ok": "HIGH_VARIANCE" not in self.validation_flags,
                "no_sparse_data": "SPARSE_DATA" not in self.validation_flags
            },
            "degradation_reasons": self.validation_flags,
            "overall_quality": self.status,
            # Timestamp for staleness detection
            "validated_at": datetime.now().isoformat()
        }



@dataclass
class HealthScore:
    """Complete health score results"""
    overall_score: float
    grade: str
    risk_level: str
    failure_rate_score: float
    trend_score: float
    pattern_score: float
    protected_objects_score: float
    repository_score: float
    trend_classification: str
    trend_percentage: float
    trend_is_significant: bool
    pattern_classification: str
    pattern_confidence: str
    pattern_detail: str
    correlated_failures: bool
    quality_result: QualityValidationResult
    recommendation: str


class VeeamAPIClient:
    """Handles all Veeam REST API communications"""
    
    def __init__(self, api_url: str, username: str, password: str):
        self.api_url = api_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = None
        self.token_expiry = None
        
    def authenticate(self) -> bool:
        """Obtain OAuth 2.0 bearer token"""
        try:
            # Legacy auth.py uses body parameters for username/password, not Basic Auth
            payload = {
                "grant_type": "password",
                "username": self.username,
                "password": self.password
            }
            
            response = requests.post(
                f"{self.api_url}/api/oauth2/token",
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
                verify=False
            )
            response.raise_for_status()
            
            data = response.json()
            self.token = data['access_token']
            expires_in = data.get('expires_in', 3600)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in)
            
            logger.info("Successfully authenticated with Veeam API")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def _ensure_authenticated(self):
        """Check token validity and refresh if needed"""
        if not self.token or not self.token_expiry:
            self.authenticate()
        elif datetime.now() > self.token_expiry - timedelta(minutes=5):
            logger.info("Token expiring soon, refreshing...")
            self.authenticate()
    
    def _make_request(self, endpoint: str, params: Dict = None, retries: int = 3) -> Optional[Dict]:
        """Make API request with retry logic"""
        self._ensure_authenticated()
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }
        
        url = f"{self.api_url}{endpoint}"
        
        for attempt in range(retries):
            try:
                response = requests.get(url, headers=headers, params=params, timeout=60, verify=False)
                
                if response.status_code == 401:
                    # Token expired, refresh and retry
                    logger.warning("Token expired (401), refreshing...")
                    self.authenticate()
                    headers["Authorization"] = f"Bearer {self.token}"
                    continue
                elif response.status_code == 429:
                    # Rate limited
                    wait_time = 60
                    logger.warning(f"Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                elif response.status_code >= 500:
                    # Server error, retry with backoff
                    wait_time = 30 * (attempt + 1)
                    logger.warning(f"Server error ({response.status_code}), retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout, attempt {attempt + 1}/{retries}")
                if attempt < retries - 1:
                    time.sleep(10 * (attempt + 1))
                    continue
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                if attempt < retries - 1:
                    time.sleep(10 * (attempt + 1))
                    continue
        
        logger.error(f"All {retries} attempts failed for {endpoint}")
        return None
    
    def get_sessions(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Retrieve all sessions with pagination"""
        all_sessions = []
        offset = 0
        limit = 100
        
        # Format dates per NEW DOCS: YYYY-MM-DDTHH:MM:SSZ (UTC with 'Z' suffix)
        # NEW DOCS Reference: Feature 01 - Section 8 (API Specifications)
        start_date_str = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_date_str = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        params = {
            "startDate": start_date_str,
            "endDate": end_date_str,
            "limit": limit,
            "offset": offset
        }
        
        logger.info(f"Fetching sessions from {start_date} to {end_date}")
        
        while True:
            params["offset"] = offset
            data = self._make_request("/api/v1/sessions", params)
            
            if not data:
                logger.error("Failed to retrieve sessions")
                break
            
            sessions = data.get("data", [])
            
            # Normalize session data to match Spec
            for s in sessions:
                if 'id' in s and 'sessionId' not in s:
                    s['sessionId'] = s['id']
                if 'creationTime' in s and 'startTime' not in s:
                    s['startTime'] = s['creationTime']
                
                # Handle complex result object
                if isinstance(s.get('result'), dict):
                     s['resultDetails'] = s['result']
                     s['result'] = s['result'].get('result', 'Unknown')

            all_sessions.extend(sessions)
            
            pagination = data.get("pagination", {})
            total = pagination.get("total", 0)
            logger.info(f"Retrieved {len(sessions)} sessions (Total: {len(all_sessions)}/{total})")
            
            if offset + len(sessions) >= total or len(sessions) == 0:
                break
            
            offset += limit
            # Safety break to prevent infinite loops
            if offset > 10000:
                logger.warning("Session limit 10000 reached, stopping pagination.")
                break
        
        logger.info(f"Total sessions retrieved: {len(all_sessions)}")
        return all_sessions
    
    def get_jobs(self) -> List[Dict]:
        """Retrieve all backup jobs"""
        data = self._make_request("/api/v1/jobs")
        if data:
            jobs = data.get("data", [])
            # Normalize keys
            for j in jobs:
                if 'id' in j and 'jobId' not in j:
                    j['jobId'] = j['id']
                if 'name' in j and 'jobName' not in j:
                    j['jobName'] = j['name']
                if 'type' in j and 'jobType' not in j:
                    j['jobType'] = j['type']
            
            logger.info(f"Retrieved {len(jobs)} jobs")
            return jobs
        return []
    
    def get_repositories(self) -> List[Dict]:
        """Retrieve repositories with fallback"""
        # Try primary endpoint first
        logger.info("Fetching repositories from /backupInfrastructure/repositories...")
        data = self._make_request("/api/v1/backupInfrastructure/repositories")
        
        if data:
            repos = data.get("data", [])
            logger.info(f"Retrieved {len(repos)} repositories (primary endpoint)")
            return repos
        
        # Fallback to alternative endpoint
        logger.warning("Primary repository endpoint failed, trying fallback...")
        data = self._make_request("/api/v1/repositories")
        
        if data:
            repos = data.get("data", [])
            logger.info(f"Retrieved {len(repos)} repositories (fallback endpoint)")
            return repos
        
        logger.error("Both repository endpoints failed")
        return []
    
    def get_protected_objects(self) -> List[Dict]:
        """Retrieve protected backup objects"""
        data = self._make_request("/api/v1/backupObjects")
        if data:
            objects = data.get("data", [])
            logger.info(f"Retrieved {len(objects)} protected objects")
            return objects
        return []


class CacheManager:
    """Manages 12-hour caching of API responses"""
    
    def __init__(self, cache_ttl_hours: int = 12):
        self.cache_ttl_hours = cache_ttl_hours
        self.cache = {}
    
    def is_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self.cache:
            return False
        
        cached_data = self.cache[cache_key]
        age = datetime.now() - cached_data['timestamp']
        
        return age.total_seconds() / 3600 < self.cache_ttl_hours
    
    def get(self, cache_key: str) -> Optional[Any]:
        """Retrieve cached data if valid"""
        if self.is_valid(cache_key):
            logger.info(f"Using cached data for {cache_key}")
            return self.cache[cache_key]['data']
        return None
    
    def set(self, cache_key: str, data: Any):
        """Store data in cache"""
        self.cache[cache_key] = {
            'data': data,
            'timestamp': datetime.now()
        }
        logger.info(f"Cached {cache_key}")
    
    def get_age_hours(self, cache_key: str) -> float:
        """Get age of cached data in hours"""
        if cache_key not in self.cache:
            return 0.0
        
        age = datetime.now() - self.cache[cache_key]['timestamp']
        return age.total_seconds() / 3600


class DataQualityValidator:
    """Validates data quality for health scoring"""
    
    def __init__(self, config: HealthScoreConfig):
        self.config = config
    
    def validate(self, sessions: List[Dict]) -> QualityValidationResult:
        """Perform comprehensive data quality validation"""
        validation_flags = []
        
        # Check 1: Minimum session count
        session_count = len(sessions)
        if session_count < self.config.min_sessions:
            logger.warning(f"Insufficient sessions: {session_count} < {self.config.min_sessions}")
            return QualityValidationResult(
                status="FAIL",
                confidence_level="INSUFFICIENT",
                confidence_multiplier=0.0,
                validation_flags=["INSUFFICIENT_DATA"],
                sample_count=session_count,
                average_frequency=0.0,
                date_range_days=0
            )
        
        # Check 2: Date range
        timestamps = []
        for s in sessions:
            if s.get('endTime'):
                try:
                    ts = datetime.fromisoformat(s['endTime'].rstrip('Z'))
                    timestamps.append(ts)
                except ValueError:
                    continue
        
        if not timestamps:
            return QualityValidationResult(
                status="FAIL", confidence_level="INSUFFICIENT", confidence_multiplier=0.0,
                validation_flags=["NO_VALID_TIMESTAMPS"], sample_count=session_count,
                average_frequency=0.0, date_range_days=0
            )
            
        date_range = (max(timestamps) - min(timestamps)).days
        
        if date_range < 30:
            logger.warning(f"Insufficient timespan: {date_range} days")
            validation_flags.append("INSUFFICIENT_TIMESPAN")
        
        # Check 3: Average frequency
        average_frequency = session_count / date_range if date_range > 0 else 0
        
        # Cap to avoid DB overflow (NUMERIC(5,2) max 999.99)
        if average_frequency > 999.99:
            average_frequency = 999.99
            
        if average_frequency < self.config.min_frequency:
            logger.warning(f"Sparse data: {average_frequency:.2f} sessions/day")
            validation_flags.append("SPARSE_DATA")
        
        # Check 4: Success rate variance
        job_success_rates = self._calculate_job_success_rates(sessions)
        variance = np.std(job_success_rates) if len(job_success_rates) > 1 else 0
        
        if variance > self.config.max_variance:
            logger.warning(f"High variance: {variance:.2%}")
            validation_flags.append("HIGH_VARIANCE")
        
        # Check 5: Job distribution
        job_counts = {}
        for session in sessions:
            job_id = session.get('jobId')
            job_counts[job_id] = job_counts.get(job_id, 0) + 1
        
        max_job_count = max(job_counts.values()) if job_counts else 0
        max_job_pct = max_job_count / session_count if session_count > 0 else 0
        
        if max_job_pct > self.config.max_single_job_pct:
            logger.warning(f"Single job dominates: {max_job_pct:.0%}")
            validation_flags.append("SINGLE_JOB_DOMINATES")
        
        # Check 6: Metadata completeness
        incomplete_count = 0
        for session in sessions:
            if not all([
                session.get('startTime'),
                session.get('endTime'),
                session.get('result'),
                session.get('jobId')
            ]):
                incomplete_count += 1
        
        incomplete_pct = incomplete_count / session_count if session_count > 0 else 0
        if incomplete_pct > 0.05:  # 5% threshold
            logger.error(f"Incomplete metadata: {incomplete_pct:.1%}")
            validation_flags.append("INCOMPLETE_METADATA")
        
        # Determine final status and confidence
        if validation_flags and any(flag in ["INSUFFICIENT_DATA", "INCOMPLETE_METADATA"] for flag in validation_flags):
            status = "FAIL"
            confidence_level = "INSUFFICIENT"
            confidence_multiplier = 0.0
        elif len(validation_flags) >= 2:
            status = "DEGRADE"
            confidence_level = "LOW"
            confidence_multiplier = 0.5
        elif len(validation_flags) == 1:
            status = "DEGRADE"
            confidence_level = "MODERATE"
            confidence_multiplier = 0.8
        else:
            status = "PASS"
            confidence_level = "HIGH"
            confidence_multiplier = 1.0
        
        return QualityValidationResult(
            status=status,
            confidence_level=confidence_level,
            confidence_multiplier=confidence_multiplier,
            validation_flags=validation_flags,
            sample_count=session_count,
            average_frequency=average_frequency,
            date_range_days=date_range
        )
    
    def _calculate_job_success_rates(self, sessions: List[Dict]) -> List[float]:
        """Calculate success rate for each job"""
        job_results = {}
        
        for session in sessions:
            job_id = session.get('jobId')
            result = session.get('result')
            
            if job_id not in job_results:
                job_results[job_id] = {'success': 0, 'total': 0}
            
            job_results[job_id]['total'] += 1
            if result == 'Success':
                job_results[job_id]['success'] += 1
            elif result == 'Warning':
                job_results[job_id]['success'] += 0.5  # Partial credit
        
        success_rates = []
        for job_id, counts in job_results.items():
            rate = counts['success'] / counts['total'] if counts['total'] > 0 else 0
            success_rates.append(rate)
        
        return success_rates


class TrendAnalyzer:
    """
    Analyzes trends with seasonal normalization and same-weekday comparison
    
    Implements NEW DOCS Feature 01 requirements:
    - 7-day rolling averages for smoothing daily variations
    - Same-weekday comparison (Mon-to-Mon, Tue-to-Tue) for day-of-week normalization
    - Seasonal pattern detection (month-end surge, weekend patterns)
    - Statistical significance testing (p < 0.05) using t-tests
    
    Reference: Feature 01 Health Metrics Implementation Guide Final.md
    Section 7: Production-Ready Pseudocode Implementation
    """
    
    def analyze_trend(self, sessions: List[Dict]) -> Tuple[str, float, bool, Optional[str]]:
        """
        Analyze trend with 7-day rolling averages and same-weekday comparison
        Returns: (classification, percentage, is_significant, seasonal_pattern)
        """
        # Sort sessions by time
        sessions_sorted = sorted(sessions, key=lambda s: s.get('endTime', ''))
        
        # Calculate daily success rates
        daily_rates = self._calculate_daily_success_rates(sessions_sorted)
        
        # Apply 7-day rolling average
        rolling_avg = self._calculate_rolling_average(daily_rates, window=7)
        
        # Detect seasonal patterns
        seasonal_pattern = self._detect_seasonal_pattern(sessions_sorted)
        
        # ✅ NEW: Same-weekday comparison for day-of-week normalization
        weekday_change, weekday_significant = self._calculate_same_weekday_comparison(daily_rates)
        
        # Split into thirds
        third_size = len(rolling_avg) // 3
        if third_size == 0:
             # Not enough data for thirds
             return "STABLE", 0.0, False, seasonal_pattern

        first_third = rolling_avg[:third_size]
        last_third = rolling_avg[-third_size:]
        
        # Calculate trend
        first_avg = np.mean(first_third) if first_third else 0
        last_avg = np.mean(last_third) if last_third else 0
        
        if first_avg > 0:
            trend_percentage = ((last_avg - first_avg) / first_avg) * 100
        else:
            trend_percentage = 0.0
            
        # Cap to avoid DB overflow (NUMERIC(6,2) max 9999.99)
        trend_percentage = max(-9999.0, min(9999.0, trend_percentage))
        
        # Statistical significance test
        if len(first_third) > 1 and len(last_third) > 1:
            t_stat, p_value = stats.ttest_ind(first_third, last_third)
            is_significant = bool(p_value < 0.05)
        else:
            is_significant = False
        
        # ✅ NEW: Combine with weekday significance
        # If weekday analysis shows significant change, consider it
        if weekday_significant and not is_significant:
            is_significant = True
            logger.info("Trend marked significant based on same-weekday analysis")
        
        # Classify trend
        if not is_significant:
            classification = "STABLE"
        elif trend_percentage <= -10.0:
            classification = "DEGRADING"
        elif trend_percentage >= 10.0:
            classification = "IMPROVING"
        else:
            classification = "STABLE"
        
        logger.info(f"Trend analysis: {classification} ({trend_percentage:+.1f}%), significant={is_significant}")
        logger.info(f"  - Rolling average trend: {trend_percentage:+.1f}%")
        logger.info(f"  - Same-weekday trend: {weekday_change:+.1f}%")
        
        return classification, float(trend_percentage), is_significant, seasonal_pattern
    
    def _calculate_daily_success_rates(self, sessions: List[Dict]) -> Dict[str, float]:
        """Calculate success rate for each day"""
        daily_results = {}
        
        for session in sessions:
            if not session.get('endTime'):
                continue
            date = session['endTime'][:10]  # YYYY-MM-DD
            result = session.get('result')
            
            if date not in daily_results:
                daily_results[date] = {'success': 0, 'total': 0}
            
            daily_results[date]['total'] += 1
            if result == 'Success':
                daily_results[date]['success'] += 1
            elif result == 'Warning':
                daily_results[date]['success'] += 0.5
        
        daily_rates = {}
        for date, counts in daily_results.items():
            rate = counts['success'] / counts['total'] if counts['total'] > 0 else 0
            daily_rates[date] = rate
        
        return daily_rates
    
    def _calculate_rolling_average(self, daily_rates: Dict[str, float], window: int = 7) -> List[float]:
        """Calculate rolling average with specified window"""
        dates = sorted(daily_rates.keys())
        rates = [daily_rates[d] for d in dates]
        
        if len(rates) < window:
            return rates
        
        rolling_avg = []
        for i in range(len(rates)):
            start = max(0, i - window // 2)
            end = min(len(rates), i + window // 2 + 1)
            window_rates = rates[start:end]
            rolling_avg.append(np.mean(window_rates))
        
        return rolling_avg
    
    def _detect_seasonal_pattern(self, sessions: List[Dict]) -> Optional[str]:
        """Detect month-end or weekend patterns"""
        # Check for month-end pattern (days 26-31)
        month_end_sessions = []
        other_sessions = []
        
        for s in sessions:
            if not s.get('endTime'): continue
            
            day = int(s['endTime'][8:10])
            if day >= 26:
                month_end_sessions.append(s)
            else:
                other_sessions.append(s)
        
        if len(month_end_sessions) > 5 and len(other_sessions) > 10:
            month_end_success = sum(1 for s in month_end_sessions if s['result'] == 'Success') / len(month_end_sessions)
            other_success = sum(1 for s in other_sessions if s['result'] == 'Success') / len(other_sessions)
            
            if other_success - month_end_success > 0.20:  # 20% difference
                return "MONTH_END_SURGE"
        
        # Check for weekend pattern
        weekend_sessions = []
        weekday_sessions = []
        
        for s in sessions:
            if not s.get('endTime'): continue
            try:
                dt = datetime.fromisoformat(s['endTime'].rstrip('Z'))
                if dt.weekday() >= 5:
                    weekend_sessions.append(s)
                else:
                    weekday_sessions.append(s)
            except ValueError:
                continue
        
        if len(weekend_sessions) > 5 and len(weekday_sessions) > 10:
            weekend_success = sum(1 for s in weekend_sessions if s['result'] == 'Success') / len(weekend_sessions)
            weekday_success = sum(1 for s in weekday_sessions if s['result'] == 'Success') / len(weekday_sessions)
            
            if weekday_success - weekend_success > 0.15:  # 15% difference
                return "WEEKEND_PATTERN"
        
        return None
    
    def _calculate_same_weekday_comparison(self, daily_rates: Dict[str, float]) -> Tuple[float, bool]:
        """
        Compare same weekdays (Mon-to-Mon, Tue-to-Tue, etc.)
        Returns: (percentage_change, is_significant)
        
        NEW DOCS Requirement: Feature 01 - Section 7.3
        This normalizes for day-of-week effects by comparing same weekdays over time.
        """
        # Group rates by weekday
        weekday_groups = {i: [] for i in range(7)}  # 0=Monday, 6=Sunday
        
        for date_str, rate in daily_rates.items():
            try:
                date = datetime.fromisoformat(date_str)
                weekday = date.weekday()
                weekday_groups[weekday].append((date, rate))
            except (ValueError, AttributeError):
                continue
        
        # Calculate change for each weekday
        weekday_changes = []
        for weekday, data in weekday_groups.items():
            if len(data) < 2:
                continue
            
            # Sort by date
            data_sorted = sorted(data, key=lambda x: x[0])
            
            # Compare first third vs last third
            third_size = len(data_sorted) // 3
            if third_size == 0:
                continue
            
            first_third = data_sorted[:third_size]
            last_third = data_sorted[-third_size:]
            
            first_avg = np.mean([r for _, r in first_third])
            last_avg = np.mean([r for _, r in last_third])
            
            if first_avg > 0:
                change_pct = ((last_avg - first_avg) / first_avg) * 100
                weekday_changes.append(change_pct)
        
        if not weekday_changes:
            return 0.0, False
        
        # Average change across all weekdays
        avg_change = np.mean(weekday_changes)
        
        # Statistical significance (if we have enough data)
        if len(weekday_changes) >= 3:
            # Test if changes are consistent (low variance)
            std_change = np.std(weekday_changes)
            # If std is low relative to mean, it's significant
            is_significant = abs(avg_change) > 5.0 and std_change < abs(avg_change) * 0.5
        else:
            is_significant = False
        
        logger.info(f"Same-weekday comparison: {avg_change:+.1f}% (significant={is_significant})")
        
        return float(avg_change), is_significant


class PatternRecognizer:
    """Recognizes failure patterns"""
    
    def recognize_pattern(self, sessions: List[Dict]) -> Tuple[str, str, str, bool]:
        """
        Recognize failure patterns
        Returns: (classification, confidence, detail, correlated_failures)
        """
        failures = [s for s in sessions if s.get('result') == 'Failed']
        
        if len(failures) == 0:
            return "NO_FAILURES", "N/A", "No failures detected in 30-day period", False
        
        # Extract failure metadata
        failure_times = []
        for f in failures:
            if f.get('endTime'):
                try:
                    failure_times.append(datetime.fromisoformat(f['endTime'].rstrip('Z')))
                except ValueError:
                    continue
                    
        if not failure_times:
            return "RANDOM", "LOW", "Insufficient timestamp data", False

        failure_weekdays = [ts.weekday() for ts in failure_times]
        failure_hours = [ts.hour for ts in failure_times]
        
        # Check for correlated failures (3+ jobs same time overlap - checking logic simplified here)
        # In a real implementation we would group failures by timeframe. 
        # Here we'll just check if 3+ failures occur within same hour
        correlated_failures = False
        time_groups = {}
        for ts in failure_times:
            key = ts.strftime('%Y-%m-%d %H')
            time_groups[key] = time_groups.get(key, 0) + 1
            if time_groups[key] >= 3:
                correlated_failures = True
                break

        # Check for weekday pattern
        if failure_weekdays:
            weekday_counts = {}
            for wd in failure_weekdays:
                weekday_counts[wd] = weekday_counts.get(wd, 0) + 1
            
            most_common_wd = max(weekday_counts, key=weekday_counts.get)
            weekday_concentration = weekday_counts[most_common_wd] / len(failures)
            
            if weekday_concentration >= 0.70:
                weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                return (
                    "CONSISTENT_WEEKDAY",
                    "HIGH",
                    f"Failures concentrated on {weekday_names[most_common_wd]} ({weekday_concentration:.0%})",
                    correlated_failures
                )
        
        # Check for time-of-day pattern
        if failure_hours:
            hour_counts = {}
            for hr in failure_hours:
                hour_counts[hr] = hour_counts.get(hr, 0) + 1
            
            most_common_hr = max(hour_counts, key=hour_counts.get)
            hour_concentration = hour_counts[most_common_hr] / len(failures)
            
            if hour_concentration >= 0.60:
                return (
                    "CONSISTENT_TIME",
                    "HIGH",
                    f"Failures concentrated around {most_common_hr}:00 ({hour_concentration:.0%})",
                    correlated_failures
                )
        
        # Check for intermittent pattern
        if len(failures) >= 3:
            failure_times_sorted = sorted(failure_times)
            
            gaps = []
            for i in range(1, len(failure_times_sorted)):
                gap_days = (failure_times_sorted[i] - failure_times_sorted[i-1]).days
                gaps.append(gap_days)
            
            if gaps:
                gap_std = np.std(gaps)
                gap_mean = np.mean(gaps)
                
                if gap_mean > 0 and gap_std / gap_mean < 0.30:
                    return (
                        "INTERMITTENT_REGULAR",
                        "MODERATE",
                        f"Failures every ~{gap_mean:.1f} days",
                        correlated_failures
                    )
                else:
                    return (
                        "INTERMITTENT_IRREGULAR",
                        "LOW",
                        "Failures at irregular intervals",
                        correlated_failures
                    )
        
        return "RANDOM", "LOW", "Insufficient failures for pattern detection", correlated_failures


class ScoreCalculator:
    """Calculates 5-component health scores"""
    
    def __init__(self, config: HealthScoreConfig):
        self.config = config
    
    def calculate_scores(
        self,
        sessions: List[Dict],
        trend_result: Tuple,
        pattern_result: Tuple,
        protected_objects: List[Dict],
        repositories: List[Dict]
    ) -> HealthScore:
        """Calculate all component scores and overall score"""
        
        # Unpack results
        trend_classification, trend_percentage, trend_is_significant, seasonal_pattern = trend_result
        pattern_classification, pattern_confidence, pattern_detail, correlated_failures = pattern_result
        
        # Component 1: Failure Rate Score
        failure_rate_score = self._calculate_failure_rate_score(sessions)
        
        # Component 2: Trend Score
        trend_score = self._calculate_trend_score(
            trend_classification, trend_percentage, sessions
        )
        
        # Component 3: Pattern Score
        pattern_score = self._calculate_pattern_score(
            pattern_classification, pattern_confidence, correlated_failures
        )
        
        # Component 4: Protected Objects Score
        protected_objects_score = self._calculate_protected_objects_score(protected_objects)
        
        # Component 5: Repository Score
        repository_score = self._calculate_repository_score(repositories)
        
        # Overall Score (weighted average)
        weights = self.config.component_weights
        overall_score = (
            failure_rate_score * weights["failure_rate"] +
            trend_score * weights["trend"] +
            pattern_score * weights["pattern"] +
            protected_objects_score * weights["protected_objects"] +
            repository_score * weights["repository"]
        )
        
        overall_score = round(max(0, min(100, overall_score)), 1)
        
        # Valid quality result (placeholder logic here as provided in spec example)
        # Real logic should come from DataQualityValidator
        quality_result = QualityValidationResult(
            status="PASS",
            confidence_level="HIGH",
            confidence_multiplier=1.0,
            validation_flags=[],
            sample_count=len(sessions),
            average_frequency=1.0,
            date_range_days=30
        )
        
        # Grade assignment and risk level
        grade, risk_level, recommendation = self._assign_grade(
            overall_score,
            [failure_rate_score, trend_score, pattern_score, protected_objects_score, repository_score]
        )
        
        return HealthScore(
            overall_score=overall_score,
            grade=grade,
            risk_level=risk_level,
            failure_rate_score=failure_rate_score,
            trend_score=trend_score,
            pattern_score=pattern_score,
            protected_objects_score=protected_objects_score,
            repository_score=repository_score,
            trend_classification=trend_classification,
            trend_percentage=trend_percentage,
            trend_is_significant=trend_is_significant,
            pattern_classification=pattern_classification,
            pattern_confidence=pattern_confidence,
            pattern_detail=pattern_detail,
            correlated_failures=correlated_failures,
            quality_result=quality_result,
            recommendation=recommendation
        )
    
    def _calculate_failure_rate_score(self, sessions: List[Dict]) -> float:
        """Calculate failure rate component score"""
        success_count = sum(1 for s in sessions if s.get('result') == 'Success')
        warning_count = sum(1 for s in sessions if s.get('result') == 'Warning')
        failure_count = sum(1 for s in sessions if s.get('result') == 'Failed')
        total_count = len(sessions)
        
        if total_count == 0:
            return 50.0
        
        # Warnings count as 0.5 success
        effective_success = success_count + (0.5 * warning_count)
        success_rate = effective_success / total_count
        
        score = success_rate * 100
        
        # Apply penalty for high failure count
        if failure_count > 10:
            penalty = min(10, (failure_count - 10) * 0.5)
            score -= penalty
        
        return round(max(0, min(100, score)), 1)
    
    def _calculate_trend_score(self, classification: str, percentage: float, sessions: List[Dict]) -> float:
        """Calculate trend component score"""
        failures = [s for s in sessions if s.get('result') == 'Failed']
        success_rate = (len(sessions) - len(failures)) / len(sessions) if sessions else 0
        
        if classification == "IMPROVING":
            if percentage > 20:
                return 100.0
            else:
                return 85.0 + (percentage * 0.75)
        elif classification == "STABLE":
            if success_rate >= 0.95:
                return 90.0
            elif success_rate >= 0.85:
                return 75.0
            else:
                return 60.0
        elif classification == "DEGRADING":
            base = 50.0
            if percentage < -20:
                base = 30.0
            elif percentage < -10:
                base = 50.0 - (abs(percentage) - 10) * 2
            return max(0, base)
        else:
            return 70.0
    
    def _calculate_pattern_score(self, classification: str, confidence: str, correlated: bool) -> float:
        """Calculate pattern consistency component score"""
        score_map = {
            "NO_FAILURES": 100.0,
            "RANDOM": 60.0,
            "INTERMITTENT_IRREGULAR": 55.0,
            "INTERMITTENT_REGULAR": 70.0,
            "CONSISTENT_WEEKDAY": 75.0,
            "CONSISTENT_TIME": 80.0
        }
        
        score = score_map.get(classification, 60.0)
        
        # Adjust for confidence
        if confidence == "LOW":
            score *= 0.85
        elif confidence == "MODERATE":
            score *= 0.95
        
        # Penalty for correlated failures
        if correlated:
            score -= 15
        
        return round(max(0, min(100, score)), 1)
    
    def _calculate_protected_objects_score(self, objects: List[Dict]) -> float:
        """Calculate protected objects component score"""
        if not objects:
            logger.warning("No protected objects found")
            return 50.0
        
        # Use 'lastRunFailed' as proxy for accessibility (API doesn't provide 'accessible' field)
        # Objects with successful last run are considered accessible
        accessible = sum(1 for obj in objects if not obj.get('lastRunFailed', True))
        total = len(objects)
        
        accessibility_rate = accessible / total if total > 0 else 0
        score = accessibility_rate * 100
        
        if accessibility_rate < 1.0:
            inaccessible = total - accessible
            penalty = min(20, inaccessible * 5)
            score -= penalty
        
        logger.info(f"Protected Objects Score: {score:.1f} ({accessible}/{total} accessible)")
        return round(max(0, min(100, score)), 1)
    
    def _calculate_repository_score(self, repositories: List[Dict]) -> float:
        """Calculate repository availability component score"""
        if not repositories:
            logger.error("No repositories found")
            return 50.0
        
        # Repository is "available" if it has valid configuration (id and name exist)
        # API doesn't provide 'available' field, so we check for essential fields
        available = sum(1 for repo in repositories if repo.get('id') and repo.get('name'))
        total = len(repositories)
        
        availability_rate = available / total if total > 0 else 0
        score = availability_rate * 100
        
        if availability_rate < 1.0:
            unavailable = total - available
            penalty = min(30, unavailable * 10)
            score -= penalty
        
        logger.info(f"Repository Score: {score:.1f} ({available}/{total} available)")
        return round(max(0, min(100, score)), 1)
    
    def _assign_grade(self, overall_score: float, component_scores: List[float]) -> Tuple[str, str, str]:
        """Assign letter grade, risk level, and recommendation"""
        min_component = min(component_scores) if component_scores else 0
        
        # Check for component failure override
        if min_component < 20:
            return "F", "CRITICAL", "Critical intervention required immediately - component failure detected"
        
        # Normal grade assignment
        if overall_score >= 85 and all(c >= 80 for c in component_scores):
            return "A", "LOW", "Maintain current configuration - system performing excellently"
        elif overall_score >= 70 and all(c >= 60 for c in component_scores):
            return "B", "LOW", "Monitor for changes, no immediate action needed"
        elif overall_score >= 50 and all(c >= 40 for c in component_scores):
            return "C", "MEDIUM", "Review failing jobs, consider remediation"
        elif overall_score >= 30 and all(c >= 20 for c in component_scores):
            return "D", "HIGH", "Immediate investigation required - health degrading"
        else:
            return "F", "CRITICAL", "Critical intervention required immediately"


class DatabaseWriter:
    """Handles database persistence"""
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
    
    def write_health_score(self, health_score: HealthScore, job_details: List[Dict]):
        """Write health score and job details to database"""
        conn = None
        try:
            conn = psycopg2.connect(**self.db_config)
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE)
            cur = conn.cursor()
            
            # Insert overall health score
            cur.execute("""
                INSERT INTO feature1.metrics_health_score (
                    created_at, overall_score, grade, risk_level,
                    failure_rate_score, trend_score, pattern_score,
                    protected_objects_score, repository_score,
                    trend_classification, trend_percentage, trend_is_significant,
                    pattern_classification, pattern_confidence, pattern_detail,
                    correlated_failures, sample_count, date_range_days,
                    average_frequency, confidence_level, confidence_multiplier,
                    quality_flags, last_api_call, last_session_timestamp,
                    cache_age_hours, data_age_hours, recommendation
                ) VALUES (
                    NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (created_date) DO UPDATE SET
                    created_at = NOW(),
                    overall_score = EXCLUDED.overall_score,
                    grade = EXCLUDED.grade,
                    risk_level = EXCLUDED.risk_level,
                    failure_rate_score = EXCLUDED.failure_rate_score,
                    trend_score = EXCLUDED.trend_score,
                    pattern_score = EXCLUDED.pattern_score,
                    protected_objects_score = EXCLUDED.protected_objects_score,
                    repository_score = EXCLUDED.repository_score,
                    trend_classification = EXCLUDED.trend_classification,
                    trend_percentage = EXCLUDED.trend_percentage,
                    trend_is_significant = EXCLUDED.trend_is_significant,
                    pattern_classification = EXCLUDED.pattern_classification,
                    pattern_confidence = EXCLUDED.pattern_confidence,
                    pattern_detail = EXCLUDED.pattern_detail,
                    correlated_failures = EXCLUDED.correlated_failures,
                    sample_count = EXCLUDED.sample_count,
                    date_range_days = EXCLUDED.date_range_days,
                    average_frequency = EXCLUDED.average_frequency,
                    confidence_level = EXCLUDED.confidence_level,
                    confidence_multiplier = EXCLUDED.confidence_multiplier,
                    quality_flags = EXCLUDED.quality_flags,
                    last_api_call = EXCLUDED.last_api_call,
                    last_session_timestamp = EXCLUDED.last_session_timestamp,
                    cache_age_hours = EXCLUDED.cache_age_hours,
                    data_age_hours = EXCLUDED.data_age_hours,
                    recommendation = EXCLUDED.recommendation
            """, (
                health_score.overall_score, health_score.grade, health_score.risk_level,
                health_score.failure_rate_score, health_score.trend_score, health_score.pattern_score,
                health_score.protected_objects_score, health_score.repository_score,
                health_score.trend_classification, health_score.trend_percentage,
                health_score.trend_is_significant,
                health_score.pattern_classification, health_score.pattern_confidence,
                health_score.pattern_detail, health_score.correlated_failures,
                health_score.quality_result.sample_count, health_score.quality_result.date_range_days,
                health_score.quality_result.average_frequency, health_score.quality_result.confidence_level,
                health_score.quality_result.confidence_multiplier,
                json.dumps(health_score.quality_result.to_feature5_metadata()),  # Enhanced metadata
                datetime.now(), datetime.now(), 0.0, 0.0,
                health_score.recommendation
            ))
            
            # Insert job-specific details
            for job in job_details:
                cur.execute("""
                    INSERT INTO feature1.metrics_job_failures (
                        created_at, job_id, job_name, job_type,
                        success_count, warning_count, failure_count,
                        total_sessions, success_rate,
                        trend_classification, pattern_classification,
                        sessions_analyzed, recommendation, priority
                    ) VALUES (
                        NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (job_id, created_date) DO UPDATE SET
                        created_at = NOW(),
                        job_name = EXCLUDED.job_name,
                        job_type = EXCLUDED.job_type,
                        success_count = EXCLUDED.success_count,
                        warning_count = EXCLUDED.warning_count,
                        failure_count = EXCLUDED.failure_count,
                        total_sessions = EXCLUDED.total_sessions,
                        success_rate = EXCLUDED.success_rate,
                        trend_classification = EXCLUDED.trend_classification,
                        pattern_classification = EXCLUDED.pattern_classification,
                        sessions_analyzed = EXCLUDED.sessions_analyzed,
                        recommendation = EXCLUDED.recommendation,
                        priority = EXCLUDED.priority
                """, (
                    job['job_id'], job['job_name'], job.get('job_type'),
                    job['success_count'], job['warning_count'], job['failure_count'],
                    job['total_sessions'], job['success_rate'],
                    job.get('trend'), job.get('pattern'),
                    job['total_sessions'], job.get('recommendation', ''), job.get('priority', 'MEDIUM')
                ))
            
            conn.commit()
            logger.info(f"Successfully wrote health scores for {len(job_details)} jobs to database")
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database write failed: {e}")
            raise
        finally:
            if conn:
                cur.close()
                conn.close()


def main():
    """Main execution function"""
    # Load configuration
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
            
        # [SECURITY FIX] Override with Environment Variables if present
        # This allows credentials to be managed securely in .env while maintaining backward compatibility
        from dotenv import load_dotenv
        load_dotenv()
        
        # Veeam Credentials
        if os.getenv('VEEAM_SERVER'): config_data['veeam']['api_url'] = f"https://{os.getenv('VEEAM_SERVER')}:9419"
        if os.getenv('VEEAM_USERNAME'): config_data['veeam']['username'] = os.getenv('VEEAM_USERNAME')
        if os.getenv('VEEAM_PASSWORD'): config_data['veeam']['password'] = os.getenv('VEEAM_PASSWORD')
        
        # Database Credentials
        if os.getenv('DB_HOST'): config_data['database']['host'] = os.getenv('DB_HOST')
        if os.getenv('DB_PORT'): config_data['database']['port'] = int(os.getenv('DB_PORT'))
        if os.getenv('DB_NAME'): config_data['database']['database'] = os.getenv('DB_NAME')
        if os.getenv('DB_USER'): config_data['database']['user'] = os.getenv('DB_USER')
        if os.getenv('DB_PASSWORD'): config_data['database']['password'] = os.getenv('DB_PASSWORD')
        
    except FileNotFoundError:
        logger.error("config.yaml not found!")
        return

    config = HealthScoreConfig(
        veeam_api_url=config_data['veeam']['api_url'],
        database_config=config_data['database']
    )
    
    # Initialize components
    api_client = VeeamAPIClient(
        api_url=config.veeam_api_url,
        username=config_data['veeam']['username'],
        password=config_data['veeam']['password']
    )
    
    cache_manager = CacheManager(cache_ttl_hours=config.cache_ttl_hours)
    validator = DataQualityValidator(config)
    trend_analyzer = TrendAnalyzer()
    pattern_recognizer = PatternRecognizer()
    score_calculator = ScoreCalculator(config)
    db_writer = DatabaseWriter(config.database_config)
    
    logger.info("Starting Feature 1: Health Metrics & Historical Analysis")
    
    # Authenticate
    if not api_client.authenticate():
        logger.error("Failed to authenticate with Veeam API")
        return
    
    # Collect data (with caching)
    end_date = datetime.now()
    days_back = getattr(config, 'history_days', 90)
    start_date = end_date - timedelta(days=days_back)
    
    sessions = cache_manager.get('sessions')
    if not sessions:
        logger.info("Attempting REST API collection...")
        sessions = api_client.get_sessions(start_date, end_date)
        
        # QUALITY CHECK: Switch to Hybrid if REST API returns insufficient history
        use_hybrid = False
        if not sessions:
            logger.warning("REST API returned NO sessions. Triggering Hybrid Fallback.")
            use_hybrid = True
        else:
            # Check date span to ensure we have enough history for trend analysis
            try:
                # Handle potential mixed formats or verify keys
                dates = []
                for s in sessions:
                    t = s.get('creationTime')
                    if t:
                        dates.append(t)
                        
                if dates:
                    dates.sort()
                    # Basic ISO parsing (resilient to Z vs +00:00)
                    min_dt_str = dates[0].split('T')[0]
                    max_dt_str = dates[-1].split('T')[0]
                    min_dt = datetime.strptime(min_dt_str, "%Y-%m-%d")
                    max_dt = datetime.strptime(max_dt_str, "%Y-%m-%d")
                    
                    span_days = (max_dt - min_dt).days
                    logger.info(f"REST API returned {len(sessions)} sessions spanning {span_days} days.")
                    
                    if span_days < 30:  # If less than 30 days, we need better data
                        logger.warning(f"Insufficient history ({span_days} < 30 days). Triggering Hybrid Fallback for better accuracy.")
                        use_hybrid = True
            except Exception as e:
                logger.warning(f"Failed to calculate span, sticking with REST data: {e}")
        
        # HYBRID FALLBACK EXECUTION
        if use_hybrid:
            hybrid_data = collect_hybrid_sessions(days_back)
            if hybrid_data:
                logger.info("Switching to Hybrid PowerShell data.")
                sessions = hybrid_data
            else:
                logger.warning("Hybrid Fallback failed. Reverting to whatever REST API provided.")

        if sessions:
            cache_manager.set('sessions', sessions)
    
    jobs = cache_manager.get('jobs')
    if not jobs:
        jobs = api_client.get_jobs()
        if jobs:
            cache_manager.set('jobs', jobs)
    
    repositories = cache_manager.get('repositories')
    if not repositories:
        repositories = api_client.get_repositories()
        if repositories:
            cache_manager.set('repositories', repositories)
    
    protected_objects = cache_manager.get('protected_objects')
    if not protected_objects:
        protected_objects = api_client.get_protected_objects()
        if protected_objects:
            cache_manager.set('protected_objects', protected_objects)
    
    # Validate data quality
    quality_result = validator.validate(sessions)
    if quality_result.status == "FAIL":
        logger.error("Data quality validation failed - skipping health scoring")
        return
    
    # Analyze trends and patterns
    trend_result = trend_analyzer.analyze_trend(sessions)
    pattern_result = pattern_recognizer.recognize_pattern(sessions)
    
    # Calculate scores
    health_score = score_calculator.calculate_scores(
        sessions, trend_result, pattern_result,
        protected_objects, repositories
    )
    
    # Override quality_result with the actual one from validator
    health_score.quality_result = quality_result
    
    # Prepare job details
    job_details = []
    
    # ✅ FIX: Discover jobs from SESSIONS, not just current configuration
    # This ensures deleted/old jobs that contribute to the score are reported
    unique_job_ids = set(s.get('jobId') for s in sessions if s.get('jobId'))
    
    # Map job ID to Name from current jobs list (for better metadata)
    job_lookup = {j['jobId']: j for j in jobs}
    
    for job_id in unique_job_ids:
        job_sessions = [s for s in sessions if s.get('jobId') == job_id]
        if not job_sessions:
            continue
            
        # Get job metadata (fallback to session data if job deleted)
        current_job_config = job_lookup.get(job_id, {})
        # Fallback chain: Config -> Session.jobName -> Session.name -> Unknown
        job_name = (
            current_job_config.get('jobName') or 
            job_sessions[0].get('jobName') or 
            job_sessions[0].get('name') or 
            'Unknown Job'
        )
        job_type = current_job_config.get('jobType') or job_sessions[0].get('sessionType') or 'Unknown'
        
        success_count = sum(1 for s in job_sessions if s.get('result') == 'Success')
        warning_count = sum(1 for s in job_sessions if s.get('result') == 'Warning')
        failure_count = sum(1 for s in job_sessions if s.get('result') == 'Failed')
        total = len(job_sessions)
        success_rate = (success_count + 0.5 * warning_count) / total * 100 if total > 0 else 0
        
        # Simple per-job analysis
        job_trend_res = trend_analyzer.analyze_trend(job_sessions)
        job_pattern_res = pattern_recognizer.recognize_pattern(job_sessions)
        
        # Determine priority based on failure rate
        if success_rate < 50:
            priority = 'HIGH'
            rec = 'Immediate breakdown investigation'
        elif success_rate < 80:
            priority = 'MEDIUM'
            rec = 'Monitor and optimize'
        else:
            priority = 'LOW'
            rec = 'Monitor regularly'

        job_details.append({
            'job_id': job_id,
            'job_name': job_name,
            'job_type': job_type,
            'success_count': success_count,
            'warning_count': warning_count,
            'failure_count': failure_count,
            'total_sessions': total,
            'success_rate': round(success_rate, 2),
            'trend': job_trend_res[0],
            'pattern': job_pattern_res[0],
            'recommendation': rec,
            'priority': priority
        })
    
    # Write to database
    db_writer.write_health_score(health_score, job_details)
    
    logger.info(f"Feature 1 complete - Overall Score: {health_score.overall_score} (Grade {health_score.grade})")


if __name__ == "__main__":
    main()
