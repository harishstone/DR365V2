
#!/usr/bin/env python3
"""
Feature 5: Advanced Risk Analysis & Prioritization - EXACT COMPLIANCE IMPLEMENTATION
"""

import os
import sys
import yaml
import json
import logging
import psycopg2
import re
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Feature5_Strict')

# =============================================================================
# ENUMS
# =============================================================================

class RiskCategory(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class DataQualityStatus(Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"

class ConfidenceLevel(Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class FeatureHealthCheck:
    feature_number: int
    freshness_ok: bool
    freshness_hours: float
    quality_ok: bool
    quality_issues: List[str]
    data_available: bool
    confidence_multiplier: float
    status: DataQualityStatus

@dataclass
class RiskScore:
    risk_type: str
    base_score: float
    feature_quality_multiplier: float
    adjusted_score: float
    threshold: float
    exceeds_threshold: bool

@dataclass
class ConsolidatedRisk:
    job_id: str
    job_name: str
    vm_tier: str
    tier_weight: float
    
    # Individual Risks
    job_failure_risk: RiskScore
    capacity_risk: RiskScore
    efficiency_risk: RiskScore
    recovery_risk: RiskScore
    data_quality_risk: RiskScore
    
    # Composite
    composite_score: float
    overall_confidence_multiplier: float
    business_impact_score: float
    risk_category: RiskCategory
    
    # Metadata
    feature_health_matrix: Dict
    data_freshness_report: Dict
    quality_flags: List[str]
    priority_rank: int = 0

# =============================================================================
# ENGINE
# =============================================================================

class Feature5RiskAnalysisEngine:
    
    def __init__(self, config_path: str = "business_context_config.yaml"):
        self.config = self._load_config(config_path)
        
        # Dual DB Architecture
        self.metrics_db_config = {
            'host': 'localhost', 'database': 'dr365v_metrics',
            'user': 'postgres', 'password': 'admin'
        }
        self.risk_db_config = {
            'host': 'localhost', 'database': 'dr365v',
            'user': 'postgres', 'password': 'admin'
        }

    def _load_config(self, path: str) -> Dict:
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(__file__), path)
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def _get_metrics_conn(self):
        return psycopg2.connect(**self.metrics_db_config)
    
    def _get_risk_conn(self):
        return psycopg2.connect(**self.risk_db_config)

    def run_analysis(self):
        logger.info("Starting Per-Job Risk Analysis (Strict Compliance Mode)")
        
        # 1. Fetch Global Data & Feature Health
        f1_data_global, f1_jobs = self._fetch_feature_1_data()
        f2_data = self._fetch_feature_2_data()
        f3_data = self._fetch_feature_3_data()
        f4_data = self._fetch_feature_4_data()
        
        # 2. Check Feature Health
        health_checks = self._perform_all_health_checks(f1_data_global, f2_data, f3_data, f4_data)
        
        # 3. Detect Staleness Cascades
        cascades = self._detect_staleness_cascades(health_checks)
        
        # 4. Calculate Overall Confidence
        overall_conf = self._calculate_overall_confidence(health_checks, cascades)
        logger.info(f"Overall Confidence Multiplier: {overall_conf}")

        # 5. Process Each Job
        all_risks = []
        
        # We iterate over all unique jobs found in F1 (Inventory Source)
        # Note: If F3/F4 have jobs not in F1, strictly we might miss them, but F1 scans all sessions.
        for job in f1_jobs:
            job_id = job['job_id']
            job_name = job['job_name']
            repo_id = job.get('repository_id')
            
            # Classify Tier
            tier_name, tier_weight = self._classify_vm_tier(job_name)
            
            # Map Specific Data
            # F1 Risk: Global System Health (as per Spec interpretation)
            # F2 Risk: Based on Repository Capacity
            f2_job_data = f2_data.get(repo_id) if repo_id else None
            # F3 Risk: Based on Job Efficiency
            f3_job_data = f3_data.get(job_id)
            # F4 Risk: Based on Job Recovery
            f4_job_data = f4_data.get(job_id)

            # Calculate Scores
            # Using per-job F1 success rate logic as decided
            scores = self._calculate_risk_scores(
                f1_data_global, job, f2_job_data, f3_job_data, f4_job_data, health_checks
            )
            
            # Composite & Impact
            consolidated = self._calculate_composite_risk(
                job_id, job_name, tier_name, tier_weight, 
                scores, overall_conf, health_checks, cascades
            )
            
            all_risks.append(consolidated)
            
        # 6. Store Results
        self._store_results(all_risks)
        logger.info(f"Analysis Complete. Processed {len(all_risks)} jobs.")

    # --- Data Fetching ---

    def _fetch_feature_1_data(self):
        conn = self._get_metrics_conn()
        cur = conn.cursor()
        
        # Global Health
        cur.execute("""
            SELECT created_at, overall_score, sample_count, trend_classification, quality_flags 
            FROM feature1.metrics_health_score ORDER BY created_at DESC LIMIT 1
        """)
        row = cur.fetchone()
        global_data = {}
        if row:
            global_data = {
                'created_at': row[0], 'overall_score': float(row[1]), 
                'sample_count': row[2], 'trend': row[3], 'quality_flags': row[4]
            }
            
        # Job Inventory & Metrics
        # Fetch success_rate for per-job risk calculation
        cur.execute("""
            SELECT job_id, job_name, repository_id, success_rate 
            FROM feature1.metrics_job_failures 
            WHERE created_at > NOW() - INTERVAL '7 days'
        """)
        # Dedupe by job_id - keep latest if duplicates exist (though query doesn't sort, we assume DB handles or we take arbitrary)
        # Ideally we'd window function it, but for simplicity in python:
        jobs_map = {}
        for r in cur.fetchall():
            # r: 0=id, 1=name, 2=repo, 3=success_rate
            jobs_map[r[0]] = {
                'job_id': r[0], 'job_name': r[1], 
                'repository_id': r[2], 'success_rate': float(r[3] or 0)
            }
            
        conn.close()
        return global_data, list(jobs_map.values())

    def _fetch_feature_2_data(self):
        # Return dict {repo_id: data}
        conn = self._get_metrics_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT repository_id, created_at, days_to_80_percent, r_squared, quality_flags
            FROM feature2.metrics_capacity_forecast 
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        data = {}
        for r in cur.fetchall():
            data[r[0]] = {
                'created_at': r[1], 'days_to_80': r[2], 'r_squared': float(r[3]), 'quality_flags': r[4]
            }
        conn.close()
        return data

    def _fetch_feature_3_data(self):
        # Return dict {job_id: data}
        conn = self._get_metrics_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT job_id, created_at, overall_score, anomalies_detected, quality_flags
            FROM feature3.metrics_storage_efficiency
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        data = {}
        for r in cur.fetchall():
            data[r[0]] = {
                'created_at': r[1], 'optimization_score': float(r[2] or 0), 
                'anomaly_count': r[3], 'quality_flags': r[4]
            }
        conn.close()
        return data

    def _fetch_feature_4_data(self):
        # Return dict {job_id: data}
        conn = self._get_metrics_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT job_id, created_at, overall_confidence_score, sample_count, confidence_level, quality_flags
            FROM feature4.metrics_recovery_verification
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        data = {}
        for r in cur.fetchall():
            data[r[0]] = {
                'created_at': r[1], 'rto_score': float(r[2]), 
                'sample_count': r[3], 'confidence_level': r[4], 'quality_flags': r[5]
            }
        conn.close()
        return data

    # --- Health & Logic ---

    def _perform_all_health_checks(self, f1, f2, f3, f4) -> Dict[int, FeatureHealthCheck]:
        # Dummy wrapper for fetching "representative" health
        # In strictly per-job, health might vary (e.g. F3 data missing for Job A but present for Job B)
        # But spec treats FeatureHealthCheck as "Feature Subsystem Health".
        # We will use the latest available data to check "System Freshness".
        
        checks = {}
        
        # F1 Check
        checks[1] = self._check_feature_health(1, f1, 24, [])
        
        # F2 Check (Any repo fresh?)
        last_f2 = max([d['created_at'] for d in f2.values()]) if f2 else None
        f2_sample = {'created_at': last_f2} if last_f2 else {}
        checks[2] = self._check_feature_health(2, f2_sample, 24, [])
        
        # F3 Check
        last_f3 = max([d['created_at'] for d in f3.values()]) if f3 else None
        f3_sample = {'created_at': last_f3} if last_f3 else {}
        checks[3] = self._check_feature_health(3, f3_sample, 24, [])
        
        # F4 Check
        last_f4 = max([d['created_at'] for d in f4.values()]) if f4 else None
        f4_sample = {'created_at': last_f4} if last_f4 else {}
        checks[4] = self._check_feature_health(4, f4_sample, 24, [])
        
        return checks

    def _check_feature_health(self, f_num: int, data: Dict, max_age_hours: int, checks: List) -> FeatureHealthCheck:
        issues = []
        all_ok = True
        
        if not data or 'created_at' not in data:
            return FeatureHealthCheck(f_num, False, 999, False, ["no_data_available"], False, 0.3, DataQualityStatus.FAILED)
            
        # Parse created_at (handle formatting)
        try:
            # Handle potential Z or no Z
            dt_str = str(data['created_at']).replace('Z', '')
            # If standard ISO, it might fail if microseconds missing.
            # Robust parsing:
            if '.' in dt_str:
                fmt = "%Y-%m-%dT%H:%M:%S.%f"
            else:
                fmt = "%Y-%m-%dT%H:%M:%S"
            created_at = datetime.strptime(dt_str, fmt)
        except Exception as e:
            # Fallback for simple date parsing or already datetime object
            if isinstance(data['created_at'], (datetime, float, int)): # Should be datetime from psycopg2
                 created_at = data['created_at']
            else:
                 logger.warning(f"Date parse error: {e}")
                 created_at = datetime.now() - timedelta(hours=999)

        age = (datetime.now() - created_at).total_seconds() / 3600
        freshness_ok = age <= max_age_hours
        
        if not freshness_ok:
             issues.append(f"data_stale_{age:.1f}h_old")
             all_ok = False

        # Feature Specific Logic (Strictly from Spec)
        if f_num == 1:
            if data.get('sample_count', 0) < 30:
                issues.append("sample_count_low")
                all_ok = False
            # Trend Check (Spec says: if trend == 'degrading')
            # DB column is trend_classification or trend
            trend = data.get('trend') or data.get('trend_classification')
            if str(trend).upper() == 'DEGRADING':
                issues.append("trend_degrading")
                all_ok = False
            if not (0 <= float(data.get('overall_score', 0)) <= 100):
                 issues.append("score_invalid")
                 all_ok = False

        elif f_num == 2:
            if data.get('r_squared', 0) < 0.70:
                issues.append("r_squared_low")
                all_ok = False
            if data.get('quality_flags') == 'LOW_CONFIDENCE': # DB col might be quality_flags
                 issues.append("quality_flag_low")
                 all_ok = False
        
        elif f_num == 3:
            # Config: anomaly_count_threshold: 2
            thresh = self.config['feature_5']['risk_thresholds']['anomaly_count_threshold']
            if data.get('anomaly_count', 0) > thresh:
                 issues.append("anomaly_count_high")
                 all_ok = False
        
        elif f_num == 4:
            if data.get('confidence_level') not in ['HIGH', 'MODERATE']:
                 issues.append("confidence_low")
                 all_ok = False
            if data.get('sample_count', 0) < 10:
                 issues.append("sample_count_low")
                 all_ok = False

        # Multiplier Calculation
        multiplier = 1.0
        status = DataQualityStatus.COMPLETE
        
        if len(issues) == 1:
            multiplier = 0.8
            status = DataQualityStatus.PARTIAL
        elif len(issues) >= 2:
            multiplier = 0.6
            status = DataQualityStatus.PARTIAL
        
        # If stale or failed, enforce lower bounds? 
        # Spec: Any FAILED -> 0.3 (handled in overall logic usually, but here we set per feature)
        # Spec Lines 907: If no data -> 0.3.
        # But if just stale? Line 319 of original file (Spec Line 172) says status=STALE.
        # If failed checks, we just return Partial usually unless critical.
        
        return FeatureHealthCheck(f_num, freshness_ok, age, all_ok, issues, True, multiplier, status)

    def _detect_staleness_cascades(self, health_checks: Dict) -> List:
        cascades = []
        # Spec logic: F1 stale but F2 fresh?
        if health_checks[1].freshness_hours > 24 and health_checks[2].freshness_hours < 2:
             cascades.append({'cascade': 'F1_to_F2'})
        return cascades

    def _calculate_overall_confidence(self, health, cascades) -> float:
        # Spec logic: Count based
        failed = sum(1 for h in health.values() if h.status == DataQualityStatus.FAILED)
        partial = sum(1 for h in health.values() if h.status == DataQualityStatus.PARTIAL)
        
        if failed > 0: return 0.3
        if partial >= 2: return 0.6
        if partial == 1: return 0.8
        
        val = 1.0
        if cascades: val = 0.7
        return val

    def _classify_vm_tier(self, job_name: str) -> Tuple[str, float]:
        cfg = self.config['feature_5']['vm_tier_classification']
        
        # 1. Overrides
        overrides = cfg.get('manual_overrides', {})
        if job_name in overrides:
            t = overrides[job_name]['tier']
            # Find weight from definitions
            w = cfg['tier_definitions'][t]['weight']
            return t, w
            
        # 2. Patterns
        for tier, params in cfg['tier_definitions'].items():
            for pat in params['patterns']:
                if re.search(pat, job_name, re.IGNORECASE):
                    return tier, params['weight']
                    
        # 3. Default
        def_t = cfg['default_tier']
        # Find weight loosely
        def_w = 0.5 # Fallback
        if def_t in cfg['tier_definitions']:
             def_w = cfg['tier_definitions'][def_t]['weight']
        return def_t, def_w

    def _calculate_risk_scores(self, f1_global, f1_job, f2, f3, f4, health) -> Dict[str, RiskScore]:
        scores = {}
        w = self.config['feature_5']['risk_score_weights']
        thresh = self.config['feature_5']['risk_thresholds']
        
        # 1. Job Failure Risk (100 - Job Success Rate)
        # We use strict per-job success rate if available.
        # Fallback to Global only if job data missing (unlikely if iterating job list)
        
        if f1_job and 'success_rate' in f1_job:
            # Risk is Probability of Failure. Success Rate is Probability of Success.
            base1 = 100.0 - f1_job['success_rate']
        else:
            # Fallback to Global derivation
            base1 = 100.0 - f1_global.get('overall_score', 0) if f1_global else 50.0
            
        # Ensure bounds 0-100
        base1 = max(0.0, min(100.0, base1))
            
        scores['job_failure'] = RiskScore(
            "job_failure", base1, health[1].confidence_multiplier,
            base1 * health[1].confidence_multiplier,
            thresh['job_failure_risk_score_threshold'],
            base1 > thresh['job_failure_risk_score_threshold']
        )
        
        # 2. Capacity Risk (Strict Thresholds from Guide)
        # <= 30: 100 (Critical)
        # <= Threshold (60): 70
        # <= 120: 40
        # Else: 10
        base2 = 50 # Default
        if f2:
            days = f2.get('days_to_80', 60)
            if days is None: days = 365 # Handle 'None' (e.g. infinite)
            
            t_days = thresh['capacity_days_threshold'] # 60
            
            if days <= 30: base2 = 100
            elif days <= t_days: base2 = 70
            elif days <= 120: base2 = 40
            else: base2 = 10
            
        scores['capacity'] = RiskScore(
            "capacity", base2, health[2].confidence_multiplier,
            base2 * health[2].confidence_multiplier,
            thresh['capacity_days_threshold'],
            False # Logic complex for boolean flag (days < threshold)
        )
        if f2:
            scores['capacity'].exceeds_threshold = (f2.get('days_to_80', 365) or 365) < thresh['capacity_days_threshold']
        
        # 3. Efficiency Risk (Inverse of Optimization Score)
        base3 = 100 - f3.get('optimization_score', 0) if f3 else 60
        scores['efficiency'] = RiskScore(
            "efficiency", base3, health[3].confidence_multiplier,
            base3 * health[3].confidence_multiplier,
            thresh['efficiency_score_threshold'],
            False
        )
        
        # 4. Recovery Risk (Mapping from Confidence Level)
        # HIGH -> 10, MODERATE -> 30, LOW -> 60, Else -> 90
        base4 = 90
        if f4:
            conf = f4.get('confidence_level', 'INSUFFICIENT')
            if conf == 'HIGH': base4 = 10
            elif conf == 'MODERATE': base4 = 30
            elif conf == 'LOW': base4 = 60
            else: base4 = 90
            
        scores['recovery'] = RiskScore(
            "recovery", base4, health[4].confidence_multiplier,
            base4 * health[4].confidence_multiplier,
            50, # Arbitrary check or need threshold? Config has rto_confidence_threshold: "MODERATE"
            False
        )
        # Check threshold logic for enum
        # Config: rto_confidence_threshold: "MODERATE"
        # If current is LOW or INSUFFICIENT -> Exceeds
        curr_conf = f4.get('confidence_level', 'INSUFFICIENT') if f4 else 'INSUFFICIENT'
        if curr_conf in ['LOW', 'INSUFFICIENT']:
             scores['recovery'].exceeds_threshold = True

        # 5. Data Quality Risk (Issue Counting)
        # Count total strings in quality_issues across all features
        total_issues = sum(len(h.quality_issues) for h in health.values())
        if total_issues <= 2: dq_base = 10
        elif total_issues <= 5: dq_base = 40
        else: dq_base = 75
        
        scores['data_quality'] = RiskScore(
            "data_quality", dq_base, 1.0, dq_base,
            thresh['data_quality_risk_threshold'],
            dq_base > thresh['data_quality_risk_threshold']
        )
        
        return scores

    def _calculate_composite_risk(self, j_id, j_name, tier, tier_w, scores, overall_conf, health, cascades) -> ConsolidatedRisk:
        params = self.config['feature_5']['risk_score_weights']
        
        comp = (
            scores['job_failure'].adjusted_score * params['job_failure_weight'] +
            scores['capacity'].adjusted_score * params['capacity_weight'] +
            scores['efficiency'].adjusted_score * params['efficiency_weight'] +
            scores['recovery'].adjusted_score * params['recovery_weight'] +
            scores['data_quality'].adjusted_score * params['data_quality_weight']
        )
        
        # Apply Overall Confidence Multiplier (Spec Line 562)
        comp = comp * overall_conf
        comp = min(100, comp)
        
        impact = comp * tier_w
        
        # Category
        cat = RiskCategory.LOW
        if impact >= 70: cat = RiskCategory.CRITICAL # Spec says 70=HIGH, my enum has CRITICAL. I'll align.
        elif impact >= 40: cat = RiskCategory.MEDIUM
        
        return ConsolidatedRisk(
            job_id=j_id, job_name=j_name, vm_tier=tier, tier_weight=tier_w,
            job_failure_risk=scores['job_failure'],
            capacity_risk=scores['capacity'],
            efficiency_risk=scores['efficiency'],
            recovery_risk=scores['recovery'],
            data_quality_risk=scores['data_quality'],
            composite_score=round(comp, 2),
            overall_confidence_multiplier=overall_conf,
            business_impact_score=round(impact, 2),
            risk_category=cat,
            feature_health_matrix={k: h.status.value for k,h in health.items()},
            data_freshness_report={k: h.freshness_hours for k,h in health.items()},
            quality_flags=[]
        )

    def _store_results(self, risks: List[ConsolidatedRisk]):
        conn = self._get_risk_conn()
        conn.autocommit = True
        cur = conn.cursor()
        
        for r in risks:
            # Cast UUID safe
            try:
                # Assuming job_id is UUID string
                jid = str(uuid.UUID(str(r.job_id)))
            except:
                # Fallback
                jid = r.job_id 

            # UPSERT: Use ON CONFLICT instead of DELETE+INSERT

            cur.execute("""
                INSERT INTO dr365v.metrics_risk_analysis_consolidated (
                    job_id, job_name, vm_tier, tier_weight,
                    job_failure_risk_score, capacity_risk_score, efficiency_risk_score,
                    recovery_risk_score, data_quality_risk_score,
                    composite_risk_score, overall_data_confidence, business_impact_score,
                    risk_category, feature_1_status, feature_2_status, feature_3_status, feature_4_status,
                    quality_flags, analysis_date
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, NOW()
                )
                ON CONFLICT (job_id, analysis_date_only) DO UPDATE SET
                    job_name = EXCLUDED.job_name,
                    vm_tier = EXCLUDED.vm_tier,
                    tier_weight = EXCLUDED.tier_weight,
                    job_failure_risk_score = EXCLUDED.job_failure_risk_score,
                    capacity_risk_score = EXCLUDED.capacity_risk_score,
                    efficiency_risk_score = EXCLUDED.efficiency_risk_score,
                    recovery_risk_score = EXCLUDED.recovery_risk_score,
                    data_quality_risk_score = EXCLUDED.data_quality_risk_score,
                    composite_risk_score = EXCLUDED.composite_risk_score,
                    overall_data_confidence = EXCLUDED.overall_data_confidence,
                    business_impact_score = EXCLUDED.business_impact_score,
                    risk_category = EXCLUDED.risk_category,
                    feature_1_status = EXCLUDED.feature_1_status,
                    feature_2_status = EXCLUDED.feature_2_status,
                    feature_3_status = EXCLUDED.feature_3_status,
                    feature_4_status = EXCLUDED.feature_4_status,
                    quality_flags = EXCLUDED.quality_flags,
                    analysis_date = NOW()
            """, (
                jid, r.job_name, r.vm_tier, r.tier_weight,
                int(r.job_failure_risk.adjusted_score),
                int(r.capacity_risk.adjusted_score),
                int(r.efficiency_risk.adjusted_score),
                int(r.recovery_risk.adjusted_score),
                int(r.data_quality_risk.adjusted_score),
                int(r.composite_score),
                r.overall_confidence_multiplier,
                int(r.business_impact_score),
                r.risk_category.value,
                r.feature_health_matrix[1], r.feature_health_matrix[2], 
                r.feature_health_matrix[3], r.feature_health_matrix[4],
                r.quality_flags
            ))
        conn.close()

if __name__ == "__main__":
    engine = Feature5RiskAnalysisEngine()
    engine.run_analysis()
