#!/usr/bin/env python3
"""
Feature 3: Storage Efficiency Analysis - HYBRID IMPLEMENTATION
Production-ready implementation with PowerShell integration for efficiency data

NEW DOCS Compliance:
- Feature 03 Storage Efficiency Implementation Guide Final.md
- FEATURE_3_EXACT_SPECIFICATIONS.md
- Comprehensive Technical Analysis Report

HYBRID APPROACH:
- PowerShell: Retrieves dedupeRatio/compressionRatio (not available in REST API)
- Python: Performs all analysis, scoring, and database persistence

Key Capabilities:
- Deduplication effectiveness scoring (EXCELLENT/GOOD/FAIR/POOR)
- Compression ratio analysis and trends
- Storage waste identification and optimization potential
- Anomaly detection (3-sigma method)
- Efficiency trend analysis (IMPROVING/STABLE/DEGRADING)
- Per-job efficiency rankings
- Quality metadata for Feature 5 integration
"""

import subprocess
import json
import os
import sys
import psycopg2
import numpy as np
from scipy import stats
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import logging
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

def load_config(config_path: str = None) -> Dict:
    """Load configuration from YAML file"""
    if config_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "config.yaml")
    
    config = {}
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning(f"Config file {config_path} not found, using defaults")
        config = {
            'database': {
                'host': 'localhost',
                'port': 5432,
                'database': 'dr365v_metrics',
                'user': 'postgres',
                'password': 'admin'
            },
            'feature3': {
                'min_sessions': 30,
                'dedup_excellent': 3.5,
                'dedup_good': 2.5,
                'dedup_fair': 1.5,
                'compression_excellent': 2.0,
                'compression_good': 1.8,
                'compression_fair': 1.3,
                'anomaly_threshold_sigma': 3.0,
                'trend_pvalue_threshold': 0.05,
                'component_weights': {
                    'dedup': 0.30,
                    'compression': 0.25,
                    'trend': 0.20,
                    'consistency': 0.15,
                    'anomaly': 0.10
                },
                'target_dedup_ratio': 2.5,
                'target_compression_ratio': 1.8,
                'storage_cost_per_tb_year': 100,
                'powershell_script': 'get_efficiency_data.ps1',
                'days_back': 30
            }
        }
        
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

    # Explicitly return the modified config
    return config


CONFIG = load_config()

# Extract configuration values
MIN_SESSIONS = CONFIG['feature3']['min_sessions']
DEDUP_EXCELLENT = CONFIG['feature3']['dedup_excellent']
DEDUP_GOOD = CONFIG['feature3']['dedup_good']
DEDUP_FAIR = CONFIG['feature3']['dedup_fair']
COMPRESSION_EXCELLENT = CONFIG['feature3']['compression_excellent']
COMPRESSION_GOOD = CONFIG['feature3']['compression_good']
COMPRESSION_FAIR = CONFIG['feature3']['compression_fair']
ANOMALY_SIGMA = CONFIG['feature3']['anomaly_threshold_sigma']
TREND_PVALUE = CONFIG['feature3']['trend_pvalue_threshold']
WEIGHTS = CONFIG['feature3']['component_weights']
TARGET_DEDUP = CONFIG['feature3']['target_dedup_ratio']
TARGET_COMPRESSION = CONFIG['feature3']['target_compression_ratio']
STORAGE_COST = CONFIG['feature3']['storage_cost_per_tb_year']


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class EfficiencyScore:
    """Complete efficiency analysis results"""
    job_id: str
    job_name: str
    job_type: str
    overall_score: float
    efficiency_grade: str
    efficiency_rating: str
    
    # Deduplication metrics
    avg_dedup_ratio: float
    dedup_score: float
    dedup_rating: str
    dedup_consistency: float
    dedup_std_dev: float
    
    # Compression metrics
    avg_compression_ratio: float
    compression_score: float
    compression_rating: str
    compression_consistency: float
    compression_std_dev: float
    
    # Combined efficiency
    combined_ratio: float
    storage_reduction_pct: float
    
    # Trend analysis
    trend_classification: str
    trend_score: float
    trend_percentage: float
    trend_pvalue: float
    
    # Anomaly detection
    anomalies_detected: int
    anomaly_score: float
    critical_anomalies: bool
    
    # Consistency
    consistency_score: float
    
    # Optimization potential
    optimization_potential_gb: float
    projected_monthly_savings_gb: float
    estimated_cost_savings_annual: float
    
    # Recommendations
    priority: str
    recommendation: str
    
    # Quality metadata
    sample_count: int
    confidence_level: str
    quality_flags: Dict = field(default_factory=dict)


# =============================================================================
# POWERSHELL DATA COLLECTOR
# =============================================================================

class PowerShellEfficiencyCollector:
    """Collects efficiency data using Veeam PowerShell module"""
    
    def __init__(self, script_path: str, days_back: int = 30):
        self.script_path = script_path
        self.days_back = days_back
        self.output_file = "efficiency_data.json"
    
    def collect_data(self) -> List[Dict]:
        """
        Execute PowerShell script to collect efficiency data
        
        Returns:
            List of session dictionaries with efficiency metrics
        """
        logger.info("=" * 80)
        logger.info("🔧 Collecting efficiency data via PowerShell")
        logger.info("=" * 80)
        
        # Verify PowerShell script exists
        if not os.path.exists(self.script_path):
            logger.error(f"❌ PowerShell script not found: {self.script_path}")
            return []
        
        # Build command using batch wrapper
        batch_file = os.path.join(os.path.dirname(self.script_path), "run_efficiency_collection.bat")
        
        if not os.path.exists(batch_file):
            logger.error(f"❌ Batch wrapper not found: {batch_file}")
            return []
        
        ps_command = [
            batch_file,
            str(self.days_back),
            self.output_file
        ]
        
        try:
            # Execute PowerShell script
            logger.info(f"Executing: {' '.join(ps_command)}")
            result = subprocess.run(
                ps_command,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            # Log PowerShell output
            if result.stdout:
                for line in result.stdout.splitlines():
                    logger.info(f"  PS: {line}")
            
            if result.stderr:
                for line in result.stderr.splitlines():
                    logger.warning(f"  PS ERROR: {line}")
            
            if result.returncode != 0:
                logger.error(f"❌ PowerShell script failed with exit code {result.returncode}")
                return []
            
            # Read JSON output
            json_path = os.path.join(os.path.dirname(self.script_path), self.output_file)
            if not os.path.exists(json_path):
                logger.error(f"❌ PowerShell script didn't create output file: {json_path}")
                return []
            
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"✅ Collected {len(data)} sessions with efficiency data")
            
            # Clean up output file
            try:
                os.remove(json_path)
            except:
                pass
            
            return data
            
        except subprocess.TimeoutExpired:
            logger.error("❌ PowerShell script timed out after 5 minutes")
            return []
        except Exception as e:
            logger.error(f"❌ Failed to execute PowerShell script: {e}")
            return []


# =============================================================================
# EFFICIENCY ANALYZER (Same as before - no changes needed)
# =============================================================================

class EfficiencyAnalyzer:
    """Core efficiency analysis engine"""
    
    def __init__(self):
        """Initialize with efficiency thresholds from config"""
        self.dedup_thresholds = {
            'excellent': DEDUP_EXCELLENT,
            'good': DEDUP_GOOD,
            'fair': DEDUP_FAIR
        }
        self.compression_thresholds = {
            'excellent': COMPRESSION_EXCELLENT,
            'good': COMPRESSION_GOOD,
            'fair': COMPRESSION_FAIR
        }
    
    def calculate_dedup_score(self, avg_dedup: float) -> Tuple[float, str]:
        """Calculate deduplication score (0-100) and rating"""
        if avg_dedup >= self.dedup_thresholds['excellent']:
            score = 90 + min(10, (avg_dedup - self.dedup_thresholds['excellent']) * 2)
            rating = "EXCELLENT"
        elif avg_dedup >= self.dedup_thresholds['good']:
            score = 75 + ((avg_dedup - self.dedup_thresholds['good']) / 
                         (self.dedup_thresholds['excellent'] - self.dedup_thresholds['good']) * 15)
            rating = "GOOD"
        elif avg_dedup >= self.dedup_thresholds['fair']:
            score = 50 + ((avg_dedup - self.dedup_thresholds['fair']) / 
                         (self.dedup_thresholds['good'] - self.dedup_thresholds['fair']) * 25)
            rating = "FAIR"
        else:
            score = min(50, (avg_dedup / self.dedup_thresholds['fair']) * 50)
            rating = "POOR"
        
        return round(score, 2), rating
    
    def calculate_compression_score(self, avg_compression: float) -> Tuple[float, str]:
        """Calculate compression score (0-100) and rating"""
        if avg_compression >= self.compression_thresholds['excellent']:
            score = 90 + min(10, (avg_compression - self.compression_thresholds['excellent']) * 5)
            rating = "EXCELLENT"
        elif avg_compression >= self.compression_thresholds['good']:
            score = 75 + ((avg_compression - self.compression_thresholds['good']) / 
                         (self.compression_thresholds['excellent'] - self.compression_thresholds['good']) * 15)
            rating = "GOOD"
        elif avg_compression >= self.compression_thresholds['fair']:
            score = 50 + ((avg_compression - self.compression_thresholds['fair']) / 
                         (self.compression_thresholds['good'] - self.compression_thresholds['fair']) * 25)
            rating = "FAIR"
        else:
            score = min(50, (avg_compression / self.compression_thresholds['fair']) * 50)
            rating = "POOR"
        
        return round(score, 2), rating
    
    def detect_anomalies(self, ratios: List[float], threshold: float = ANOMALY_SIGMA) -> Tuple[List[int], int, bool]:
        """Detect statistical anomalies using z-score method"""
        if len(ratios) < 5:
            return [], 0, False
        
        mean = np.mean(ratios)
        std = np.std(ratios)
        
        if std == 0:
            return [], 0, False
        
        z_scores = [(r - mean) / std for r in ratios]
        anomalies = [i for i, z in enumerate(z_scores) if abs(z) > threshold]
        
        # Check for critical anomalies (>20% drop from mean)
        critical = any(ratios[i] < mean * 0.8 for i in anomalies)
        
        return anomalies, len(anomalies), critical
    
    def analyze_trend(self, ratios: List[float]) -> Tuple[str, float, float]:
        """Analyze trend: IMPROVING/STABLE/DEGRADING"""
        if len(ratios) < 10:
            return "UNKNOWN", 0.0, 1.0
        
        # Split into first half and second half
        mid = len(ratios) // 2
        first_half = ratios[:mid]
        second_half = ratios[mid:]
        
        first_avg = np.mean(first_half)
        second_avg = np.mean(second_half)
        
        # Calculate percentage change
        if first_avg > 0:
            pct_change = ((second_avg - first_avg) / first_avg) * 100
        else:
            pct_change = 0.0
        
        # Statistical significance test
        try:
            t_stat, p_value = stats.ttest_ind(first_half, second_half)
        except:
            p_value = 1.0
        
        # Classify trend
        if p_value < TREND_PVALUE:
            if pct_change > 5:
                classification = "IMPROVING"
            elif pct_change < -5:
                classification = "DEGRADING"
            else:
                classification = "STABLE"
        else:
            classification = "STABLE"
        
        return classification, round(pct_change, 2), round(p_value, 4)
    
    def calculate_consistency_score(self, ratios: List[float]) -> float:
        """Calculate consistency score based on coefficient of variation"""
        if len(ratios) < 2:
            return 50.0
        
        mean = np.mean(ratios)
        std = np.std(ratios)
        
        # Coefficient of variation
        cv = (std / mean) if mean > 0 else 1.0
        
        # Convert to score (0-100)
        score = max(0, min(100, 100 - (cv * 200)))
        
        return round(score, 2)
    
    def calculate_trend_score(self, classification: str, pct_change: float) -> float:
        """Calculate trend score based on classification"""
        if classification == "IMPROVING":
            score = 85 + min(15, abs(pct_change) / 2)
        elif classification == "STABLE":
            score = 70 + max(0, 15 - abs(pct_change))
        else:  # DEGRADING
            score = max(0, 70 - abs(pct_change) * 2)
        
        return round(score, 2)
    
    def calculate_anomaly_score(self, anomaly_count: int, total_count: int) -> float:
        """Calculate anomaly score - fewer anomalies = higher score"""
        if total_count == 0:
            return 50.0
        
        anomaly_rate = anomaly_count / total_count
        
        if anomaly_rate == 0:
            score = 100
        elif anomaly_rate < 0.10:
            score = 75 + (1 - anomaly_rate * 10) * 25
        elif anomaly_rate < 0.20:
            score = 75 - (anomaly_rate - 0.10) * 750
        else:
            score = 0
        
        return round(score, 2)
    
    def calculate_optimization_potential(self, 
                                        current_dedup: float,
                                        current_compression: float,
                                        raw_data_gb_per_day: float) -> Tuple[float, float, float]:
        """Calculate potential GB savings from optimization"""
        # Current storage per day
        current_storage = raw_data_gb_per_day / (current_dedup * current_compression)
        
        # Potential storage with optimized ratios
        target_storage = raw_data_gb_per_day / (TARGET_DEDUP * TARGET_COMPRESSION)
        
        # Optimization potential
        potential_per_day = max(0, current_storage - target_storage)
        monthly_savings = potential_per_day * 30
        
        # Annual cost savings
        annual_savings = (monthly_savings * 12 / 1024) * STORAGE_COST
        
        return round(potential_per_day, 2), round(monthly_savings, 2), round(annual_savings, 2)


# =============================================================================
# DATABASE WRITER
# =============================================================================

class DatabaseWriter:
    """Handles database persistence"""
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
    
    def write_efficiency_scores(self, scores: List[EfficiencyScore], 
                                history_data: List[Dict]):
        """Write efficiency scores and historical data to database"""
        conn = psycopg2.connect(**self.db_config)
        try:
            cur = conn.cursor()
            
            # Write efficiency scores
            for score in scores:
                # UPSERT: Use ON CONFLICT instead of DELETE+INSERT
                
                cur.execute("""
                    INSERT INTO feature3.metrics_storage_efficiency (
                        created_at, job_id, job_name, job_type,
                        overall_score, efficiency_grade, efficiency_rating,
                        avg_dedup_ratio, dedup_score, dedup_rating, dedup_consistency,
                        avg_compression_ratio, compression_score, compression_rating, compression_consistency,
                        combined_ratio, storage_reduction_pct,
                        trend_classification, trend_score, trend_percentage,
                        anomalies_detected, anomaly_score, critical_anomalies,
                        consistency_score, dedup_std_dev, compression_std_dev,
                        optimization_potential_gb, projected_monthly_savings_gb, estimated_cost_savings_annual,
                        priority, recommendation,
                        sample_count, confidence_level, quality_flags
                    ) VALUES (
                        NOW(), %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s, %s
                    )
                    ON CONFLICT (job_id, created_date) DO UPDATE SET
                        created_at = NOW(),
                        job_name = EXCLUDED.job_name,
                        job_type = EXCLUDED.job_type,
                        overall_score = EXCLUDED.overall_score,
                        efficiency_grade = EXCLUDED.efficiency_grade,
                        efficiency_rating = EXCLUDED.efficiency_rating,
                        avg_dedup_ratio = EXCLUDED.avg_dedup_ratio,
                        dedup_score = EXCLUDED.dedup_score,
                        dedup_rating = EXCLUDED.dedup_rating,
                        dedup_consistency = EXCLUDED.dedup_consistency,
                        avg_compression_ratio = EXCLUDED.avg_compression_ratio,
                        compression_score = EXCLUDED.compression_score,
                        compression_rating = EXCLUDED.compression_rating,
                        compression_consistency = EXCLUDED.compression_consistency,
                        combined_ratio = EXCLUDED.combined_ratio,
                        storage_reduction_pct = EXCLUDED.storage_reduction_pct,
                        trend_classification = EXCLUDED.trend_classification,
                        trend_score = EXCLUDED.trend_score,
                        trend_percentage = EXCLUDED.trend_percentage,
                        anomalies_detected = EXCLUDED.anomalies_detected,
                        anomaly_score = EXCLUDED.anomaly_score,
                        critical_anomalies = EXCLUDED.critical_anomalies,
                        consistency_score = EXCLUDED.consistency_score,
                        dedup_std_dev = EXCLUDED.dedup_std_dev,
                        compression_std_dev = EXCLUDED.compression_std_dev,
                        optimization_potential_gb = EXCLUDED.optimization_potential_gb,
                        projected_monthly_savings_gb = EXCLUDED.projected_monthly_savings_gb,
                        estimated_cost_savings_annual = EXCLUDED.estimated_cost_savings_annual,
                        priority = EXCLUDED.priority,
                        recommendation = EXCLUDED.recommendation,
                        sample_count = EXCLUDED.sample_count,
                        confidence_level = EXCLUDED.confidence_level,
                        quality_flags = EXCLUDED.quality_flags
                """, (
                    score.job_id, score.job_name, score.job_type,
                    float(score.overall_score), score.efficiency_grade, score.efficiency_rating,
                    float(score.avg_dedup_ratio), float(score.dedup_score), score.dedup_rating, float(score.dedup_consistency),
                    float(score.avg_compression_ratio), float(score.compression_score), score.compression_rating, float(score.compression_consistency),
                    float(score.combined_ratio), float(score.storage_reduction_pct),
                    score.trend_classification, float(score.trend_score), float(score.trend_percentage),
                    score.anomalies_detected, float(score.anomaly_score), score.critical_anomalies,
                    float(score.consistency_score), float(score.dedup_std_dev), float(score.compression_std_dev),
                    float(score.optimization_potential_gb), float(score.projected_monthly_savings_gb), float(score.estimated_cost_savings_annual),
                    score.priority, score.recommendation,
                    score.sample_count, score.confidence_level, json.dumps(score.quality_flags)
                ))
            
            # Write historical data
            for record in history_data:
                # Use database constraint to prevent duplicates
                cur.execute("""
                    INSERT INTO feature3.storage_efficiency_history (
                        created_at, job_id, job_name,
                        dedup_ratio, compression_ratio, combined_ratio,
                        session_id, backup_size_gb, stored_size_gb,
                        is_anomaly, is_interpolated
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s
                    ) ON CONFLICT (session_id) DO NOTHING
                """, (
                    record['created_at'], record['job_id'], record['job_name'],
                    record['dedup_ratio'], record['compression_ratio'], record['combined_ratio'],
                    record.get('session_id'), record.get('backup_size_gb'), record.get('stored_size_gb'),
                    record.get('is_anomaly', False), record.get('is_interpolated', False)
                ))
            
            conn.commit()
            logger.info(f"✅ Wrote {len(scores)} efficiency scores and {len(history_data)} historical records to database")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Database write failed: {e}")
            raise
        finally:
            conn.close()


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main execution function"""
    logger.info("=" * 80)
    logger.info("🚀 Starting Feature 3: Storage Efficiency Analysis (HYBRID MODE)")
    logger.info("=" * 80)
    
    # Initialize components
    db_config = CONFIG['database']
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ps_script_path = os.path.join(script_dir, CONFIG['feature3']['powershell_script'])
    days_back = CONFIG['feature3']['days_back']

    # [DEBUG] Verify DB Config
    logger.info(f"Database Config: Host={db_config.get('host')}, User={db_config.get('user')}, DB={db_config.get('database')}")
    
    # Step 1: Collect efficiency data via PowerShell
    collector = PowerShellEfficiencyCollector(ps_script_path, days_back)
    sessions = collector.collect_data()
    
    if not sessions:
        logger.error("❌ No efficiency data collected from PowerShell")
        logger.info("Please verify:")
        logger.info("  1. Veeam PowerShell module is installed")
        logger.info("  2. You have permissions to run Get-VBRBackupSession")
        logger.info("  3. Backup sessions exist in the specified date range")
        return
    
    # Step 2: Group sessions by job
    jobs_sessions = {}
    for session in sessions:
        job_id = session.get('JobId')
        if job_id:
            if job_id not in jobs_sessions:
                jobs_sessions[job_id] = []
            jobs_sessions[job_id].append(session)
    
    logger.info(f"📊 Analyzing {len(jobs_sessions)} jobs")
    
    # Step 3: Analyze each job
    analyzer = EfficiencyAnalyzer()
    db_writer = DatabaseWriter(db_config)
    
    efficiency_scores = []
    history_data = []
    
    for job_id, job_sessions in jobs_sessions.items():
        if len(job_sessions) < MIN_SESSIONS:
            logger.warning(f"⚠️ Job {job_id}: Only {len(job_sessions)} sessions (min {MIN_SESSIONS} required), skipping")
            continue
        
        # Extract job metadata
        job_name = job_sessions[0].get('JobName', 'Unknown Job')
        job_type = job_sessions[0].get('JobType', 'Unknown')
        
        logger.info(f"\n📈 Analyzing job: {job_name} ({len(job_sessions)} sessions)")
        
        # Extract ratios
        dedup_ratios = []
        compression_ratios = []
        combined_ratios = []
        
        for session in job_sessions:
            dedup = session.get('DedupeRatio')
            compression = session.get('CompressionRatio')
            
            if dedup and compression:
                # Validate ranges with warning thresholds
                # Spec's "reasonable range": 1.0-50.0x dedup, 1.0-20.0x compression
                # Hard limits: reject truly invalid data (lab can have extreme values)
                if dedup < 1.0 or dedup > 200.0:
                    logger.warning(f"   Skipping session: invalid dedup {dedup}x (must be 1.0-200.0)")
                    continue
                if compression < 1.0 or compression > 10000.0:
                    logger.warning(f"   Skipping session: invalid compression {compression}x (must be 1.0-10000.0)")
                    continue
                
                # Accept all valid values (warnings logged separately)
                dedup_ratios.append(dedup)
                compression_ratios.append(compression)
                combined_ratios.append(dedup * compression)
                
                # Store historical data
                history_data.append({
                    'created_at': session.get('CreationTime'),
                    'job_id': job_id,
                    'job_name': job_name,
                    'dedup_ratio': dedup,
                    'compression_ratio': compression,
                    'combined_ratio': dedup * compression,
                    'session_id': session.get('SessionId'),
                    'backup_size_gb': session.get('BackupSizeGB', 0),
                    'stored_size_gb': session.get('TransferredSizeGB', 0)
                })
        
        if len(dedup_ratios) < MIN_SESSIONS:
            logger.warning(f"⚠️ Job {job_name}: Insufficient valid data after filtering")
            continue
        
        # Calculate averages
        avg_dedup = np.mean(dedup_ratios)
        avg_compression = np.mean(compression_ratios)
        avg_combined = np.mean(combined_ratios)
        dedup_std = np.std(dedup_ratios)
        compression_std = np.std(compression_ratios)
        
        # Check for extreme values (outside spec's "reasonable range")
        extreme_efficiency = False
        if avg_dedup > 50.0 or avg_compression > 20.0:
            logger.warning(f"⚠️ Job {job_name}: Extreme efficiency detected")
            logger.warning(f"   Dedup: {avg_dedup:.2f}x (reasonable range: ≤50x)")
            logger.warning(f"   Compression: {avg_compression:.2f}x (reasonable range: ≤20x)")
            logger.warning(f"   This may indicate lab/test environment")
            extreme_efficiency = True
        
        # Calculate scores
        dedup_score, dedup_rating = analyzer.calculate_dedup_score(avg_dedup)
        compression_score, compression_rating = analyzer.calculate_compression_score(avg_compression)
        
        # Detect anomalies
        dedup_anomalies, dedup_anomaly_count, dedup_critical = analyzer.detect_anomalies(dedup_ratios)
        compression_anomalies, compression_anomaly_count, compression_critical = analyzer.detect_anomalies(compression_ratios)
        total_anomalies = dedup_anomaly_count + compression_anomaly_count
        critical_anomalies = dedup_critical or compression_critical
        
        # Analyze trends
        dedup_trend, dedup_pct, dedup_pvalue = analyzer.analyze_trend(dedup_ratios)
        trend_classification = dedup_trend
        trend_percentage = dedup_pct
        trend_pvalue = dedup_pvalue
        
        # Calculate component scores
        trend_score = analyzer.calculate_trend_score(trend_classification, trend_percentage)
        consistency_score = analyzer.calculate_consistency_score(combined_ratios)
        anomaly_score = analyzer.calculate_anomaly_score(total_anomalies, len(dedup_ratios))
        dedup_consistency = analyzer.calculate_consistency_score(dedup_ratios)
        compression_consistency = analyzer.calculate_consistency_score(compression_ratios)
        
        # Calculate overall score (weighted average)
        overall_score = (
            dedup_score * WEIGHTS['dedup'] +
            compression_score * WEIGHTS['compression'] +
            trend_score * WEIGHTS['trend'] +
            consistency_score * WEIGHTS['consistency'] +
            anomaly_score * WEIGHTS['anomaly']
        )
        
        # Assign grade
        if overall_score >= 85:
            grade = "A"
            efficiency_rating = "EXCELLENT"
        elif overall_score >= 70:
            grade = "B"
            efficiency_rating = "GOOD"
        elif overall_score >= 55:
            grade = "C"
            efficiency_rating = "FAIR"
        elif overall_score >= 40:
            grade = "D"
            efficiency_rating = "POOR"
        else:
            grade = "F"
            efficiency_rating = "CRITICAL"
        
        # Calculate optimization potential
        avg_backup_size = np.mean([s.get('BackupSizeGB', 0) for s in job_sessions if s.get('BackupSizeGB')])
        opt_potential, monthly_savings, annual_cost = analyzer.calculate_optimization_potential(
            avg_dedup, avg_compression, avg_backup_size
        )
        
        # Determine priority
        if overall_score < 40 or critical_anomalies:
            priority = "CRITICAL"
        elif overall_score < 55 or trend_classification == "DEGRADING":
            priority = "HIGH"
        elif overall_score < 70:
            priority = "MEDIUM"
        else:
            priority = "LOW"
        
        # Generate recommendation
        if efficiency_rating == "EXCELLENT":
            recommendation = f"✅ Excellent efficiency ({avg_combined:.1f}x combined ratio). Maintain current configuration."
        elif efficiency_rating == "GOOD":
            recommendation = f"✅ Good efficiency ({avg_combined:.1f}x combined ratio). Minor optimization possible."
        elif efficiency_rating == "FAIR":
            recommendation = f"⚠️ Fair efficiency ({avg_combined:.1f}x combined ratio). Review dedup/compression settings. Potential savings: {monthly_savings:.0f} GB/month."
        else:
            recommendation = f"🔴 Poor efficiency ({avg_combined:.1f}x combined ratio). Immediate review required. Potential savings: {monthly_savings:.0f} GB/month (${annual_cost:.0f}/year)."
        
        # Determine confidence level
        if len(dedup_ratios) >= 60:
            confidence_level = "HIGH"
        elif len(dedup_ratios) >= MIN_SESSIONS:
            confidence_level = "MODERATE"
        else:
            confidence_level = "LOW"
        
        # Quality flags
        quality_flags = {}
        if critical_anomalies:
            quality_flags['CRITICAL_ANOMALIES'] = True
        if trend_classification == "DEGRADING":
            quality_flags['DEGRADING_TREND'] = True
        if dedup_std / avg_dedup > 0.3:
            quality_flags['HIGH_VARIANCE'] = True
        if extreme_efficiency:
            quality_flags['EXTREME_EFFICIENCY'] = True
            quality_flags['OUTSIDE_REASONABLE_RANGE'] = True
        
        # Create efficiency score object
        score = EfficiencyScore(
            job_id=job_id,
            job_name=job_name,
            job_type=job_type,
            overall_score=round(overall_score, 2),
            efficiency_grade=grade,
            efficiency_rating=efficiency_rating,
            avg_dedup_ratio=round(avg_dedup, 2),
            dedup_score=dedup_score,
            dedup_rating=dedup_rating,
            dedup_consistency=dedup_consistency,
            dedup_std_dev=round(dedup_std, 2),
            avg_compression_ratio=round(avg_compression, 2),
            compression_score=compression_score,
            compression_rating=compression_rating,
            compression_consistency=compression_consistency,
            compression_std_dev=round(compression_std, 2),
            combined_ratio=round(avg_combined, 2),
            storage_reduction_pct=round((1 - 1/avg_combined) * 100, 1),
            trend_classification=trend_classification,
            trend_score=trend_score,
            trend_percentage=trend_percentage,
            trend_pvalue=trend_pvalue,
            anomalies_detected=total_anomalies,
            anomaly_score=anomaly_score,
            critical_anomalies=critical_anomalies,
            consistency_score=consistency_score,
            optimization_potential_gb=opt_potential,
            projected_monthly_savings_gb=monthly_savings,
            estimated_cost_savings_annual=annual_cost,
            priority=priority,
            recommendation=recommendation,
            sample_count=len(dedup_ratios),
            confidence_level=confidence_level,
            quality_flags=quality_flags
        )
        
        efficiency_scores.append(score)
        
        # Log summary
        logger.info(f"  Overall Score: {overall_score:.1f}/100 (Grade {grade})")
        logger.info(f"  Dedup: {avg_dedup:.2f}x ({dedup_rating}), Compression: {avg_compression:.2f}x ({compression_rating})")
        logger.info(f"  Combined: {avg_combined:.2f}x = {score.storage_reduction_pct}% reduction")
        logger.info(f"  Trend: {trend_classification}, Anomalies: {total_anomalies}")
    
    # Step 4: Write to database
    if efficiency_scores:
        db_writer.write_efficiency_scores(efficiency_scores, history_data)
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ Feature 3 Analysis Complete")
        logger.info("=" * 80)
        logger.info(f"Jobs Analyzed: {len(efficiency_scores)}")
        logger.info(f"Historical Records: {len(history_data)}")
        logger.info(f"Average Efficiency: {np.mean([s.overall_score for s in efficiency_scores]):.1f}/100")
    else:
        logger.warning("⚠️ No efficiency scores generated")
    
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
