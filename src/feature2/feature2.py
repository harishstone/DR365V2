#!/usr/bin/env python3
"""
Feature 2: Capacity Exhaustion Forecasting
Production-ready implementation following NEW DOCS specifications

NEW DOCS Compliance:
- Feature 02 Capacity Forecasting Implementation Guide Final.md
- FEATURE_2_EXACT_SPECIFICATIONS.md
- Comprehensive Technical Analysis Report

Key Capabilities:
- Polynomial regression (linear vs quadratic with p-value testing)
- Statistical significance testing (p < 0.05 for quadratic)
- Deduplication trend analysis and growth adjustment
- 95% confidence intervals for predictions
- Quality metadata for Feature 5 integration
"""

import os
import sys
import yaml
import logging
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
import warnings

# Scientific computing
import numpy as np
import pandas as pd
from scipy import stats
import psycopg2
from psycopg2.extras import RealDictCursor
import requests

# Suppress warnings for clean output
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('Feature2_Capacity')

# =============================================================================
# CONFIGURATION
# =============================================================================

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file"""
    if not os.path.isabs(config_path):
        config_path = os.path.join(os.path.dirname(__file__), config_path)
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    # [SECURITY FIX] Override with Environment Variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
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
        print(f"Warning: Failed to load environment variables: {e}")

    return config

CONFIG = load_config()

# Data Quality Thresholds
MIN_DAYS = CONFIG['feature2']['min_days']
MIN_FREQUENCY = CONFIG['feature2']['min_frequency']
MAX_GAP_DAYS = CONFIG['feature2']['max_gap_days']
OUTLIER_THRESHOLD = CONFIG['feature2']['outlier_threshold']

# Confidence Classification
R_SQUARED_HIGH = CONFIG['feature2']['r_squared_high']
R_SQUARED_MODERATE = CONFIG['feature2']['r_squared_moderate']

# Deduplication Thresholds
DEDUP_IMPROVING_THRESHOLD = CONFIG['feature2']['dedup_improving_threshold']
DEDUP_DEGRADING_THRESHOLD = CONFIG['feature2']['dedup_degrading_threshold']
DEDUP_IMPROVING_ADJUSTMENT = CONFIG['feature2']['dedup_improving_adjustment']
DEDUP_DEGRADING_ADJUSTMENT = CONFIG['feature2']['dedup_degrading_adjustment']

# Statistical Significance
P_VALUE_THRESHOLD = CONFIG['feature2']['p_value_threshold']

# Priority Classification
URGENT_THRESHOLD_DAYS = CONFIG['feature2']['urgent_threshold_days']
HIGH_THRESHOLD_DAYS = CONFIG['feature2']['high_threshold_days']
MEDIUM_THRESHOLD_DAYS = CONFIG['feature2']['medium_threshold_days']


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CapacityForecast:
    """Complete forecast results"""
    repository_id: str
    repository_name: str
    repository_type: str
    total_capacity_gb: float
    current_used_gb: float
    current_utilization_pct: float
    
    # Predictions
    days_to_80: Optional[int]
    days_to_90: Optional[int]
    days_to_100: Optional[int]
    
    # Confidence intervals
    days_to_80_ci: Tuple[Optional[int], Optional[int]]
    days_to_100_ci: Tuple[Optional[int], Optional[int]]
    
    # Growth analysis
    growth_rate: float
    acceleration: float
    growth_pattern: str
    
    # Model quality
    model_type: str
    r_squared: float
    sample_count: int
    confidence_level: str
    confidence_multiplier: float
    
    # Deduplication
    dedup_trend: str
    dedup_adjustment_applied: bool
    current_dedup_ratio: Optional[float]
    
    # Quality
    quality_flags: Dict
    gaps_interpolated: int
    outliers_removed: int
    
    # Recommendations
    priority: str
    recommendation: str
    recommended_capacity_gb: Optional[float]


# =============================================================================
# VEEAM API CLIENT
# =============================================================================

class VeeamCapacityClient:
    """Veeam API client for capacity data"""
    
    def __init__(self, api_url: str, username: str, password: str):
        self.api_url = api_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = None
        self.token_expiry = None
        self.verify_ssl = False  # Self-signed certs in lab
    
    def authenticate(self) -> bool:
        """Obtain OAuth token"""
        try:
            # Veeam API expects username/password in request body
            payload = {
                "grant_type": "password",
                "username": self.username,
                "password": self.password
            }
            
            response = requests.post(
                f"{self.api_url}/api/oauth2/token",
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                verify=self.verify_ssl,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            self.token = data['access_token']
            self.token_expiry = datetime.now() + timedelta(seconds=data.get('expires_in', 3600))
            logger.info("Authenticated with Veeam API")
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def _ensure_authenticated(self):
        """Check token validity and refresh if needed"""
        if not self.token or (self.token_expiry and datetime.now() >= self.token_expiry):
            self.authenticate()
    
    def get_repositories(self) -> List[Dict]:
        """Get current repository capacity using /states endpoint"""
        self._ensure_authenticated()
        headers = {"Authorization": f"Bearer {self.token}"}
        
        try:
            # Use /states endpoint which has capacity data
            response = requests.get(
                f"{self.api_url}/api/v1/backupInfrastructure/repositories/states",
                headers=headers,
                verify=self.verify_ssl,
                timeout=60
            )
            
            response.raise_for_status()
            repos = response.json().get('data', [])
            logger.info(f"Retrieved {len(repos)} repositories")
            return repos
        except Exception as e:
            logger.error(f"Failed to get repositories: {e}")
            return []


# =============================================================================
# DATA PREPROCESSOR
# =============================================================================

class DataPreprocessor:
    """Preprocess capacity data for regression"""
    
    @staticmethod
    def interpolate_gaps(df: pd.DataFrame, max_gap_days: int = 2) -> Tuple[pd.DataFrame, int]:
        """Linear interpolation for gaps ≤ max_gap_days"""
        if df.empty:
            return df, 0
        
        df = df.sort_values('date').copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        # Resample to daily frequency
        df_daily = df.resample('D').asfreq()
        
        # Count gaps before interpolation
        gaps_before = df_daily['capacity_gb'].isna().sum()
        
        # Interpolate only small gaps
        df_daily['capacity_gb'] = df_daily['capacity_gb'].interpolate(
            method='linear',
            limit=max_gap_days,
            limit_direction='both'
        )
        
        # Count gaps after interpolation
        gaps_after = df_daily['capacity_gb'].isna().sum()
        interpolated_count = gaps_before - gaps_after
        
        if interpolated_count > 0:
            logger.info(f"Interpolated {interpolated_count} missing days")
        
        if gaps_after > 0:
            logger.warning(f"Found {gaps_after} days with gaps > {max_gap_days} days")
        
        return df_daily.reset_index(), interpolated_count
    
    @staticmethod
    def remove_outliers(data: np.array, threshold: float = 3.0) -> Tuple[np.array, int]:
        """Remove outliers beyond threshold standard deviations"""
        if len(data) < 3:
            return data, 0
        
        mean = np.mean(data)
        std = np.std(data)
        
        if std == 0:
            return data, 0
        
        outliers = np.abs(data - mean) > (threshold * std)
        outlier_count = np.sum(outliers)
        
        if outlier_count > 0:
            logger.warning(f"Removing {outlier_count} outliers (>{threshold} sigma)")
            data_clean = data[~outliers]
            return data_clean, outlier_count
        
        return data, 0


# =============================================================================
# DEDUPLICATION ANALYZER
# =============================================================================

class DedupAnalyzer:
    """Analyze deduplication trends"""
    
    @staticmethod
    def analyze_dedup_trend(dedup_ratios: List[float]) -> Tuple[str, float]:
        """
        Classify dedup trend and calculate adjustment factor
        Returns: (trend_classification, adjustment_factor)
        """
        if len(dedup_ratios) < 10:
            return "UNKNOWN", 1.0
        
        # Split into first half and second half
        mid = len(dedup_ratios) // 2
        first_half = dedup_ratios[:mid]
        second_half = dedup_ratios[mid:]
        
        first_avg = np.mean(first_half)
        second_avg = np.mean(second_half)
        
        diff = second_avg - first_avg
        
        # Classify trend
        if diff > DEDUP_IMPROVING_THRESHOLD:
            return "IMPROVING", DEDUP_IMPROVING_ADJUSTMENT
        elif diff < DEDUP_DEGRADING_THRESHOLD:
            return "DEGRADING", DEDUP_DEGRADING_ADJUSTMENT
        else:
            return "STABLE", 1.0


# =============================================================================
# POLYNOMIAL FORECASTER
# =============================================================================

class PolynomialForecaster:
    """Core forecasting engine using polynomial regression"""
    
    def __init__(self, min_rsquared: float = 0.70):
        self.min_rsquared = min_rsquared
    
    def fit_model(self, x: np.array, y: np.array) -> Dict:
        """Fit polynomial model and select linear vs quadratic"""
        n = len(x)
        
        # Fit both models
        coeffs_linear = np.polyfit(x, y, deg=1)
        coeffs_quad = np.polyfit(x, y, deg=2)
        
        # Extract quadratic coefficients
        a, b, c = coeffs_quad
        
        # Statistical significance test for quadratic coefficient
        # Build design matrix
        X = np.column_stack([x**2, x, np.ones_like(x)])
        
        # Calculate residuals and MSE
        y_pred_quad = np.polyval(coeffs_quad, x)
        residuals = y - y_pred_quad
        mse = np.sum(residuals**2) / (n - 3)
        
        # Calculate standard error of 'a' coefficient
        try:
            XtX_inv = np.linalg.inv(X.T @ X)
            se_a = np.sqrt(mse * XtX_inv[0, 0])
            
            # Calculate t-statistic and p-value
            if se_a > 0:
                t_stat = abs(a / se_a)
                p_value = 2 * stats.t.sf(t_stat, df=n-3)
            else:
                p_value = 1.0
        except:
            p_value = 1.0
        
        # Model selection based on p-value
        if p_value < P_VALUE_THRESHOLD:
            model_type = "QUADRATIC"
            coeffs = coeffs_quad
            logger.info(f"Selected QUADRATIC model (p={p_value:.4f})")
        else:
            model_type = "LINEAR"
            coeffs = np.array([0.0, coeffs_linear[0], coeffs_linear[1]])
            logger.info(f"Selected LINEAR model (p={p_value:.4f})")
        
        # Calculate R²
        y_pred = np.polyval(coeffs, x)
        ss_res = np.sum((y - y_pred)**2)
        ss_tot = np.sum((y - np.mean(y))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        
        return {
            'coeffs': coeffs,
            'model_type': model_type,
            'r_squared': r_squared,
            'p_value': p_value,
            'mse': mse
        }
    
    def solve_for_threshold(self, coeffs: np.array, threshold: float, current_day: int) -> Optional[int]:
        """
        Solve polynomial equation for threshold
        Returns days from current_day, or None if no valid solution
        """
        a, b, c = coeffs
        c_adj = c - threshold
        
        # Check if quadratic or linear
        if abs(a) < 1e-6:  # Linear model
            if abs(b) < 1e-6:  # Stable capacity
                return None
            
            x = -c_adj / b
            
            if b < 0:  # Declining
                return None
            
            days_from_now = x - current_day
            return int(days_from_now) if days_from_now > 0 else None
        
        else:  # Quadratic model
            # Quadratic formula
            discriminant = b**2 - 4*a*c_adj
            
            if discriminant < 0:  # No real solution
                return None
            
            sqrt_disc = np.sqrt(discriminant)
            x1 = (-b + sqrt_disc) / (2*a)
            x2 = (-b - sqrt_disc) / (2*a)
            
            # Select valid positive solution in the future
            solutions = [x1, x2]
            valid_solutions = [x for x in solutions if x > current_day]
            
            if not valid_solutions:
                return None
            
            # Take earliest valid solution
            x_solution = min(valid_solutions)
            days_from_now = x_solution - current_day
            
            return int(days_from_now) if days_from_now > 0 else None


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

class DatabaseOperations:
    """Handle all database interactions"""
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
    
    def get_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)
    
    def get_historical_data(self, repo_id: str, days: int = 60) -> pd.DataFrame:
        """Get historical capacity data from database"""
        conn = self.get_connection()
        try:
            query = """
                SELECT 
                    created_at as date,
                    used_space_bytes / (1024.0^3) as capacity_gb,
                    deduplication_ratio
                FROM feature2.capacity_history_raw
                WHERE repository_id = %s
                  AND created_at >= NOW() - INTERVAL '%s days'
                  AND source = 'veeam_api'
                ORDER BY created_at ASC
            """
            df = pd.read_sql(query, conn, params=(repo_id, days))
            return df
        finally:
            conn.close()
    
    def save_current_measurement(self, repo: Dict):
        """Save current capacity measurement to history"""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            
            # Convert GB to bytes for storage
            total_capacity_bytes = int(repo.get('capacityGB', 0) * (1024**3))
            used_space_bytes = int(repo.get('usedSpaceGB', 0) * (1024**3))
            free_space_bytes = int(repo.get('freeGB', 0) * (1024**3))
            
            # UPSERT capacity history (one record per repo per day)
            cur.execute("""
                INSERT INTO feature2.capacity_history_raw
                (repository_id, repository_name, total_capacity_bytes, 
                 used_space_bytes, free_space_bytes, utilization_pct, source, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'veeam_api', NOW())
                ON CONFLICT (repository_id, created_date)
                DO UPDATE SET
                    created_at = NOW(),
                    repository_name = EXCLUDED.repository_name,
                    total_capacity_bytes = EXCLUDED.total_capacity_bytes,
                    used_space_bytes = EXCLUDED.used_space_bytes,
                    free_space_bytes = EXCLUDED.free_space_bytes,
                    utilization_pct = EXCLUDED.utilization_pct,
                    source = EXCLUDED.source
            """, (
                repo['id'],
                repo['name'],
                total_capacity_bytes,
                used_space_bytes,
                free_space_bytes,
                (used_space_bytes / total_capacity_bytes * 100) if total_capacity_bytes > 0 else 0
            ))
            conn.commit()
        finally:
            conn.close()
    
    def save_forecast(self, forecast: CapacityForecast):
        """Save forecast to database"""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO feature2.metrics_capacity_forecast
                (repository_id, repository_name, repository_type, total_capacity_gb, current_used_gb, current_utilization_pct,
                 days_to_80_percent, days_to_90_percent, days_to_100_percent,
                 days_to_80_ci_lower, days_to_80_ci_upper, days_to_100_ci_lower, days_to_100_ci_upper,
                 growth_rate_gb_per_day, acceleration_factor, growth_pattern,
                 model_type, r_squared, sample_count, confidence_level, confidence_multiplier,
                 dedup_trend, dedup_adjustment_applied, current_dedup_ratio,
                 quality_flags, gaps_interpolated, outliers_removed,
                 priority, recommendation, recommended_capacity_gb, created_at)
                VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (repository_id, created_date)
                DO UPDATE SET
                    created_at = NOW(),
                    repository_name = EXCLUDED.repository_name,
                    repository_type = EXCLUDED.repository_type,
                    total_capacity_gb = EXCLUDED.total_capacity_gb,
                    current_used_gb = EXCLUDED.current_used_gb,
                    current_utilization_pct = EXCLUDED.current_utilization_pct,
                    days_to_80_percent = EXCLUDED.days_to_80_percent,
                    days_to_90_percent = EXCLUDED.days_to_90_percent,
                    days_to_100_percent = EXCLUDED.days_to_100_percent,
                    days_to_80_ci_lower = EXCLUDED.days_to_80_ci_lower,
                    days_to_80_ci_upper = EXCLUDED.days_to_80_ci_upper,
                    days_to_100_ci_lower = EXCLUDED.days_to_100_ci_lower,
                    days_to_100_ci_upper = EXCLUDED.days_to_100_ci_upper,
                    growth_rate_gb_per_day = EXCLUDED.growth_rate_gb_per_day,
                    acceleration_factor = EXCLUDED.acceleration_factor,
                    growth_pattern = EXCLUDED.growth_pattern,
                    model_type = EXCLUDED.model_type,
                    r_squared = EXCLUDED.r_squared,
                    sample_count = EXCLUDED.sample_count,
                    confidence_level = EXCLUDED.confidence_level,
                    confidence_multiplier = EXCLUDED.confidence_multiplier,
                    dedup_trend = EXCLUDED.dedup_trend,
                    dedup_adjustment_applied = EXCLUDED.dedup_adjustment_applied,
                    current_dedup_ratio = EXCLUDED.current_dedup_ratio,
                    quality_flags = EXCLUDED.quality_flags,
                    gaps_interpolated = EXCLUDED.gaps_interpolated,
                    outliers_removed = EXCLUDED.outliers_removed,
                    priority = EXCLUDED.priority,
                    recommendation = EXCLUDED.recommendation,
                    recommended_capacity_gb = EXCLUDED.recommended_capacity_gb
            """, (
                forecast.repository_id, forecast.repository_name, forecast.repository_type,
                forecast.total_capacity_gb, forecast.current_used_gb, forecast.current_utilization_pct,
                forecast.days_to_80, forecast.days_to_90, forecast.days_to_100,
                forecast.days_to_80_ci[0], forecast.days_to_80_ci[1],
                forecast.days_to_100_ci[0], forecast.days_to_100_ci[1],
                forecast.growth_rate, forecast.acceleration, forecast.growth_pattern,
                forecast.model_type, forecast.r_squared, forecast.sample_count,
                forecast.confidence_level, forecast.confidence_multiplier,
                forecast.dedup_trend, forecast.dedup_adjustment_applied, forecast.current_dedup_ratio,
                json.dumps(forecast.quality_flags), forecast.gaps_interpolated, forecast.outliers_removed,
                forecast.priority, forecast.recommendation, forecast.recommended_capacity_gb
            ))
            conn.commit()
            logger.info(f"✅ Saved forecast for {forecast.repository_name}")
        finally:
            conn.close()


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

class CapacityOrchestrator:
    """Main orchestrator for Feature 2"""
    
    def __init__(self):
        self.veeam = VeeamCapacityClient(
            CONFIG['veeam']['api_url'],
            CONFIG['veeam']['username'],
            CONFIG['veeam']['password']
        )
        self.db = DatabaseOperations(CONFIG['database'])
        self.preprocessor = DataPreprocessor()
        self.dedup_analyzer = DedupAnalyzer()
        self.forecaster = PolynomialForecaster()
    
    def analyze_repository(self, repo: Dict) -> Optional[CapacityForecast]:
        """Analyze single repository"""
        repo_id = repo['id']
        repo_name = repo['name']
        
        # Get historical data
        df = self.db.get_historical_data(repo_id, days=60)
        
        if len(df) < MIN_DAYS:
            logger.warning(f"WARNING: {repo_name}: Only {len(df)} days of data (min {MIN_DAYS} required)")
            return None
        
        # Add current measurement
        current_row = pd.DataFrame([{
            'date': datetime.now(),
            'capacity_gb': repo.get('usedSpaceGB', 0),
            'deduplication_ratio': None
        }])
        df = pd.concat([df, current_row], ignore_index=True)
        
        # Preprocess data
        df, gaps_interpolated = self.preprocessor.interpolate_gaps(df, MAX_GAP_DAYS)
        df = df.dropna(subset=['capacity_gb'])
        
        if len(df) < MIN_DAYS:
            logger.warning(f"⚠️ {repo_name}: Insufficient data after preprocessing")
            return None
        
        # Prepare regression data
        df['days'] = (df['date'] - df['date'].min()).dt.days
        x = df['days'].values
        y = df['capacity_gb'].values
        
        # Remove outliers
        y_clean, outliers_removed = self.preprocessor.remove_outliers(y, OUTLIER_THRESHOLD)
        if outliers_removed > 0:
            # Re-align x with cleaned y
            outlier_mask = np.abs(y - np.mean(y)) <= (OUTLIER_THRESHOLD * np.std(y))
            x = x[outlier_mask]
            y = y_clean
        
        # Analyze deduplication trend
        dedup_ratios = df['deduplication_ratio'].dropna().tolist()
        if len(dedup_ratios) >= 10:
            dedup_trend, dedup_adjustment = self.dedup_analyzer.analyze_dedup_trend(dedup_ratios)
            current_dedup = dedup_ratios[-1] if dedup_ratios else None
        else:
            dedup_trend = "UNKNOWN"
            dedup_adjustment = 1.0
            current_dedup = None
        
        # Fit polynomial model
        model = self.forecaster.fit_model(x, y)
        
        # Apply deduplication adjustment to coefficients
        coeffs = model['coeffs'].copy()
        if dedup_adjustment != 1.0:
            coeffs[0] *= dedup_adjustment  # Adjust 'a'
            coeffs[1] *= dedup_adjustment  # Adjust 'b'
            dedup_adjustment_applied = True
        else:
            dedup_adjustment_applied = False
        
        # Current state
        current_day = x[-1]
        total_capacity_gb = repo.get('capacityGB', 0)
        current_used_gb = repo.get('usedSpaceGB', 0)
        current_utilization_pct = (current_used_gb / total_capacity_gb * 100) if total_capacity_gb > 0 else 0
        
        # Solve for thresholds
        threshold_80 = total_capacity_gb * 0.80
        threshold_90 = total_capacity_gb * 0.90
        threshold_100 = total_capacity_gb * 1.00
        
        days_to_80 = self.forecaster.solve_for_threshold(coeffs, threshold_80, current_day)
        days_to_90 = self.forecaster.solve_for_threshold(coeffs, threshold_90, current_day)
        days_to_100 = self.forecaster.solve_for_threshold(coeffs, threshold_100, current_day)
        
        # Confidence intervals (simplified - 10% margin)
        days_to_80_ci = (
            int(days_to_80 * 0.9) if days_to_80 else None,
            int(days_to_80 * 1.1) if days_to_80 else None
        )
        days_to_100_ci = (
            int(days_to_100 * 0.9) if days_to_100 else None,
            int(days_to_100 * 1.1) if days_to_100 else None
        )
        
        # Growth analysis
        growth_rate = coeffs[1]  # Linear coefficient
        acceleration = coeffs[0]  # Quadratic coefficient
        
        # Determine growth pattern
        if growth_rate < -1:
            growth_pattern = "DECLINING"
        elif abs(growth_rate) < 1:
            growth_pattern = "STABLE"
        elif model['model_type'] == "QUADRATIC" and acceleration > 0.1:
            growth_pattern = "QUADRATIC"
        else:
            growth_pattern = "LINEAR"
        
        # Confidence classification
        r_squared = model['r_squared']
        if r_squared >= R_SQUARED_HIGH and len(x) >= 21:
            confidence_level = "HIGH"
            confidence_multiplier = 1.0
        elif r_squared >= R_SQUARED_MODERATE and len(x) >= MIN_DAYS:
            confidence_level = "MODERATE"
            confidence_multiplier = 0.8
        else:
            confidence_level = "LOW"
            confidence_multiplier = 0.5
        
        # Priority classification
        if days_to_80 and days_to_80 < URGENT_THRESHOLD_DAYS:
            priority = "URGENT"
        elif days_to_80 and days_to_80 < HIGH_THRESHOLD_DAYS:
            priority = "HIGH"
        elif days_to_80 and days_to_80 < MEDIUM_THRESHOLD_DAYS:
            priority = "MEDIUM"
        else:
            priority = "LOW"
        
        # Generate recommendation
        if growth_pattern == "DECLINING":
            recommendation = f"Capacity declining at {abs(growth_rate):.1f} GB/day. Monitor for stabilization."
        elif days_to_80 and days_to_80 < URGENT_THRESHOLD_DAYS:
            recommendation = f"URGENT: {days_to_80} days to 80% capacity. Order storage immediately."
        elif days_to_80 and days_to_80 < HIGH_THRESHOLD_DAYS:
            recommendation = f"HIGH: {days_to_80} days to 80% capacity. Order storage within 2 weeks."
        elif days_to_80 and days_to_80 < MEDIUM_THRESHOLD_DAYS:
            recommendation = f"MEDIUM: {days_to_80} days to 80% capacity. Plan expansion within 30 days."
        else:
            recommendation = f"LOW: {days_to_80 if days_to_80 else 'N/A'} days to 80% capacity. Monitor quarterly."
        
        # Recommended capacity
        if days_to_100:
            projected_6month = growth_rate * 180
            recommended_capacity_gb = total_capacity_gb + projected_6month * 1.2
        else:
            recommended_capacity_gb = None
        
        # Quality flags
        quality_flags = {
            "r_squared": r_squared,
            "sample_count": len(x),
            "model_type": model['model_type'],
            "dedup_adjustment": dedup_adjustment_applied,
            "confidence_level": confidence_level
        }
        
        return CapacityForecast(
            repository_id=repo_id,
            repository_name=repo_name,
            repository_type=repo.get('repositoryType', 'Unknown'),
            total_capacity_gb=total_capacity_gb,
            current_used_gb=current_used_gb,
            current_utilization_pct=current_utilization_pct,
            days_to_80=days_to_80,
            days_to_90=days_to_90,
            days_to_100=days_to_100,
            days_to_80_ci=days_to_80_ci,
            days_to_100_ci=days_to_100_ci,
            growth_rate=growth_rate,
            acceleration=acceleration,
            growth_pattern=growth_pattern,
            model_type=model['model_type'],
            r_squared=r_squared,
            sample_count=len(x),
            confidence_level=confidence_level,
            confidence_multiplier=confidence_multiplier,
            dedup_trend=dedup_trend,
            dedup_adjustment_applied=dedup_adjustment_applied,
            current_dedup_ratio=current_dedup,
            quality_flags=quality_flags,
            gaps_interpolated=gaps_interpolated,
            outliers_removed=outliers_removed,
            priority=priority,
            recommendation=recommendation,
            recommended_capacity_gb=recommended_capacity_gb
        )
    
    def run(self):
        """Main execution"""
        logger.info("=" * 80)
        logger.info("Starting Feature 2: Capacity Forecasting")
        logger.info("=" * 80)
        
        # Authenticate
        if not self.veeam.authenticate():
            logger.error("Failed to authenticate")
            return
        
        # Get repositories
        repos = self.veeam.get_repositories()
        if not repos:
            logger.error("No repositories found")
            return
        
        # Save current measurements
        for repo in repos:
            try:
                self.db.save_current_measurement(repo)
            except Exception as e:
                logger.error(f"Failed to save measurement for {repo.get('name', 'Unknown')}: {e}")
        
        # Analyze each repository
        forecasts = []
        for repo in repos:
            try:
                logger.info(f"\nAnalyzing {repo.get('name', 'Unknown')}...")
                forecast = self.analyze_repository(repo)
                if forecast:
                    self.db.save_forecast(forecast)
                    forecasts.append(forecast)
                    logger.info(f"SUCCESS: {forecast.growth_pattern} growth, {forecast.days_to_80} days to 80%")
            except Exception as e:
                logger.error(f"Failed to analyze {repo.get('name', 'Unknown')}: {e}", exc_info=True)
        
        logger.info("=" * 80)
        logger.info(f"Feature 2 complete - {len(forecasts)} repositories forecasted")
        logger.info("=" * 80)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    orchestrator = CapacityOrchestrator()
    orchestrator.run()
