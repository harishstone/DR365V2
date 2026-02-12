#!/usr/bin/env python3
"""
Feature 6: Actionable Recommendations & Guidance System
Production-ready implementation for planning and guidance ONLY
NO EXECUTION, NO API WRITES, NO AUTOMATED CHANGES

Strict compliance with:
- Feature 06 Actionable Recommendations And Guidance System Implementation Guide Final.md
- FEATURE_6_EXACT_SPECIFICATIONS.md
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import yaml
import json
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from enum import Enum
import uuid
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Feature6_GuidanceEngine")

# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class RiskType(Enum):
    JOB_FAILURE = "job_failure"
    CAPACITY = "capacity"
    EFFICIENCY = "efficiency"
    RECOVERY = "recovery"
    DATA_QUALITY = "data_quality"

class UrgencyLevel(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class ComplexityLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

@dataclass
class InvestigationStep:
    """Investigation step with priority and details"""
    priority: int
    description: str
    expected_duration_minutes: int
    tools_needed: List[str]
    success_criteria: str

@dataclass
class RemediationOption:
    """Remediation option with considerations (NOT prescriptions)"""
    option_id: str
    name: str
    description: str
    when_to_consider: str
    typical_effort_hours: float
    complexity: str
    prerequisites: List[str]
    risks: List[str]
    verification_steps: List[str]
    guidance_notes: List[str]

@dataclass
class SuccessCriteria:
    """Success criteria for remediation"""
    metrics: List[Dict]
    verification_method: str
    timeframe: str
    fallback_plan: str

@dataclass
class RemediationPlan:
    """Complete remediation guidance plan"""
    plan_id: str
    generated_at: datetime
    
    # Risk Context
    risk_id: str
    risk_type: str
    job_id: Optional[str]
    job_name: Optional[str]
    vm_tier: str
    composite_risk_score: float
    business_impact_score: float
    confidence_level: str
    
    # Plan Content
    issue_summary: str
    pattern_analysis: str
    root_cause_hypotheses: List[str]
    investigation_steps: List[InvestigationStep]
    remediation_options: List[RemediationOption]
    success_criteria: SuccessCriteria
    
    # Metadata
    urgency: str
    estimated_effort_hours: float
    complexity: str
    prerequisites: List[str]
    warnings: List[str]
    
    # Complete JSON
    plan_json: Dict

# ============================================================================
# MAIN FEATURE 6 GUIDANCE ENGINE
# ============================================================================

class Feature6GuidanceEngine:
    """
    Production-ready guidance engine for remediation planning.
    GENERATES PLANS ONLY - NO EXECUTION, NO CHANGES MADE.
    """
    
    def __init__(self, config_file: str = None):
        """Initialize Feature 6 guidance engine"""
        self.logger = logging.getLogger("Feature6GuidanceEngine")
        
        # Load configuration
        if config_file is None:
            config_file = os.path.join(os.path.dirname(__file__), 'config.yaml')
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # [SECURITY FIX] Inject Environment Variables
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            f6_conf = config.get('feature_6', {})
            
            # Database Overrides
            if 'database' not in f6_conf: f6_conf['database'] = {}
            if os.getenv('DB_HOST'): f6_conf['database']['host'] = os.getenv('DB_HOST')
            if os.getenv('DB_PORT'): f6_conf['database']['port'] = int(os.getenv('DB_PORT'))
            # [FIX] Feature 6 must use the Risk Database (dr365v), not the Metrics Database (dr365v_metrics)
            # if os.getenv('DB_NAME'): f6_conf['database']['database'] = os.getenv('DB_NAME') 
            f6_conf['database']['database'] = 'dr365v'
            if os.getenv('DB_USER'): f6_conf['database']['user'] = os.getenv('DB_USER')
            if os.getenv('DB_PASSWORD'): f6_conf['database']['password'] = os.getenv('DB_PASSWORD')

            # Veeam Overrides (if present)
            if 'veeam_api' in f6_conf and os.getenv('VEEAM_SERVER'):
                f6_conf['veeam_api']['api_url'] = f"https://{os.getenv('VEEAM_SERVER')}:9419"

            config['feature_6'] = f6_conf
        except Exception as e:
            self.logger.warning(f"Failed to load environment variables: {e}")

        self.config = config['feature_6']
        
        # Safety validation
        self._validate_safety_configuration()
        
        # Database connection
        self.db_config = self.config['database']
        self.db = None
        
        self.logger.info("Feature 6 Guidance Engine initialized (Planning Only)")
    
    def _validate_safety_configuration(self):
        """Validate that configuration guarantees safety"""
        safety = self.config['safety']
        
        if not safety['no_execution_guarantee']:
            raise ValueError("SAFETY VIOLATION: Configuration does not guarantee no execution")
        
        if not safety['read_only_api_only']:
            raise ValueError("SAFETY VIOLATION: Read-only mode not enforced")
        
        if not safety['human_review_required']:
            raise ValueError("SAFETY VIOLATION: Human review not required")
        
        self.logger.info("Safety configuration validated: NO EXECUTION GUARANTEED")
    
    def _get_db_connection(self):
        """Get database connection"""
        if self.db is None or self.db.closed:
            self.db = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password']
            )
        return self.db
    
    def generate_remediation_plans(self) -> List[RemediationPlan]:
        """
        Main entry point: Generate remediation plans for high-priority risks
        Returns: List of complete remediation guidance plans
        """
        self.logger.info("=" * 80)
        self.logger.info("FEATURE 6 GUIDANCE ENGINE - GENERATING REMEDIATION PLANS")
        self.logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
        self.logger.info("=" * 80)
        
        plans = []
        
        try:
            # Connect to database
            conn = self._get_db_connection()
            
            # Step 1: Retrieve high-priority risks from Feature 5
            high_priority_risks = self._retrieve_high_priority_risks(conn)
            self.logger.info(f"Retrieved {len(high_priority_risks)} high-priority risks")
            
            # Step 2: Generate plan for each risk
            for risk_data in high_priority_risks:
                try:
                    # Check for duplicate plan (recently generated)
                    if self._check_duplicate_plan_exists(conn, risk_data):
                        self.logger.info(f"Skipping duplicate plan for {risk_data.get('job_name')} (recently generated)")
                        continue

                    plan = self._generate_single_plan(risk_data)
                    plans.append(plan)
                    self.logger.info(f"Generated plan {plan.plan_id} for {risk_data.get('job_name', 'unknown')}")
                except Exception as e:
                    self.logger.error(f"Failed to generate plan for risk {risk_data.get('risk_id')}: {e}")
                    continue
            
            # Step 3: Store plans in database
            if plans and self.config['output']['store_in_database']:
                self._store_plans_in_database(conn, plans)
            
            self.logger.info("=" * 80)
            self.logger.info(f"FEATURE 6 COMPLETE - {len(plans)} plans generated")
            self.logger.info(f"Critical/High Urgency: {sum(1 for p in plans if p.urgency in ['CRITICAL', 'HIGH'])}")
            self.logger.info(f"Medium Urgency: {sum(1 for p in plans if p.urgency == 'MEDIUM')}")
            self.logger.info(f"Low Urgency: {sum(1 for p in plans if p.urgency == 'LOW')}")
            self.logger.info("=" * 80)
            
            return plans
        
        except Exception as e:
            self.logger.critical(f"Feature 6 plan generation failed: {str(e)}")
            raise
        finally:
            if self.db and not self.db.closed:
                self.db.close()
    
    def _check_duplicate_plan_exists(self, conn, risk_data: Dict) -> bool:
        """
        Check if a valid plan already exists for this job and risk type
        Logic: Avoid generating duplicate plans if one was generated recently (< 24h)
        """
        try:
            cur = conn.cursor()
            
            job_id = risk_data.get('job_id')
            
            # Determine primary risk type to check against
            # (We need to execute this locally since _generate_single_plan hasn't run yet)
            risk_type = self._determine_primary_risk_type(risk_data).value
            
            query = """
                SELECT COUNT(*)
                FROM dr365v.remediation_plans
                WHERE job_id = %s
                AND risk_type = %s
                AND generated_at >= NOW() - INTERVAL '24 hours'
                AND is_test_data = FALSE  -- Only check production plans
            """
            
            cur.execute(query, (job_id, risk_type))
            count = cur.fetchone()[0]
            cur.close()
            
            return count > 0
            
        except Exception as e:
            self.logger.warning(f"Failed to check for duplicate plans: {e}")
            return False

    def _retrieve_high_priority_risks(self, conn) -> List[Dict]:
        """Retrieve high-priority risks from Feature 5 database"""
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        threshold = self.config['risk_filtering']['min_risk_score']
        max_plans = self.config['risk_filtering']['max_plans_per_execution']
        
        query = """
            SELECT DISTINCT ON (job_id)
                job_id, job_name, vm_tier,
                composite_risk_score, business_impact_score,
                job_failure_risk_score, capacity_risk_score, efficiency_risk_score, 
                recovery_risk_score, data_quality_risk_score,
                overall_data_confidence, analysis_date
            FROM dr365v.metrics_risk_analysis_consolidated
            WHERE composite_risk_score >= %s
                AND analysis_date >= NOW() - INTERVAL '24 hours'
            ORDER BY job_id, analysis_date DESC
        """
        
        cur.execute(query, (threshold,))
        rows = cur.fetchall()
        
        # Sort by business impact and limit
        risks = sorted(rows, key=lambda x: x['business_impact_score'], reverse=True)[:max_plans]
        
        cur.close()
        return [dict(r) for r in risks]
    
    def _generate_single_plan(self, risk_data: Dict) -> RemediationPlan:
        """Generate a complete remediation plan for a single risk"""
        
        # Determine primary risk type (highest individual risk score)
        risk_type = self._determine_primary_risk_type(risk_data)
        
        # Generate plan components
        issue_summary = self._generate_issue_summary(risk_data, risk_type)
        pattern_analysis = self._analyze_risk_pattern(risk_data, risk_type)
        root_cause_hypotheses = self._generate_root_cause_hypotheses(risk_type, risk_data)
        investigation_steps = self._generate_investigation_steps(risk_type, risk_data)
        remediation_options = self._generate_remediation_options(risk_type, risk_data)
        success_criteria = self._define_success_criteria(risk_type, risk_data)
        
        # Calculate metadata
        estimated_effort = self._calculate_estimated_effort(investigation_steps, remediation_options)
        urgency = self._determine_urgency(risk_data)
        complexity = self._determine_complexity(risk_data, risk_type)
        prerequisites = self._generate_prerequisites(risk_data, remediation_options)
        warnings = self._generate_warnings(risk_data)
        
        # Create plan
        plan_id = str(uuid.uuid4())
        generated_at = datetime.utcnow()
        
        plan = RemediationPlan(
            plan_id=plan_id,
            generated_at=generated_at,
            risk_id=str(risk_data.get('job_id', uuid.uuid4())),
            risk_type=risk_type.value,
            job_id=risk_data.get('job_id'),
            job_name=risk_data.get('job_name'),
            vm_tier=risk_data.get('vm_tier', 'MEDIUM'),
            composite_risk_score=float(risk_data['composite_risk_score']),
            business_impact_score=float(risk_data['business_impact_score']),
            confidence_level=self._map_confidence(risk_data.get('overall_data_confidence', 0.5)),
            issue_summary=issue_summary,
            pattern_analysis=pattern_analysis,
            root_cause_hypotheses=root_cause_hypotheses,
            investigation_steps=investigation_steps,
            remediation_options=remediation_options,
            success_criteria=success_criteria,
            urgency=urgency.value,
            estimated_effort_hours=estimated_effort,
            complexity=complexity.value,
            prerequisites=prerequisites,
            warnings=warnings,
            plan_json={}  # Will be filled below
        )
        
        # Generate JSON output
        plan.plan_json = self._generate_json_output(plan)
        
        return plan
    
    def _determine_primary_risk_type(self, risk_data: Dict) -> RiskType:
        """Determine primary risk type based on highest individual risk score"""
        risk_scores = {
            RiskType.JOB_FAILURE: risk_data.get('job_failure_risk_score', 0),
            RiskType.CAPACITY: risk_data.get('capacity_risk_score', 0),
            RiskType.EFFICIENCY: risk_data.get('efficiency_risk_score', 0),
            RiskType.RECOVERY: risk_data.get('recovery_risk_score', 0),
            RiskType.DATA_QUALITY: risk_data.get('data_quality_risk_score', 0)
        }
        
        primary_type = max(risk_scores, key=risk_scores.get)
        return primary_type
    
    def _map_confidence(self, multiplier: float) -> str:
        """Map confidence multiplier to level"""
        if multiplier >= 0.8:
            return "HIGH"
        elif multiplier >= 0.5:
            return "MODERATE"
        elif multiplier >= 0.3:
            return "LOW"
        else:
            return "INSUFFICIENT"
    
    def _generate_issue_summary(self, risk_data: Dict, risk_type: RiskType) -> str:
        """Generate concise issue summary"""
        job_name = risk_data.get('job_name', 'Unknown Job')
        score = risk_data['composite_risk_score']
        
        if risk_type == RiskType.JOB_FAILURE:
            return f"{job_name} showing elevated failure risk with {score:.1f}/100 risk score. Investigation recommended for job reliability."
        elif risk_type == RiskType.CAPACITY:
            return f"Storage capacity risk detected with {score:.1f}/100 risk score. Review capacity planning and efficiency features."
        elif risk_type == RiskType.EFFICIENCY:
            return f"{job_name} showing suboptimal storage efficiency with {score:.1f}/100 risk score. Optimization opportunities may exist."
        elif risk_type == RiskType.RECOVERY:
            return f"{job_name} showing recovery uncertainty with {score:.1f}/100 risk score. Recovery testing and validation recommended."
        else:
            return f"{job_name} showing data quality concerns with {score:.1f}/100 risk score. Validation recommended."
    
    def _analyze_risk_pattern(self, risk_data: Dict, risk_type: RiskType) -> str:
        """Analyze risk pattern"""
        score = risk_data['composite_risk_score']
        
        if score >= 70:
            severity = "high severity"
        elif score >= 50:
            severity = "moderate severity"
        else:
            severity = "low to moderate severity"
        
        return f"Risk pattern indicates {severity} issue requiring attention. Business impact score: {risk_data['business_impact_score']:.1f}/100."
    
    def _generate_root_cause_hypotheses(self, risk_type: RiskType, risk_data: Dict) -> List[str]:
        """Generate root cause hypotheses based on risk type"""
        
        if risk_type == RiskType.JOB_FAILURE:
            return [
                "Insufficient retry settings for transient failures",
                "Resource constraints during backup window",
                "Infrastructure performance issues (storage/network)",
                "Software or configuration changes affecting backup process"
            ]
        elif risk_type == RiskType.CAPACITY:
            return [
                "Accelerating data growth from new sources",
                "Retention policies exceeding business needs",
                "Suboptimal storage efficiency feature utilization",
                "Limited storage expansion planning"
            ]
        elif risk_type == RiskType.EFFICIENCY:
            return [
                "Deduplication or compression not optimally configured",
                "Data types not suitable for current efficiency settings",
                "Repository configuration suboptimal",
                "Backup job settings not aligned with data characteristics"
            ]
        elif risk_type == RiskType.RECOVERY:
            return [
                "Insufficient recovery testing frequency",
                "SureBackup not configured or not running",
                "Recovery procedures not validated",
                "RTO targets not aligned with infrastructure capabilities"
            ]
        else:
            return [
                "Data validation processes insufficient",
                "Backup integrity checks not comprehensive",
                "Historical data quality issues",
                "Monitoring gaps in data quality metrics"
            ]
    
    def _generate_investigation_steps(self, risk_type: RiskType, risk_data: Dict) -> List[InvestigationStep]:
        """Generate prioritized investigation steps"""
        
        if risk_type == RiskType.JOB_FAILURE:
            return [
                InvestigationStep(
                    priority=1,
                    description="Review current job configuration and retry settings",
                    expected_duration_minutes=15,
                    tools_needed=["Veeam Console", "Job configuration report"],
                    success_criteria="Understand current settings and identify obvious mismatches"
                ),
                InvestigationStep(
                    priority=2,
                    description="Examine recent failure logs for specific error patterns",
                    expected_duration_minutes=30,
                    tools_needed=["Veeam Session Logs", "Event Viewer"],
                    success_criteria="Identify dominant failure mode (VSS, network, storage, etc.)"
                ),
                InvestigationStep(
                    priority=3,
                    description="Check infrastructure health during failure windows",
                    expected_duration_minutes=45,
                    tools_needed=["Storage performance logs", "Network monitoring", "Hypervisor metrics"],
                    success_criteria="Correlate failures with infrastructure events or performance issues"
                )
            ]
        
        elif risk_type == RiskType.CAPACITY:
            return [
                InvestigationStep(
                    priority=1,
                    description="Analyze storage growth rate and composition",
                    expected_duration_minutes=30,
                    tools_needed=["Veeam Capacity Report", "Storage analytics"],
                    success_criteria="Identify growth drivers and acceleration patterns"
                ),
                InvestigationStep(
                    priority=2,
                    description="Review retention policies and alignment with business needs",
                    expected_duration_minutes=45,
                    tools_needed=["Business requirements document", "Compliance policy"],
                    success_criteria="Identify retention policy optimization opportunities"
                ),
                InvestigationStep(
                    priority=3,
                    description="Evaluate efficiency feature utilization",
                    expected_duration_minutes=20,
                    tools_needed=["Repository configuration", "Deduplication/compression reports"],
                    success_criteria="Understand current efficiency gains and potential improvements"
                )
            ]
        
        elif risk_type == RiskType.EFFICIENCY:
            return [
                InvestigationStep(
                    priority=1,
                    description="Review current deduplication and compression settings",
                    expected_duration_minutes=20,
                    tools_needed=["Repository configuration", "Job settings"],
                    success_criteria="Understand current efficiency configuration"
                ),
                InvestigationStep(
                    priority=2,
                    description="Analyze backup data characteristics and types",
                    expected_duration_minutes=30,
                    tools_needed=["Backup session details", "Data type analysis"],
                    success_criteria="Identify data types and their efficiency potential"
                ),
                InvestigationStep(
                    priority=3,
                    description="Compare with similar jobs and best practices",
                    expected_duration_minutes=25,
                    tools_needed=["Efficiency reports", "Best practice guides"],
                    success_criteria="Identify gaps from optimal configuration"
                )
            ]
        
        elif risk_type == RiskType.RECOVERY:
            return [
                InvestigationStep(
                    priority=1,
                    description="Review recovery testing frequency and coverage",
                    expected_duration_minutes=20,
                    tools_needed=["SureBackup reports", "Recovery test logs"],
                    success_criteria="Understand current testing coverage and gaps"
                ),
                InvestigationStep(
                    priority=2,
                    description="Validate recovery procedures and documentation",
                    expected_duration_minutes=40,
                    tools_needed=["Recovery runbooks", "RTO/RPO requirements"],
                    success_criteria="Confirm procedures are current and tested"
                ),
                InvestigationStep(
                    priority=3,
                    description="Test actual recovery process for critical systems",
                    expected_duration_minutes=120,
                    tools_needed=["Test environment", "Recovery tools"],
                    success_criteria="Validate recovery capability and measure actual RTO"
                )
            ]
        
        else:  # DATA_QUALITY
            return [
                InvestigationStep(
                    priority=1,
                    description="Review data validation and integrity checks",
                    expected_duration_minutes=25,
                    tools_needed=["Backup verification reports", "Integrity check logs"],
                    success_criteria="Understand current validation coverage"
                ),
                InvestigationStep(
                    priority=2,
                    description="Analyze historical data quality metrics",
                    expected_duration_minutes=30,
                    tools_needed=["Quality metrics database", "Trend analysis tools"],
                    success_criteria="Identify patterns in data quality issues"
                ),
                InvestigationStep(
                    priority=3,
                    description="Validate backup chain integrity",
                    expected_duration_minutes=35,
                    tools_needed=["Veeam Console", "Backup chain reports"],
                    success_criteria="Confirm backup chains are complete and valid"
                )
            ]
    
    def _generate_remediation_options(self, risk_type: RiskType, risk_data: Dict) -> List[RemediationOption]:
        """Generate remediation options with considerations (NOT prescriptions)"""
        
        options = []
        
        if risk_type == RiskType.JOB_FAILURE:
            options = [
                RemediationOption(
                    option_id=str(uuid.uuid4()),
                    name="Review and adjust job configuration",
                    description="Evaluate current settings against best practices and adjust as appropriate for your environment",
                    when_to_consider="When failure analysis suggests configuration mismatch with job requirements",
                    typical_effort_hours=1.5,
                    complexity=ComplexityLevel.LOW.value,
                    prerequisites=[
                        "Job idle period for testing",
                        "Current configuration documented",
                        "Rollback plan defined"
                    ],
                    risks=[
                        "Changes may affect dependent jobs",
                        "Incorrect settings could worsen issues"
                    ],
                    verification_steps=[
                        "Monitor next 3 job executions",
                        "Compare duration and success rate",
                        "Validate no negative impact on related jobs"
                    ],
                    guidance_notes=[
                        "Consider appropriate retry count for your environment",
                        "Balance retry count with job window constraints",
                        "Test changes during maintenance window if possible"
                    ]
                ),
                RemediationOption(
                    option_id=str(uuid.uuid4()),
                    name="Investigate and address infrastructure issues",
                    description="Identify and resolve underlying infrastructure problems causing failures",
                    when_to_consider="When failures correlate with infrastructure events or performance degradation",
                    typical_effort_hours=4.0,
                    complexity=ComplexityLevel.HIGH.value,
                    prerequisites=[
                        "Infrastructure team engagement",
                        "Performance baseline established",
                        "Maintenance window scheduled"
                    ],
                    risks=[
                        "Infrastructure changes may have broad impact",
                        "Root cause may be complex and time-consuming"
                    ],
                    verification_steps=[
                        "Monitor infrastructure metrics during backup window",
                        "Validate correlation between infrastructure health and job success",
                        "Conduct controlled test of infrastructure improvements"
                    ],
                    guidance_notes=[
                        "Coordinate with infrastructure teams for holistic investigation",
                        "Consider phased approach for complex infrastructure issues",
                        "Document findings for future reference"
                    ]
                ),
                RemediationOption(
                    option_id=str(uuid.uuid4()),
                    name="Optimize backup timing and resource allocation",
                    description="Review and adjust backup scheduling and resource allocation",
                    when_to_consider="When resource contention or timing conflicts are suspected",
                    typical_effort_hours=2.0,
                    complexity=ComplexityLevel.MEDIUM.value,
                    prerequisites=[
                        "Understanding of backup schedule",
                        "Resource utilization data",
                        "Business window requirements"
                    ],
                    risks=[
                        "Schedule changes may conflict with business operations",
                        "Resource reallocation may impact other jobs"
                    ],
                    verification_steps=[
                        "Monitor resource utilization after changes",
                        "Validate backup completion within business window",
                        "Confirm no conflicts with other operations"
                    ],
                    guidance_notes=[
                        "Consider staggering backup start times",
                        "Evaluate resource allocation based on job priority",
                        "Balance backup window with business requirements"
                    ]
                )
            ]
        
        elif risk_type == RiskType.CAPACITY:
            options = [
                RemediationOption(
                    option_id=str(uuid.uuid4()),
                    name="Optimize storage efficiency features",
                    description="Evaluate and enable appropriate deduplication, compression, and archiving",
                    when_to_consider="When analysis shows low efficiency feature utilization",
                    typical_effort_hours=2.5,
                    complexity=ComplexityLevel.MEDIUM.value,
                    prerequisites=[
                        "Storage compatibility verified",
                        "Performance impact understood",
                        "Testing environment available"
                    ],
                    risks=[
                        "Performance impact on backup/restore operations",
                        "Compatibility issues with certain data types"
                    ],
                    verification_steps=[
                        "Monitor storage efficiency gains",
                        "Validate no performance degradation",
                        "Confirm data integrity after changes"
                    ],
                    guidance_notes=[
                        "Consider appropriate efficiency settings for your data types",
                        "Test efficiency features in non-production first",
                        "Monitor both storage savings and performance impact"
                    ]
                ),
                RemediationOption(
                    option_id=str(uuid.uuid4()),
                    name="Review and adjust retention policies",
                    description="Align retention policies with actual business and compliance needs",
                    when_to_consider="When retention exceeds documented business requirements",
                    typical_effort_hours=3.0,
                    complexity=ComplexityLevel.MEDIUM.value,
                    prerequisites=[
                        "Business requirements documented",
                        "Compliance requirements understood",
                        "Data classification completed"
                    ],
                    risks=[
                        "Over-aggressive retention reduction may violate requirements",
                        "Users may expect longer retention than documented"
                    ],
                    verification_steps=[
                        "Validate business units accept new retention periods",
                        "Monitor storage reclamation",
                        "Confirm no restoration requests fail due to retention changes"
                    ],
                    guidance_notes=[
                        "Balance storage savings with business continuity needs",
                        "Consider tiered retention (short-term vs archive)",
                        "Communicate changes to stakeholders before implementation"
                    ]
                ),
                RemediationOption(
                    option_id=str(uuid.uuid4()),
                    name="Plan storage capacity expansion",
                    description="Develop and execute storage expansion plan",
                    when_to_consider="When optimization alone cannot meet capacity needs",
                    typical_effort_hours=8.0,
                    complexity=ComplexityLevel.HIGH.value,
                    prerequisites=[
                        "Budget approval obtained",
                        "Hardware procurement timeline understood",
                        "Expansion plan documented"
                    ],
                    risks=[
                        "Lead time for hardware procurement",
                        "Integration complexity with existing infrastructure"
                    ],
                    verification_steps=[
                        "Validate new capacity available and accessible",
                        "Confirm integration with backup infrastructure",
                        "Test backup operations with expanded capacity"
                    ],
                    guidance_notes=[
                        "Plan for future growth beyond immediate needs",
                        "Consider scalability and flexibility in expansion design",
                        "Coordinate with infrastructure and procurement teams"
                    ]
                )
            ]
        
        elif risk_type == RiskType.EFFICIENCY:
            options = [
                RemediationOption(
                    option_id=str(uuid.uuid4()),
                    name="Enable or optimize deduplication",
                    description="Review deduplication settings and enable if not active",
                    when_to_consider="When deduplication is disabled or suboptimally configured",
                    typical_effort_hours=2.0,
                    complexity=ComplexityLevel.MEDIUM.value,
                    prerequisites=[
                        "Repository supports deduplication",
                        "Performance impact acceptable",
                        "Test environment available"
                    ],
                    risks=[
                        "CPU overhead during backup operations",
                        "Initial deduplication may take longer"
                    ],
                    verification_steps=[
                        "Monitor deduplication ratios",
                        "Validate backup duration acceptable",
                        "Confirm storage savings achieved"
                    ],
                    guidance_notes=[
                        "Consider block size appropriate for your data",
                        "Monitor CPU utilization during backups",
                        "Allow time for deduplication to show full benefit"
                    ]
                ),
                RemediationOption(
                    option_id=str(uuid.uuid4()),
                    name="Adjust compression settings",
                    description="Review and optimize compression level for data types",
                    when_to_consider="When compression ratios are below expected for data type",
                    typical_effort_hours=1.5,
                    complexity=ComplexityLevel.LOW.value,
                    prerequisites=[
                        "Understanding of data types backed up",
                        "Compression level options understood",
                        "Test job available"
                    ],
                    risks=[
                        "Higher compression may increase backup duration",
                        "Some data types don't compress well"
                    ],
                    verification_steps=[
                        "Monitor compression ratios after changes",
                        "Validate backup duration remains acceptable",
                        "Confirm restore performance not degraded"
                    ],
                    guidance_notes=[
                        "Balance compression level with backup window",
                        "Consider data type characteristics",
                        "Test different compression levels to find optimal"
                    ]
                ),
                RemediationOption(
                    option_id=str(uuid.uuid4()),
                    name="Review backup mode and job design",
                    description="Evaluate if backup mode (full/incremental) is optimal",
                    when_to_consider="When job design may not be optimal for efficiency",
                    typical_effort_hours=3.0,
                    complexity=ComplexityLevel.MEDIUM.value,
                    prerequisites=[
                        "Understanding of backup modes",
                        "Business requirements for recovery",
                        "Test environment for validation"
                    ],
                    risks=[
                        "Job redesign may affect recovery procedures",
                        "Change in backup patterns"
                    ],
                    verification_steps=[
                        "Validate efficiency improvements",
                        "Confirm recovery capability maintained",
                        "Test restore from new backup design"
                    ],
                    guidance_notes=[
                        "Consider incremental vs full backup trade-offs",
                        "Evaluate synthetic full vs active full",
                        "Align with recovery time objectives"
                    ]
                )
            ]
        
        elif risk_type == RiskType.RECOVERY:
            options = [
                RemediationOption(
                    option_id=str(uuid.uuid4()),
                    name="Implement or enhance SureBackup testing",
                    description="Configure SureBackup for automated recovery verification",
                    when_to_consider="When recovery testing is insufficient or not automated",
                    typical_effort_hours=4.0,
                    complexity=ComplexityLevel.MEDIUM.value,
                    prerequisites=[
                        "SureBackup infrastructure available",
                        "Test network configured",
                        "Application verification scripts prepared"
                    ],
                    risks=[
                        "Resource overhead for test environment",
                        "False positives from test configuration"
                    ],
                    verification_steps=[
                        "Validate SureBackup jobs running successfully",
                        "Review test results for accuracy",
                        "Confirm coverage of critical systems"
                    ],
                    guidance_notes=[
                        "Start with critical systems first",
                        "Develop application-specific verification tests",
                        "Schedule testing during off-peak hours"
                    ]
                ),
                RemediationOption(
                    option_id=str(uuid.uuid4()),
                    name="Conduct manual recovery testing",
                    description="Perform controlled recovery tests for critical systems",
                    when_to_consider="When automated testing not feasible or comprehensive validation needed",
                    typical_effort_hours=6.0,
                    complexity=ComplexityLevel.HIGH.value,
                    prerequisites=[
                        "Test environment available",
                        "Recovery procedures documented",
                        "Business stakeholder coordination"
                    ],
                    risks=[
                        "Time-intensive process",
                        "Requires coordination across teams"
                    ],
                    verification_steps=[
                        "Document actual recovery time",
                        "Validate application functionality post-recovery",
                        "Update recovery procedures based on findings"
                    ],
                    guidance_notes=[
                        "Schedule during maintenance windows",
                        "Document every step of recovery process",
                        "Involve application teams in validation"
                    ]
                ),
                RemediationOption(
                    option_id=str(uuid.uuid4()),
                    name="Review and update recovery procedures",
                    description="Validate and update recovery documentation and procedures",
                    when_to_consider="When procedures are outdated or untested",
                    typical_effort_hours=3.0,
                    complexity=ComplexityLevel.LOW.value,
                    prerequisites=[
                        "Current recovery documentation",
                        "Access to recovery tools",
                        "Understanding of current infrastructure"
                    ],
                    risks=[
                        "Procedures may not reflect current reality",
                        "Gaps in documentation may be discovered"
                    ],
                    verification_steps=[
                        "Validate procedures against actual infrastructure",
                        "Test procedures in non-production",
                        "Obtain stakeholder review and approval"
                    ],
                    guidance_notes=[
                        "Include screenshots and detailed steps",
                        "Document dependencies and prerequisites",
                        "Establish regular review schedule"
                    ]
                )
            ]
        
        else:  # DATA_QUALITY
            options = [
                RemediationOption(
                    option_id=str(uuid.uuid4()),
                    name="Enhance backup verification processes",
                    description="Implement or improve backup integrity verification",
                    when_to_consider="When data quality concerns exist",
                    typical_effort_hours=2.5,
                    complexity=ComplexityLevel.MEDIUM.value,
                    prerequisites=[
                        "Understanding of current verification",
                        "Verification tools available",
                        "Performance impact acceptable"
                    ],
                    risks=[
                        "Verification may increase backup duration",
                        "May discover existing issues"
                    ],
                    verification_steps=[
                        "Monitor verification success rates",
                        "Review verification logs",
                        "Validate no performance degradation"
                    ],
                    guidance_notes=[
                        "Consider verification frequency appropriate for data criticality",
                        "Balance thoroughness with performance impact",
                        "Establish baseline for normal verification results"
                    ]
                ),
                RemediationOption(
                    option_id=str(uuid.uuid4()),
                    name="Review and improve monitoring",
                    description="Enhance monitoring of backup quality metrics",
                    when_to_consider="When visibility into data quality is insufficient",
                    typical_effort_hours=3.0,
                    complexity=ComplexityLevel.MEDIUM.value,
                    prerequisites=[
                        "Monitoring tools available",
                        "Metrics defined",
                        "Alerting infrastructure ready"
                    ],
                    risks=[
                        "Alert fatigue from too many notifications",
                        "Monitoring overhead"
                    ],
                    verification_steps=[
                        "Validate metrics are being collected",
                        "Confirm alerts are actionable",
                        "Review monitoring effectiveness"
                    ],
                    guidance_notes=[
                        "Focus on actionable metrics",
                        "Establish baselines before alerting",
                        "Tune alert thresholds based on experience"
                    ]
                ),
                RemediationOption(
                    option_id=str(uuid.uuid4()),
                    name="Investigate and resolve specific quality issues",
                    description="Address identified data quality problems",
                    when_to_consider="When specific quality issues have been identified",
                    typical_effort_hours=4.0,
                    complexity=ComplexityLevel.HIGH.value,
                    prerequisites=[
                        "Issues clearly identified",
                        "Root cause analysis completed",
                        "Resolution approach defined"
                    ],
                    risks=[
                        "Resolution may require infrastructure changes",
                        "Issue may be symptom of larger problem"
                    ],
                    verification_steps=[
                        "Confirm issue resolved",
                        "Monitor for recurrence",
                        "Validate no new issues introduced"
                    ],
                    guidance_notes=[
                        "Address root cause, not just symptoms",
                        "Document resolution for future reference",
                        "Consider preventive measures"
                    ]
                )
            ]
        
        # Limit to configured maximum
        max_options = self.config['plan_generation']['remediation_options_count']
        return options[:max_options]
    
    def _define_success_criteria(self, risk_type: RiskType, risk_data: Dict) -> SuccessCriteria:
        """Define success criteria for remediation"""
        
        score = risk_data['composite_risk_score']
        
        if risk_type == RiskType.JOB_FAILURE:
            if score >= 70:
                target = "<5%"
                duration = "14 consecutive days"
            else:
                target = "<10%"
                duration = "7 consecutive days"
            
            return SuccessCriteria(
                metrics=[
                    {"metric": "failure_rate", "target": target, "duration": duration},
                    {"metric": "job_duration", "target": "no increase >20%", "duration": "3 executions"}
                ],
                verification_method="Automated monitoring with manual review",
                timeframe="1-2 weeks post-implementation",
                fallback_plan="Revert changes and investigate alternative approaches"
            )
        
        elif risk_type == RiskType.CAPACITY:
            return SuccessCriteria(
                metrics=[
                    {"metric": "growth_rate", "target": "reduced by 30-50%", "duration": "30 days"},
                    {"metric": "time_to_80_percent", "target": "increased by 60+ days", "duration": "projection"}
                ],
                verification_method="Weekly capacity reports and performance monitoring",
                timeframe="30-day evaluation period",
                fallback_plan="Disable efficiency features and schedule capacity expansion"
            )
        
        elif risk_type == RiskType.EFFICIENCY:
            return SuccessCriteria(
                metrics=[
                    {"metric": "dedup_ratio", "target": "improvement of 20%+", "duration": "30 days"},
                    {"metric": "compression_ratio", "target": "improvement of 15%+", "duration": "30 days"},
                    {"metric": "backup_duration", "target": "no increase >15%", "duration": "7 days"}
                ],
                verification_method="Efficiency reports and performance monitoring",
                timeframe="30-day evaluation period",
                fallback_plan="Revert to previous settings if performance degraded"
            )
        
        elif risk_type == RiskType.RECOVERY:
            return SuccessCriteria(
                metrics=[
                    {"metric": "test_coverage", "target": ">80% of critical systems", "duration": "90 days"},
                    {"metric": "test_success_rate", "target": ">95%", "duration": "ongoing"},
                    {"metric": "rto_confidence", "target": "HIGH confidence level", "duration": "90 days"}
                ],
                verification_method="SureBackup reports and manual test results",
                timeframe="90-day implementation period",
                fallback_plan="Escalate to senior administration for resource allocation"
            )
        
        else:  # DATA_QUALITY
            return SuccessCriteria(
                metrics=[
                    {"metric": "verification_success_rate", "target": ">98%", "duration": "30 days"},
                    {"metric": "quality_score", "target": "improvement to MODERATE+", "duration": "60 days"}
                ],
                verification_method="Verification reports and quality metrics",
                timeframe="60-day evaluation period",
                fallback_plan="Conduct comprehensive backup infrastructure review"
            )
    
    def _calculate_estimated_effort(self, investigation_steps: List[InvestigationStep], 
                                   remediation_options: List[RemediationOption]) -> float:
        """Calculate total estimated effort in hours"""
        
        investigation_hours = sum(step.expected_duration_minutes for step in investigation_steps) / 60
        
        # Use minimum option effort (most conservative estimate)
        remediation_hours = min(option.typical_effort_hours for option in remediation_options) if remediation_options else 0
        
        # Add 30% contingency
        total = investigation_hours + remediation_hours
        return round(total * 1.3, 1)
    
    def _determine_urgency(self, risk_data: Dict) -> UrgencyLevel:
        """Determine urgency level based on risk score and business impact"""
        
        risk_score = risk_data['composite_risk_score']
        impact_score = risk_data['business_impact_score']
        
        if risk_score >= 80 or impact_score >= 80:
            return UrgencyLevel.CRITICAL
        elif risk_score >= 60 or impact_score >= 60:
            return UrgencyLevel.HIGH
        elif risk_score >= 40:
            return UrgencyLevel.MEDIUM
        else:
            return UrgencyLevel.LOW
    
    def _determine_complexity(self, risk_data: Dict, risk_type: RiskType) -> ComplexityLevel:
        """Determine complexity level"""
        
        # Capacity and Recovery tend to be more complex
        if risk_type in [RiskType.CAPACITY, RiskType.RECOVERY]:
            return ComplexityLevel.MEDIUM
        
        # High risk scores suggest complex issues
        if risk_data['composite_risk_score'] >= 70:
            return ComplexityLevel.HIGH
        elif risk_data['composite_risk_score'] >= 50:
            return ComplexityLevel.MEDIUM
        else:
            return ComplexityLevel.LOW
    
    def _generate_prerequisites(self, risk_data: Dict, options: List[RemediationOption]) -> List[str]:
        """Generate prerequisites for the plan"""
        
        prerequisites = [
            "Recent successful backup available",
            "Maintenance window identified if changes needed",
            "Rollback plan documented"
        ]
        
        # Tier-specific prerequisites
        vm_tier = risk_data.get('vm_tier', 'MEDIUM')
        if vm_tier in ['CRITICAL', 'HIGH']:
            prerequisites.append("Change approval from infrastructure architect")
            prerequisites.append("Business stakeholder notification completed")
        
        # Collect unique prerequisites from options
        for option in options:
            prerequisites.extend(option.prerequisites)
        
        # Deduplicate
        return list(set(prerequisites))
    
    def _generate_warnings(self, risk_data: Dict) -> List[str]:
        """Generate warnings for the plan"""
        
        warnings = [
            "This is guidance only - human review and approval required before any changes",
            "Verify all prerequisites are met before proceeding"
        ]
        
        # Risk-specific warnings
        vm_tier = risk_data.get('vm_tier', 'MEDIUM')
        if vm_tier in ['CRITICAL', 'HIGH']:
            warnings.append("CRITICAL/HIGH tier system - coordinate changes with business stakeholders")
        
        confidence = self._map_confidence(risk_data.get('overall_data_confidence', 0.5))
        if confidence in ['LOW', 'INSUFFICIENT']:
            warnings.append("Low confidence in risk assessment - validate issue before proceeding")
        
        return warnings
    
    def _generate_json_output(self, plan: RemediationPlan) -> Dict:
        """Generate JSON output for the plan"""
        
        return {
            "plan_id": plan.plan_id,
            "generated_at": plan.generated_at.isoformat(),
            "risk_context": {
                "risk_id": plan.risk_id,
                "risk_type": plan.risk_type,
                "job_id": plan.job_id,
                "job_name": plan.job_name,
                "vm_tier": plan.vm_tier,
                "composite_risk_score": plan.composite_risk_score,
                "business_impact_score": plan.business_impact_score,
                "confidence_level": plan.confidence_level
            },
            "issue_summary": plan.issue_summary,
            "pattern_analysis": plan.pattern_analysis,
            "root_cause_hypotheses": plan.root_cause_hypotheses,
            "investigation_steps": [
                {
                    "priority": step.priority,
                    "description": step.description,
                    "expected_duration_minutes": step.expected_duration_minutes,
                    "tools_needed": step.tools_needed,
                    "success_criteria": step.success_criteria
                }
                for step in plan.investigation_steps
            ],
            "remediation_options": [
                {
                    "option_id": opt.option_id,
                    "name": opt.name,
                    "description": opt.description,
                    "when_to_consider": opt.when_to_consider,
                    "typical_effort_hours": opt.typical_effort_hours,
                    "complexity": opt.complexity,
                    "prerequisites": opt.prerequisites,
                    "risks": opt.risks,
                    "verification_steps": opt.verification_steps,
                    "guidance_notes": opt.guidance_notes
                }
                for opt in plan.remediation_options
            ],
            "success_criteria": {
                "metrics": plan.success_criteria.metrics,
                "verification_method": plan.success_criteria.verification_method,
                "timeframe": plan.success_criteria.timeframe,
                "fallback_plan": plan.success_criteria.fallback_plan
            },
            "estimated_total_effort_hours": plan.estimated_effort_hours,
            "urgency": plan.urgency,
            "complexity": plan.complexity,
            "prerequisites": plan.prerequisites,
            "warnings": plan.warnings,
            "metadata": {
                "plan_version": "1.0",
                "generator": "Feature6GuidanceEngine",
                "safety_note": "GUIDANCE ONLY - NO AUTOMATED EXECUTION"
            }
        }
    
    def _store_plans_in_database(self, conn, plans: List[RemediationPlan]):
        """Store plans in database for audit trail"""
        
        cur = conn.cursor()
        
        for plan in plans:
            try:
                cur.execute("""
                    INSERT INTO dr365v.remediation_plans
                    (plan_id, risk_id, risk_type, job_id, job_name, vm_tier,
                     composite_risk_score, business_impact_score, confidence_level,
                     issue_summary, pattern_analysis, root_cause_hypotheses,
                     investigation_steps, remediation_options, success_criteria,
                     urgency, estimated_effort_hours, complexity,
                     prerequisites, warnings, plan_json, generated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (job_id, risk_type) 
                    DO UPDATE SET
                        composite_risk_score = EXCLUDED.composite_risk_score,
                        business_impact_score = EXCLUDED.business_impact_score,
                        confidence_level = EXCLUDED.confidence_level,
                        issue_summary = EXCLUDED.issue_summary,
                        pattern_analysis = EXCLUDED.pattern_analysis,
                        root_cause_hypotheses = EXCLUDED.root_cause_hypotheses,
                        investigation_steps = EXCLUDED.investigation_steps,
                        remediation_options = EXCLUDED.remediation_options,
                        success_criteria = EXCLUDED.success_criteria,
                        urgency = EXCLUDED.urgency,
                        estimated_effort_hours = EXCLUDED.estimated_effort_hours,
                        complexity = EXCLUDED.complexity,
                        prerequisites = EXCLUDED.prerequisites,
                        warnings = EXCLUDED.warnings,
                        plan_json = EXCLUDED.plan_json,
                        generated_at = EXCLUDED.generated_at
                """, (
                    plan.plan_id,
                    plan.risk_id,
                    plan.risk_type,
                    plan.job_id,
                    plan.job_name,
                    plan.vm_tier,
                    plan.composite_risk_score,
                    plan.business_impact_score,
                    plan.confidence_level,
                    plan.issue_summary,
                    plan.pattern_analysis,
                    plan.root_cause_hypotheses,
                    json.dumps([asdict(step) for step in plan.investigation_steps]),
                    json.dumps([asdict(opt) for opt in plan.remediation_options]),
                    plan.success_criteria.metrics[0]['metric'] if plan.success_criteria.metrics else '',
                    plan.urgency,
                    plan.estimated_effort_hours,
                    plan.complexity,
                    plan.prerequisites,
                    plan.warnings,
                    json.dumps(plan.plan_json),
                    plan.generated_at
                ))
            except Exception as e:
                self.logger.error(f"Failed to store plan {plan.plan_id}: {e}")
                continue
        
        conn.commit()
        cur.close()
        self.logger.info(f"Stored {len(plans)} plans in database")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function"""
    
    try:
        # Initialize and run guidance engine
        engine = Feature6GuidanceEngine()
        plans = engine.generate_remediation_plans()
        
        print(f"\nSuccessfully generated {len(plans)} remediation plans")
        
        # Print summary
        if plans:
            print("\n" + "="*80)
            print("REMEDIATION PLANS SUMMARY:")
            print("="*80)
            for plan in plans:
                print(f"\nPlan ID: {plan.plan_id}")
                print(f"Job: {plan.job_name}")
                print(f"Risk Type: {plan.risk_type}")
                print(f"Urgency: {plan.urgency}")
                print(f"Estimated Effort: {plan.estimated_effort_hours} hours")
                print(f"Options: {len(plan.remediation_options)}")
            print("="*80)
        
    except Exception as e:
        logger.error(f"Feature 6 execution failed: {e}")
        raise


if __name__ == "__main__":
    main()
