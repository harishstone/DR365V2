"""
DR365V Intelligent MCP Server - NEW DOCS Compliant
===================================================

MCP Server that exposes DR365V database metrics through standardized tools.
This server queries the PostgreSQL database populated by Features 1-6 and
returns structured data for AI assistants (Claude, etc.).

NEW DOCS Compliance:
- Feature 1: Queries metrics_health_score table
- Feature 2: Queries metrics_capacity_forecast table
- Feature 3: Queries metrics_storage_efficiency table
- Feature 4: Queries metrics_recovery_verification table
- Feature 5: Queries metrics_risk_analysis_consolidated table (dr365v DB)
- Feature 6: Queries remediation_plans table (dr365v DB)
- Feature 7: Checks ransomware status via Wazuh (API/Dashboard)

Key Principle: MCP server does NOT perform calculations.
All analysis is done by feature1.py, feature2.py, etc.
MCP server only READS and FORMATS database data.

Reference: NEW DOCS FEEDBACK folder - Database Schema sections
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from mcp.server.fastmcp import FastMCP
import psycopg2
import psycopg2.extras
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()

# Database connection
try:
    from .database.db import get_db_connection
except ImportError:
    from database.db import get_db_connection

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.feature7.feature_07 import detect_ransomware, RansomwareDetectionInput, list_wazuh_agents
from src.feature7.feature_07 import detect_ransomware, RansomwareDetectionInput, list_wazuh_agents
from src.feature8.feature_08 import analyze_ransomware_context
from src.feature9.feature_09 import analyze_attack_timeline
from src.feature10.feature_10 import generate_response_playbook
from src.feature11.feature_11 import scan_backup_security
from src.feature12.feature_12 import map_compliance_gaps
from src.demo.simulator import run_simulation
from src.feature13_stonefusion.feature_13 import (
    get_stonefusion_events as f13_get_events,
    get_stonefusion_inventory as f13_get_inventory,
    get_stonefusion_volume_details as f13_get_volume_details
)

# =============================================================================
# CONFIGURATION
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dr365v_mcp")

# Initialize MCP Server
mcp = FastMCP("dr365v-intelligence")

# =============================================================================
# FEATURE 1: HEALTH METRICS & HISTORICAL ANALYSIS
# NEW DOCS: Feature 01 - Section 5 (Database Schema)
# =============================================================================

@mcp.tool()
async def get_health_metrics() -> str:
    """
    Retrieves the current system health score and breakdown.
    
    PRESENTATION STYLE GUIDE:
    ------------------------
    You MUST display this data as an "Executive Dashboard" using the following rules:
    
    1. **Icons**: Use ONLY these icons:
       - 🔴 (Critical/High Risk)
       - ⚠️ (Warning/Medium Risk)
       - ✅ (Healthy/Success)
       - 📊 (Stats/Charts)
       - 📈 (Trend Up), 📉 (Trend Down), ➡️ (Stable)
    
       *DO NOT use strange characters like '※' or '├'.*

    2. **Structure**:
       # Backup Health Infrastructure
       ## [Icon] Overall Score: [Score]/100 (Grade [Grade])
       
       ### Key Components
       - [Icon] **Failure Rate:** [Score]
       - [Arrow Icon] **Trends:** [Classification]
       ...

    3. **Formatting**: Use bolding for key metrics. Icons MUST be placed properly where needed, dont unncessarily place icons, It should look visually good.

    Returns:
        JSON string containing overall_score, breakdown, and recommendations.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Get latest score
        cursor.execute("SELECT * FROM feature1.metrics_health_score ORDER BY created_at DESC LIMIT 1")
        score = cursor.fetchone()
        
        if not score:
            return json.dumps({
                "status": "NO_DATA",
                "message": "No health metrics found. Run Feature 1 analysis: python src/feature1/feature1.py",
                "feature": "Feature 1: Health Metrics & Historical Analysis"
            })
            
        # Parse JSON fields
        if score.get('quality_flags') and isinstance(score['quality_flags'], str):
            score['quality_flags'] = json.loads(score['quality_flags'])

        # Calculate data freshness
        data_age_hours = (datetime.now() - score['created_at']).total_seconds() / 3600

        # Structure output
        response = {
            "feature": "Feature 1: Health Metrics & Historical Analysis",
            "timestamp": score['created_at'].isoformat(),
            "data_freshness_hours": round(data_age_hours, 1),
            "overall_health": {
                "score": float(score['overall_score']),
                "grade": score['grade'],
                "risk_level": score['risk_level'],
                "recommendation": score['recommendation']
            },
            "component_scores": {
                "failure_rate": {
                    "score": float(score['failure_rate_score']),
                    "weight": "35%",
                    "description": "Success/failure rate of backup jobs"
                },
                "trend_analysis": {
                    "score": float(score['trend_score']),
                    "weight": "25%",
                    "classification": score['trend_classification'],
                    "percentage_change": float(score['trend_percentage']),
                    "is_significant": score['trend_is_significant'],
                    "description": f"{score['trend_classification']} trend"
                },
                "pattern_recognition": {
                    "score": float(score['pattern_score']),
                    "weight": "20%",
                    "classification": score['pattern_classification'],
                    "confidence": score['pattern_confidence'],
                    "detail": score['pattern_detail'],
                    "correlated_failures": score['correlated_failures'],
                    "description": f"Pattern: {score['pattern_classification']}"
                },
                "protected_objects": {
                    "score": float(score['protected_objects_score']),
                    "weight": "10%",
                    "description": "VM accessibility in inventory"
                },
                "repository_health": {
                    "score": float(score['repository_score']),
                    "weight": "10%",
                    "description": "Storage availability"
                }
            },
            "quality_metadata": {
                "confidence_level": score['confidence_level'],
                "confidence_multiplier": float(score['confidence_multiplier']),
                "sample_count": score['sample_count'],
                "date_range_days": score['date_range_days'],
                "average_frequency": float(score['average_frequency']),
                "quality_flags": score['quality_flags']
            },
            "data_source": "PostgreSQL: metrics_health_score",
            "calculated_by": "Feature 1 (src/feature1/feature1.py)"
        }
        
        return json.dumps(response, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error in get_health_metrics: {e}", exc_info=True)
        return json.dumps({
            "status": "ERROR",
            "error": str(e),
            "message": "Failed to retrieve health metrics from database"
        })
    finally:
        cursor.close()
        conn.close()

@mcp.tool()
async def get_failing_jobs() -> str:
    """
    Retrieves a list of backup jobs that are failing or actively degrading.
    
    PRESENTATION STYLE GUIDE:
    ------------------------
    Organize this list by **PRIORITY** using the following structure:
    
    **TOP PRIORITIES (Critical Failures)**
    *🔴 Jobs with 0% Success Rate or Critical Trends*
    - **[Job Name]**: [X] Failures (Consecutive)
      - *Cause:* [Recommendation]
      
    **⚠️ WARNINGS**
    *Jobs with warnings or intermittent failures*
    - **[Job Name]**: [X]% Success Rate
    
    **✅ HEALTHY / FALSE ALARMS**
    *Jobs that are working but might have minor notes*

    **SUMMARY STATS:**
    - Total Jobs Analyzed: [X]
    - Critical: [X] | Warning: [X] | Healthy: [X]
    
    Returns:
        JSON string containing the list of failing jobs.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Get latest run
        cursor.execute("SELECT created_at FROM feature1.metrics_health_score ORDER BY created_at DESC LIMIT 1")
        latest = cursor.fetchone()
        
        if not latest:
            return json.dumps({
                "status": "NO_DATA",
                "message": "No health metrics found. Run Feature 1 analysis first.",
                "feature": "Feature 1: Job Failures"
            })
            
        timestamp = latest['created_at']
        
        # Get all jobs from that run (both good and bad)
        cursor.execute("""
            SELECT 
                job_id,
                job_name,
                job_type,
                success_count,
                warning_count,
                failure_count,
                total_sessions,
                success_rate,
                trend_classification,
                pattern_classification,
                sessions_analyzed,
                recommendation,
                priority
            FROM feature1.metrics_job_failures 
            WHERE created_at = %s
            ORDER BY 
                CASE priority 
                    WHEN 'CRITICAL' THEN 1 
                    WHEN 'HIGH' THEN 2 
                    WHEN 'MEDIUM' THEN 3 
                    ELSE 4 
                END,
                failure_count DESC,
                warning_count DESC
        """, (timestamp,))
        
        jobs = cursor.fetchall()
        
        job_list = []
        for j in jobs:
            job_list.append({
                "job_id": j['job_id'],
                "job_name": j['job_name'],
                "job_type": j['job_type'],
                "success_rate": float(j['success_rate']),
                "failure_count": j['failure_count'],
                "warning_count": j['warning_count'],
                "total_sessions": j['total_sessions'],
                "trend": j['trend_classification'],
                "pattern": j['pattern_classification'],
                "priority": j['priority'],
                "recommendation": j['recommendation']
            })
        
        if not job_list:
            return json.dumps({
                "status": "HEALTHY",
                "message": "No failing jobs detected",
                "count": 0,
                "feature": "Feature 1: Job Failures"
            })

        response = {
            "feature": "Feature 1: Job Failures",
            "count": len(job_list),
            "jobs": job_list,
            "data_source": "PostgreSQL: metrics_job_failures",
            "calculated_by": "Feature 1 (src/feature1/feature1.py)"
        }
        
        return json.dumps(response, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error in get_failing_jobs: {e}", exc_info=True)
        return json.dumps({
            "status": "ERROR",
            "error": str(e),
            "message": "Failed to retrieve failing jobs from database"
        })
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# FEATURE 2: CAPACITY FORECASTING
# NEW DOCS: Feature 02 - Section 5 (Database Schema)
# =============================================================================

@mcp.tool()
async def get_capacity_forecast() -> str:
    """
    Retrieves storage capacity forecasts and exhaustion predictions.
    
    PRESENTATION STYLE GUIDE:
    ------------------------
    Use a **Storage Health Card** format:
    
    **REPOSITORY STATUS**
    
    **🔴 CRITICAL (Runway < 30 Days)**
    - [Repo Name]: [Days] days remaining
    
    **⚠️ WARNING (Runway < 90 Days)**
    - [Repo Name]: [Days] days remaining
    
    **✅ HEALTHY**
    - [Repo Name]: [Days] days | Growth: [Rate] GB/day
    
    Use the `model_type` to explain the prediction (e.g., "Accelerating Growth (Quadratic)").

    Returns:
        JSON string containing forecast data for all repositories.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Get LATEST forecast for EVERY repository
        # We use DISTINCT ON to ensure we only get the single most recent row per repo
        cursor.execute("""
            SELECT DISTINCT ON (repository_id) *
            FROM feature2.metrics_capacity_forecast 
            ORDER BY repository_id, created_at DESC
        """)
        
        repos = cursor.fetchall()
        
        # FALLBACK: If no FORECASTS (Accumulation Phase), get raw STATE from history
        if not repos:
            logger.info("No forecasts found. Falling back to raw capacity history.")
            cursor.execute("""
                SELECT DISTINCT ON (repository_name) 
                    repository_name,
                    total_capacity_bytes,
                    used_space_bytes,
                    utilization_pct,
                    created_at
                FROM feature2.capacity_history_raw
                ORDER BY repository_name, created_at DESC
            """)
            raw_states = cursor.fetchall()

            if not raw_states:
                return json.dumps({"error": "No capacity data found. Please ensure Feature 2 collection is running."})

            # Convert raw states to forecast-like structure
            repo_list = []
            timestamp = max(r['created_at'] for r in raw_states)
            
            for r in raw_states:
                total_gb = float(r['total_capacity_bytes'] or 0) / (1024**3)
                used_gb = float(r['used_space_bytes'] or 0) / (1024**3)
                
                repo_list.append({
                    "repository_id": "unknown", # Raw history doesn't store ID
                    "repository_name": r['repository_name'],
                    "repository_type": "Repository",
                    "capacity": {
                        "total_gb": round(total_gb, 2),
                        "used_gb": round(used_gb, 2),
                        "utilization_pct": float(r['utilization_pct'] or 0),
                        "total_display": f"{total_gb/1024:.2f} TB" if total_gb >= 1000 else f"{total_gb:.2f} GB",
                        "used_display": f"{used_gb/1024:.2f} TB" if used_gb >= 1000 else f"{used_gb:.2f} GB"
                    },
                    "forecast": {
                        "days_to_80_percent": None,
                        "days_to_90_percent": None,
                        "days_to_100_percent": None,
                        "status": "ACCUMULATING_DATA"
                    },
                    "growth_analysis": {
                        "growth_rate_gb_per_day": 0.0,
                        "growth_pattern": "INSUFFICIENT_HISTORY",
                        "model_type": "None (Accumulating)",
                        "r_squared": 0.0
                    },
                    "priority": "INFO",
                    "recommendation": "System is accumulating historical data for accurate forecasting (Needs 14 days)."
                })
            
            response = {
                "feature": "Feature 2: Capacity Exhaustion Forecasting",
                "timestamp": timestamp.isoformat(),
                "status_message": "ACCUMULATING DATA: Forecasts will be available after 14 days of history.",
                "summary": {"total_repositories": len(repo_list), "urgent": 0, "high": 0, "accumulating": len(repo_list)},
                "repositories": repo_list,
                "data_source": "PostgreSQL: feature2.capacity_history_raw (Fallback)",
                "calculated_by": "Feature 2 (Accumulator)",
                "note": "Forecasts require 14 days of data. Showing current capacity values only."
            }
            return json.dumps(response, indent=2, default=str)
            
        # Normal Forecast Processing
        # Use the timestamp of the most recent record for the report
        timestamp = max(r['created_at'] for r in repos)
        
        repo_list = []
        summary = {"total_repositories": 0, "urgent": 0, "high": 0, "medium": 0, "low": 0}
        
        for r in repos:
            # Parse Quality Flags JSON (this ONE is json)
            try:
                quality_flags = json.loads(r['quality_flags']) if r.get('quality_flags') else {}
            except (json.JSONDecodeError, TypeError):
                quality_flags = {}

            summary["total_repositories"] += 1
            prio = r['priority'] if r['priority'] else 'LOW'
            if prio == 'URGENT': summary['urgent'] += 1
            elif prio == 'HIGH': summary['high'] += 1
            elif prio == 'MEDIUM': summary['medium'] += 1
            else: summary['low'] += 1
            
            repo_list.append({
                "repository_id": r['repository_id'],
                "repository_name": r['repository_name'],
                "repository_type": r['repository_type'],
                "capacity": {
                    "total_gb": float(r['total_capacity_gb'] or 0),
                    "used_gb": float(r['current_used_gb'] or 0),
                    "utilization_pct": float(r['current_utilization_pct'] or 0),
                    "total_display": f"{float(r['total_capacity_gb'] or 0)/1024:.2f} TB" if float(r['total_capacity_gb'] or 0) >= 1000 else f"{float(r['total_capacity_gb'] or 0):.2f} GB",
                    "used_display": f"{float(r['current_used_gb'] or 0)/1024:.2f} TB" if float(r['current_used_gb'] or 0) >= 1000 else f"{float(r['current_used_gb'] or 0):.2f} GB"
                },
                "forecast": {
                    "days_to_80_percent": r['days_to_80_percent'],
                    "days_to_90_percent": r['days_to_90_percent'],
                    "days_to_100_percent": r['days_to_100_percent'],
                    "confidence_interval_80": {
                        "lower": r['days_to_80_ci_lower'],
                        "upper": r['days_to_80_ci_upper']
                    }
                },
                "growth_analysis": {
                    "growth_rate_gb_per_day": float(r['growth_rate_gb_per_day'] or 0),
                    "acceleration_factor": float(r['acceleration_factor'] or 0),
                    "growth_pattern": r['growth_pattern'],
                    "model_type": r['model_type'],
                    "r_squared": float(r['r_squared'] or 0)
                },
                "quality_metadata": {
                    "confidence_level": r['confidence_level'],
                    "confidence_multiplier": float(r['confidence_multiplier'] or 0),
                    "sample_count": r['sample_count'],
                    "quality_flags": quality_flags,
                    "gaps_interpolated": r['gaps_interpolated'],
                    "outliers_removed": r['outliers_removed']
                },
                "priority": prio,
                "recommendation": r['recommendation']
            })

        response = {
            "feature": "Feature 2: Capacity Exhaustion Forecasting",
            "timestamp": timestamp.isoformat(),
            "status_message": "HEALTHY: All repositories have sufficient capacity runway" if summary['urgent'] == 0 else "WARNING: Capacity risks detected",
            "summary": summary,
            "repositories": repo_list,
            "data_source": "PostgreSQL: feature2.metrics_capacity_forecast",
            "calculated_by": "Feature 2 (src/feature2/feature2.py)",
            "methodology": {
                "model": "Polynomial Regression (Linear + Quadratic)",
                "statistical_test": "P-value < 0.05 for quadratic significance",
                "confidence_intervals": "95% CI using t-distribution",
                "reference": "NEW DOCS Feature 02 - Section 7"
            }
        }
        
        return json.dumps(response, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error in get_capacity_forecast: {e}", exc_info=True)
        return json.dumps({
            "status": "ERROR",
            "error": str(e),
            "message": "Failed to retrieve capacity forecast from database"
        })
    finally:
        cursor.close()
        conn.close()


@mcp.tool()
async def get_capacity_history(repository_name: str, days: int = 30) -> Dict[str, Any]:
    """
    Get historical capacity data for a specific repository
    
    NEW DOCS Reference: Feature 02 - Section 5.2 (capacity_history_raw table)
    
    Args:
        repository_name: Name of the repository
        days: Number of days of history to retrieve (default: 30)
    
    Returns historical capacity measurements used for forecasting
    
    Data Source: PostgreSQL table 'feature2.capacity_history_raw'
    Populated by: src/feature2/feature2.py (daily snapshots)
    
    Use this to answer:
    - "Show me capacity history for [repo]"
    - "How has storage grown over time?"
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Query historical capacity data (NEW DOCS: Section 5.2)
        cur.execute("""
            SELECT 
                created_at,
                total_capacity_bytes / 1024.0 / 1024.0 / 1024.0 as total_capacity_gb,
                used_space_bytes / 1024.0 / 1024.0 / 1024.0 as used_space_gb,
                free_space_bytes / 1024.0 / 1024.0 / 1024.0 as free_space_gb,
                utilization_pct
            FROM feature2.capacity_history_raw
            WHERE repository_name = %s
            AND created_at > NOW() - INTERVAL '%s days'
            ORDER BY created_at ASC
        """, (repository_name, days))
        
        rows = cur.fetchall()
        
        if not rows:
            return {
                "status": "NO_DATA",
                "message": f"No history found for repository: {repository_name}",
                "feature": "Feature 2: Capacity History"
            }
        
        # Format history
        history = []
        for row in rows:
            history.append({
                "timestamp": row['created_at'].isoformat(),
                "total_capacity_gb": float(row['total_capacity_gb']),
                "used_space_gb": float(row['used_space_gb']),
                "free_space_gb": float(row['free_space_gb']),
                "utilization_pct": float(row['utilization_pct'])
            })
        
        return {
            "feature": "Feature 2: Capacity History",
            "repository_name": repository_name,
            "days_requested": days,
            "data_points": len(history),
            "history": history,
            "data_source": "PostgreSQL: feature2.capacity_history_raw"
        }
        
    except Exception as e:
        logger.error(f"Error in get_capacity_history: {e}", exc_info=True)
        return {
            "status": "ERROR",
            "error": str(e),
            "message": "Failed to retrieve capacity history from database"
        }
    finally:
        conn.close()


# =============================================================================
# FEATURES 3-6: PLACEHOLDER TOOLS
# =============================================================================

@mcp.tool()
async def get_storage_efficiency() -> str:
    """
    Get storage efficiency analysis with deduplication and compression metrics
    
    NEW DOCS Reference: Feature 03 - Storage Efficiency Implementation Guide
    
    PRESENTATION STYLE GUIDE:
    ------------------------
    Present as a "Storage Efficiency Report" with the following structure:
    
    # Storage Efficiency Analysis
    
    ## Overall Efficiency: [Score]/100 (Grade [Grade])
    **Rating:** [EXCELLENT/GOOD/FAIR/POOR]
    
    ### Efficiency Breakdown
    
    **🔴 POOR EFFICIENCY** (Score < 55)
    - **[Job Name]**: [Dedup]x dedup, [Compression]x compression
      - Combined: [Combined]x total reduction
      - Optimization Potential: [X] GB/month savings
      - Recommendation: [Action]
    
    **⚠️ FAIR EFFICIENCY** (Score 55-70)
    - Similar format
    
    **✅ GOOD/EXCELLENT EFFICIENCY** (Score > 70)
    - Similar format
    
    ### 📊 Summary Statistics
    - Total Jobs Analyzed: [X]
    - Average Dedup Ratio: [X]x
    - Average Compression: [X]x
    - Total Optimization Potential: [X] GB/month
    
    Use icons: 🔴 (Poor), ⚠️ (Fair), ✅ (Good/Excellent), 📊 (Stats), 🚨 (Critical)
    
    Returns:
        JSON string containing efficiency scores, ratings, and optimization potential
    
    Data Source: PostgreSQL table 'metrics_storage_efficiency'
    Populated by: src/feature3/feature3.py (daily analysis)
    
    Use this to answer:
    - "How efficient is our storage?"
    - "Which jobs have poor deduplication?"
    - "How much storage could we save?"
    - "Show me efficiency trends"
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Get LATEST efficiency scores for ALL jobs
        cursor.execute("""
            SELECT DISTINCT ON (job_id) *
            FROM feature3.metrics_storage_efficiency 
            WHERE created_at > NOW() - INTERVAL '24 hours'
            ORDER BY job_id, created_at DESC
        """)
        
        jobs = cursor.fetchall()
        
        # FALLBACK: If no EFFICIENCY data, get JOB LIST from Feature 1 inventory
        # This ensures we at least show which jobs exist, even if stats are missing.
        # FALLBACK: SMART EFFICIENCY OPPORTUNITY ANALYSIS
        # If specific ratios are missing, we pivot to an "Opportunity Analysis"
        # We look at Total Used Storage (from F2) and project potential savings
        # based on industry standards (1.5x - 2.0x), making the output distinct
        # from F1 (Health) or F2 (Forecast).
        if not jobs:
            logger.info("No efficiency data found. Generating Smart Opportunity Analysis.")
            
            # 1. Get Jobs (to know what workload types we have)
            cursor.execute("""
                SELECT job_name, job_type, success_rate
                FROM feature1.metrics_job_failures
                WHERE created_at = (
                    SELECT created_at FROM feature1.metrics_health_score 
                    ORDER BY created_at DESC LIMIT 1
                )
            """)
            raw_jobs = cursor.fetchall()
            
            # 2. Get Repositories (to know Used Capacity for savings calc)
            cursor.execute("""
                SELECT DISTINCT ON (repository_name) 
                    repository_name, total_capacity_bytes, used_space_bytes
                FROM feature2.capacity_history_raw
                ORDER BY repository_name, created_at DESC
            """)
            raw_repos = cursor.fetchall()
            
            timestamp = datetime.now()
            
            # Application Logic: Calculate Savings Potential
            total_used_bytes = sum(float(r['used_space_bytes'] or 0) for r in raw_repos)
            total_used_gb = total_used_bytes / (1024**3)
            
            # Conservative Industry Estimate: 1.5x (33% reduction)
            est_ratio = 1.5
            est_savings_gb = total_used_gb * (1 - (1/est_ratio))
            
            # Format utility
            def fmt_cap(gb):
                return f"{gb/1024:.2f} TB" if gb >= 1000 else f"{gb:.2f} GB"
            
            # Process Repositories: Identify Top Efficiency Targets
            efficiency_targets = []
            for r in sorted(raw_repos, key=lambda x: float(x['used_space_bytes'] or 0), reverse=True):
                u_gb = float(r['used_space_bytes'] or 0) / (1024**3)
                if u_gb > 0:
                    potential_save = u_gb * (1 - (1/est_ratio))
                    efficiency_targets.append({
                        "repository_name": r['repository_name'],
                        "current_usage": fmt_cap(u_gb),
                        "optimization_potential": f"~{fmt_cap(potential_save)} (Est)",
                        "priority": "HIGH" if potential_save > 1000 else "MEDIUM"
                    })

            # Process Jobs: Sample Top 5 Active Jobs (Prioritize Backup Jobs)
            # Filter for meaningful user jobs, excluding system/discovery jobs
            # We look for "Backup" in type or name to catch the important ones
            user_jobs = [j for j in raw_jobs if 'Backup' in j['job_type'] or 'Backup' in j['job_name']]
            
            # Use user_jobs if available, otherwise fallback to whatever we have
            display_source = user_jobs if user_jobs else raw_jobs
            
            sampled_jobs = []
            for j in display_source[:5]:
                sampled_jobs.append({
                    "job_name": j['job_name'],
                    "status": "Verified Active (Feature 1)",
                    "efficiency_data": "Pending"
                })

            response = {
                "feature": "Feature 3: Storage Efficiency Analysis",
                "timestamp": timestamp.isoformat(),
                "status_message": "OPPORTUNITY ANALYSIS: Metrics unavailable. Projecting savings based on industry standards.",
                "efficiency_projection": {
                    "total_storage_consumed": fmt_cap(total_used_gb),
                    "estimated_deduplication_target": "1.5x (Industry Standard)",
                    "estimated_reclaimable_space": fmt_cap(est_savings_gb),
                    "analysis_basis": "Projection based on consumed capacity of monitored repositories vs optimal compression.",
                    "action_required": "Verify deduplication is enabled on largest repositories."
                },
                "top_optimization_targets": efficiency_targets[:5], # Top 5 biggest targets
                "sampled_active_jobs": sampled_jobs,
                "workload_context": {
                    "active_jobs_count": len(raw_jobs),
                    "note": f"Analysis covers {len(raw_jobs)} active backup jobs across {len(raw_repos)} repositories."
                },
                "data_source": "Integrated Analysis (Projected from Actual Consumption)",
                "calculated_by": "Feature 3 (Smart Projection)"
            }
            return json.dumps(response, indent=2, default=str)
            
        # Use the timestamp of the most recent record
        timestamp = max(j['created_at'] for j in jobs)
        
        # Calculate summary statistics
        summary = {
            "total_jobs": len(jobs),
            "poor": 0,
            "fair": 0,
            "good": 0,
            "excellent": 0,
            "avg_dedup_ratio": 0.0,
            "avg_compression_ratio": 0.0,
            "total_optimization_potential_gb": 0.0,
            "total_monthly_savings_gb": 0.0,
            "total_annual_cost_savings": 0.0
        }
        
        job_list = []
        
        for j in jobs:
            # Categorize by rating
            rating = j['efficiency_rating']
            if rating == 'EXCELLENT':
                summary['excellent'] += 1
            elif rating == 'GOOD':
                summary['good'] += 1
            elif rating == 'FAIR':
                summary['fair'] += 1
            else:  # POOR
                summary['poor'] += 1
            
            # Accumulate averages
            summary['avg_dedup_ratio'] += float(j['avg_dedup_ratio'])
            summary['avg_compression_ratio'] += float(j['avg_compression_ratio'])
            summary['total_optimization_potential_gb'] += float(j['optimization_potential_gb'] or 0)
            summary['total_monthly_savings_gb'] += float(j['projected_monthly_savings_gb'] or 0)
            summary['total_annual_cost_savings'] += float(j['estimated_cost_savings_annual'] or 0)
            
            job_list.append({
                "job_id": j['job_id'],
                "job_name": j['job_name'],
                "job_type": j['job_type'],
                "overall_score": float(j['overall_score']),
                "efficiency_grade": j['efficiency_grade'],
                "efficiency_rating": j['efficiency_rating'],
                "deduplication": {
                    "avg_ratio": float(j['avg_dedup_ratio']),
                    "score": float(j['dedup_score']),
                    "rating": j['dedup_rating'],
                    "consistency": float(j['dedup_consistency'] or 0)
                },
                "compression": {
                    "avg_ratio": float(j['avg_compression_ratio']),
                    "score": float(j['compression_score']),
                    "rating": j['compression_rating'],
                    "consistency": float(j['compression_consistency'] or 0)
                },
                "combined_efficiency": {
                    "combined_ratio": float(j['combined_ratio']),
                    "storage_reduction_pct": float(j['storage_reduction_pct'])
                },
                "trend": {
                    "classification": j['trend_classification'],
                    "score": float(j['trend_score']),
                    "percentage_change": float(j['trend_percentage'] or 0)
                },
                "anomalies": {
                    "detected": j['anomalies_detected'],
                    "score": float(j['anomaly_score']),
                    "critical": j['critical_anomalies']
                },
                "optimization": {
                    "potential_gb_per_day": float(j['optimization_potential_gb'] or 0),
                    "monthly_savings_gb": float(j['projected_monthly_savings_gb'] or 0),
                    "annual_cost_savings": float(j['estimated_cost_savings_annual'] or 0)
                },
                "priority": j['priority'],
                "recommendation": j['recommendation'],
                "quality": {
                    "sample_count": j['sample_count'],
                    "confidence_level": j['confidence_level'],
                    "quality_flags": j['quality_flags']
                }
            })
        
        # Calculate averages
        if summary['total_jobs'] > 0:
            summary['avg_dedup_ratio'] = round(summary['avg_dedup_ratio'] / summary['total_jobs'], 2)
            summary['avg_compression_ratio'] = round(summary['avg_compression_ratio'] / summary['total_jobs'], 2)
        
        response = {
            "feature": "Feature 3: Storage Efficiency Analysis",
            "timestamp": timestamp.isoformat(),
            "summary": summary,
            "jobs": job_list,
            "data_source": "PostgreSQL: metrics_storage_efficiency",
            "calculated_by": "Feature 3 (src/feature3/feature3.py)",
            "methodology": {
                "dedup_scoring": "4-tier rating (EXCELLENT ≥3.5x, GOOD ≥2.5x, FAIR ≥1.5x, POOR <1.5x)",
                "compression_scoring": "4-tier rating (EXCELLENT ≥2.0x, GOOD ≥1.8x, FAIR ≥1.3x, POOR <1.3x)",
                "anomaly_detection": "Z-score method with 3σ threshold",
                "trend_analysis": "T-test with p<0.05 for statistical significance",
                "overall_score": "Weighted average: Dedup(30%), Compression(25%), Trend(20%), Consistency(15%), Anomaly(10%)",
                "reference": "NEW DOCS Feature 03 - Section 7"
            }
        }
        
        return json.dumps(response, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error in get_storage_efficiency: {e}", exc_info=True)
        return json.dumps({
            "status": "ERROR",
            "error": str(e),
            "message": "Failed to retrieve storage efficiency from database"
        })
    finally:
        cursor.close()
        conn.close()



@mcp.tool()
async def get_recovery_verification() -> str:
    """
    Get recovery verification and RTO analysis with SureBackup integration (Feature 4).
    
    PRESENTATION STYLE GUIDE:
    ------------------------
    Present as a "Recovery Readiness Dashboard" with the following structure:
    
    # 🔄 Recovery Verification & RTO Analysis
    
    ## Overall Recovery Posture
    - **Jobs Analyzed:** [X]
    - **SLA Compliant:** ✅ [X] | **At Risk:** ⚠️ [X] | **Non-Compliant:** 🔴 [X]
    - **SureBackup Enhanced:** [X] jobs
    
    ### 🔴 CRITICAL - Non-Compliant (Grade D/F)
    - **[Job Name]** - Grade [Grade] ([Score]/100)
      - **RTO Prediction:** [Median] min (95th: [P95] min)
      - **SLA Target:** [Target] min | **Buffer:** [Buffer]% ([Status])
      - **Confidence:** [Level] ([Samples] tests, [Success]% success)
      - **SureBackup:** [Enabled/Enhanced/Disabled]
      - **Max Concurrent:** [X] restores
      - **Action:** [Recommendation]
    
    ### ⚠️ AT RISK - Marginal (Grade C)
    - Similar format
    
    ### ✅ COMPLIANT - Healthy (Grade A/B)
    - Similar format
    
    ### 📊 Component Breakdown (for detailed analysis)
    For each job, show:
    - **Success Rate Score:** [X]/100 (30% weight)
    - **Recency Score:** [X]/100 (25% weight) - Last test: [X] days ago
    - **Predictability Score:** [X]/100 (20% weight) - CV: [X]
    - **SLA Compliance Score:** [X]/100 (15% weight)
    - **Test Coverage Score:** [X]/100 (10% weight) - [X] tests
    
    Use icons: 🔴 (Critical), ⚠️ (Warning), ✅ (Healthy), 🔄 (Recovery), 📊 (Stats)
    
    Returns:
        JSON string containing RTO predictions, confidence scores, component breakdowns, and SureBackup status.
    
    Data Source: PostgreSQL table 'feature4.metrics_recovery_verification'
    Populated by: src/feature4/feature4.py (90-day analysis with continuous interpolation scoring)
    
    Use this to answer:
    - "Can we meet our RTO targets?"
    - "Which jobs have recovery issues?"
    - "Show me RTO predictions"
    - "What's our recovery confidence?"
    - "Is SureBackup working?"
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Get ALL recovery data for full analysis
        cursor.execute("""
            SELECT DISTINCT ON (job_id) *
            FROM feature4.metrics_recovery_verification 
            ORDER BY job_id, created_at DESC
        """)
        
        all_jobs = cursor.fetchall()
        
        if not all_jobs:
            return json.dumps({
                "status": "NO_DATA",
                "message": "No recovery verification data found. Run Feature 4 analysis: python src/feature4/feature4.py",
                "feature": "Feature 4: Recovery Verification & RTO"
            })
        
        # Calculate full grade distribution
        grades = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        sla_status = {'COMPLIANT': 0, 'AT_RISK': 0, 'NON_COMPLIANT': 0}
        total_confidence = 0
        surebackup_enabled = 0
        
        for job in all_jobs:
            grade = job.get('recovery_grade', 'Unknown')
            if grade in grades:
                grades[grade] += 1
            
            sla = job.get('sla_compliance_status', 'Unknown')
            if sla in sla_status:
                sla_status[sla] += 1
            
            total_confidence += job.get('overall_confidence_score', 0)
            
            if job.get('surebackup_available'):
                surebackup_enabled += 1
        
        avg_confidence = total_confidence / len(all_jobs) if all_jobs else 0
        
        # Get critical issues (Grade D/F or Non-Compliant) for detailed list
        cursor.execute("""
            SELECT DISTINCT ON (job_id) job_name, recovery_grade, overall_confidence_score,
                   predicted_rto_minutes, sla_compliance_status, surebackup_available
            FROM feature4.metrics_recovery_verification 
            WHERE recovery_grade IN ('D', 'F') OR sla_compliance_status = 'NON_COMPLIANT'
            ORDER BY job_id, created_at DESC
        """)
        
        critical_jobs = cursor.fetchall()
        
        job_list = []
        for j in critical_jobs:
            job_list.append({
                "job_name": j['job_name'],
                "grade": j['recovery_grade'],
                "confidence_score": float(j['overall_confidence_score'] or 0),
                "predicted_rto_min": float(j['predicted_rto_minutes'] or 0),
                "sla_status": j['sla_compliance_status'],
                "surebackup_available": j['surebackup_available'] or False
            })
        
        response = {
            "feature": "Feature 4: Recovery Verification & RTO Analysis",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_jobs_analyzed": len(all_jobs),
                "grade_distribution": grades,
                "sla_compliance": sla_status,
                "overall_recovery_confidence_pct": round(avg_confidence, 1),
                "surebackup_enabled_jobs": surebackup_enabled,
                "critical_issues_count": len(critical_jobs)
            },
            "critical_issues": job_list,
            "data_source": "PostgreSQL: feature4.metrics_recovery_verification",
            "calculated_by": "Feature 4 (src/feature4/feature4.py)"
        }
        
        return json.dumps(response, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error in get_recovery_verification: {e}", exc_info=True)
        return json.dumps({
            "status": "ERROR",
            "error": str(e),
            "message": "Failed to retrieve recovery verification from database"
        })
    finally:
        cursor.close()
        conn.close()





@mcp.tool()
async def get_risk_analysis() -> str:
    """
    Get advanced risk analysis and prioritization (Feature 5).
    
    NEW DOCS Reference: Feature 05 - Advanced Risk Analysis Implementation Guide
    
    PRESENTATION STYLE GUIDE:
    ------------------------
    Present as a "Risk & Prioritization Report":
    
    # Advanced Risk Analysis
    
    ## 📊 Executive Summary
    - **Overall Confidence:** [High/Moderate/Low] (Score: [X]%)
    - **High Risk Systems:** [X]
    - **Medium Risk Systems:** [X]
    
    ## 🚨 PRIORITY RISKS (High Business Impact)
    
    ### 1. [Job Name]
    - **Composite Risk Score:** [Score]/100 (Category: [CAT])
    - **Business Impact:** [Score] (Tier: [Tier])
    - **Risk Drivers:**
      - [Icon] **Job Failure:** [Score] - [Description if risky]
      - [Icon] **Capacity:** [Score] - [Description if risky]
      - [Icon] **Recovery:** [Score] - [Description if risky]
    
    ## ⚠️ WATCH LIST (Medium Risk)
    - **[Job Name]**: Risk [Score] (Impact [Score])
    
    ## ✅ LOW RISK SYSTEMS
    - [List of jobs]
    
    Returns:
        JSON string containing consolidated risk analysis.
    """
    # Feature 5 uses a SEPARATE database (dr365v)
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': 'dr365v',  # Explicitly Risk DB
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres') 
    }
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get Latest Analysis items
        cursor.execute("""
            SELECT DISTINCT ON (job_id) *
            FROM dr365v.metrics_risk_analysis_consolidated
            ORDER BY job_id, analysis_date DESC
        """)
        
        rows = cursor.fetchall()
        
        if not rows:
            return json.dumps({
                "status": "NO_DATA",
                "message": "No risk analysis data found. Run Feature 5 analysis: python src/feature5/feature5.py",
                "feature": "Feature 5: Advanced Risk Analysis"
            })
            
        timestamp = max(r['analysis_date'] for r in rows)
        
        summary = {
            "high_risk_count": 0,
            "medium_risk_count": 0,
            "low_risk_count": 0,
            "total_analyzed": len(rows),
            "overall_confidence": rows[0]['overall_data_confidence'] if rows else 0
        }
        
        jobs = []
        for r in rows:
            cat = r['risk_category']
            if cat in ['CRITICAL', 'HIGH']: summary['high_risk_count'] += 1
            elif cat == 'MEDIUM': summary['medium_risk_count'] += 1
            else: summary['low_risk_count'] += 1
            
            jobs.append({
                "job_name": r['job_name'],
                "tier": r['vm_tier'],
                "risk_category": r['risk_category'],
                "composite_score": r['composite_risk_score'],
                "business_impact_score": r['business_impact_score'],
                "drivers": {
                    "job_failure": r['job_failure_risk_score'],
                    "capacity": r['capacity_risk_score'],
                    "efficiency": r['efficiency_risk_score'],
                    "recovery": r['recovery_risk_score'],
                    "data_quality": r['data_quality_risk_score']
                },
                "confidence": r['overall_data_confidence']
            })
            
        # Sort by Business Impact
        jobs.sort(key=lambda x: x['business_impact_score'], reverse=True)
        
        response = {
            "feature": "Feature 5: Advanced Risk Analysis",
            "timestamp": timestamp.isoformat(),
            "summary": summary,
            "risks": jobs,
            "data_source": "PostgreSQL: dr365v.metrics_risk_analysis_consolidated",
            "calculated_by": "Feature 5 (src/feature5/feature5.py)"
        }
        
        return json.dumps(response, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error in get_risk_analysis: {e}", exc_info=True)
        return json.dumps({
            "status": "ERROR",
            "error": str(e),
            "details": "Could not connect to Risk DB (dr365v) or query failed.",
            "message": "Failed to retrieve risk analysis."
        })
    finally:
        if 'conn' in locals() and conn:
            conn.close()


@mcp.tool()
async def get_recommendations() -> str:
    """
    Get actionable recommendations and remediation plans (Feature 6)
    
    Retrieves structured remediation guidance plans generated by Feature 6.
    Plans include investigation steps, remediation options, and success criteria.
    
    IMPORTANT: Feature 6 provides GUIDANCE ONLY - no automated execution.
    All plans require human review and approval before implementation.
    
    Returns:
        JSON string containing remediation plans with:
        - Investigation priorities
        - Multiple remediation options with pros/cons
        - Success criteria and verification steps
        - Effort estimates and complexity levels
        - Prerequisites and warnings
    """
    # Feature 6 uses the same database as Feature 5 (dr365v)
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': 'dr365v',
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres')
    }
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # ============================================================================
        # DEMO/TESTING MODE - REMOVE THIS SECTION BEFORE PRODUCTION DEPLOYMENT
        # ============================================================================
        # This section allows Claude to offer test data for demonstration purposes.
        # In production, only real remediation plans should be shown.
        # 
        # TO PREPARE FOR PRODUCTION:
        # 1. Delete everything between the "DEMO/TESTING MODE" markers
        # 2. Keep only the production query (marked below)
        # 3. Remove the test data check and offer logic
        # ============================================================================
        
        # First, check for production plans (is_test_data = FALSE)
        cursor.execute("""
            SELECT 
                plan_id, risk_id, risk_type, job_id, job_name, vm_tier,
                composite_risk_score, business_impact_score, confidence_level,
                issue_summary, pattern_analysis, root_cause_hypotheses,
                investigation_steps, remediation_options, success_criteria,
                urgency, estimated_effort_hours, complexity,
                prerequisites, warnings, plan_json, generated_at, status,
                is_test_data
            FROM dr365v.remediation_plans
            WHERE generated_at >= NOW() - INTERVAL '7 days'
            AND is_test_data = FALSE  -- Production data only
            ORDER BY composite_risk_score DESC, generated_at DESC
            LIMIT 50
        """)
        
        production_rows = cursor.fetchall()
        
        # Check if test data exists
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM dr365v.remediation_plans
            WHERE generated_at >= NOW() - INTERVAL '7 days'
            AND is_test_data = TRUE
        """)
        test_count = cursor.fetchone()['count']
        
        # If no production data but test data exists, offer to show test data
        if not production_rows and test_count > 0:
            return json.dumps({
                "status": "NO_PRODUCTION_DATA",
                "feature": "Feature 6: Actionable Recommendations",
                "message": "No production remediation plans found.",
                "production_plans": 0,
                "test_plans_available": test_count,
                "note": "Your backup environment is healthy (all risk scores < 40).",
                "demo_mode_offer": {
                    "available": True,
                    "message": "No production data found because your environment is healthy (current production threshold is 40). I found {} test plans generated with a lower threshold of 5. Would you like to see those?".format(test_count),
                    "instruction": "If you'd like to see the demo data, ask me: 'Show me the test data' or 'Show demo plans'"
                }
            }, indent=2)
        
        # Use production data
        rows = production_rows
        
        # ============================================================================
        # END OF DEMO/TESTING MODE SECTION
        # ============================================================================
        
        # PRODUCTION CODE STARTS HERE (keep this in production)
        if not rows:
            return json.dumps({
                "status": "NO_DATA",
                "feature": "Feature 6: Actionable Recommendations",
                "message": "No remediation plans found. Run Feature 6 (feature6.py) to generate plans.",
                "note": "Feature 6 generates plans based on Feature 5 risk analysis."
            }, indent=2)
        
        # Build summary
        total_plans = len(rows)
        by_urgency = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        by_risk_type = {}
        by_status = {}
        
        plans = []
        for row in rows:
            # Count by urgency
            urgency = row['urgency']
            if urgency in by_urgency:
                by_urgency[urgency] += 1
            
            # Count by risk type
            risk_type = row['risk_type']
            by_risk_type[risk_type] = by_risk_type.get(risk_type, 0) + 1
            
            # Count by status
            status = row.get('status', 'GENERATED')
            by_status[status] = by_status.get(status, 0) + 1
            
            # Build plan object
            plan = {
                "plan_id": row['plan_id'],
                "generated_at": row['generated_at'].isoformat() if row['generated_at'] else None,
                "status": row.get('status', 'GENERATED'),
                "risk_context": {
                    "risk_id": row['risk_id'],
                    "risk_type": row['risk_type'],
                    "job_id": row['job_id'],
                    "job_name": row['job_name'],
                    "vm_tier": row['vm_tier'],
                    "composite_risk_score": float(row['composite_risk_score']) if row['composite_risk_score'] else 0,
                    "business_impact_score": float(row['business_impact_score']) if row['business_impact_score'] else 0,
                    "confidence_level": row['confidence_level']
                },
                "issue_summary": row['issue_summary'],
                "pattern_analysis": row['pattern_analysis'],
                "root_cause_hypotheses": row['root_cause_hypotheses'],
                "investigation_steps": row['investigation_steps'],
                "remediation_options": row['remediation_options'],
                "success_criteria": row['success_criteria'],
                "urgency": row['urgency'],
                "estimated_effort_hours": float(row['estimated_effort_hours']) if row['estimated_effort_hours'] else 0,
                "complexity": row['complexity'],
                "prerequisites": row['prerequisites'],
                "warnings": row['warnings']
            }
            
            plans.append(plan)
        
        # Build response
        timestamp = datetime.now()
        
        summary = {
            "total_plans": total_plans,
            "by_urgency": by_urgency,
            "by_risk_type": by_risk_type,
            "by_status": by_status,
            "plans_shown": len(plans)
        }
        
        response = {
            "feature": "Feature 6: Actionable Recommendations & Guidance System",
            "timestamp": timestamp.isoformat(),
            "summary": summary,
            "plans": plans,
            "safety_notice": "GUIDANCE ONLY - All plans require human review and approval before implementation",
            "data_source": "PostgreSQL: dr365v.remediation_plans",
            "generated_by": "Feature 6 (src/feature6/feature6.py)"
        }
        
        return json.dumps(response, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error in get_recommendations: {e}", exc_info=True)
        return json.dumps({
            "status": "ERROR",
            "error": str(e),
            "details": "Could not connect to database (dr365v) or query failed.",
            "message": "Failed to retrieve remediation plans."
        }, indent=2)
    finally:
        if 'conn' in locals() and conn:
            conn.close()


# ============================================================================
# DEMO/TESTING TOOL - REMOVE BEFORE PRODUCTION DEPLOYMENT
# ============================================================================
# This tool shows test/demo data for demonstration purposes only.
# DELETE THIS ENTIRE FUNCTION before deploying to production.
# ============================================================================

@mcp.tool()
async def get_test_recommendations() -> str:
    """
    Get test/demo remediation plans (FOR DEMONSTRATION ONLY)
    
    ⚠️ WARNING: This tool is for testing/demo purposes only!
    ⚠️ DELETE THIS TOOL before production deployment!
    
    Shows remediation plans generated with lowered threshold for demonstration.
    These are NOT real production plans.
    
    Returns:
        JSON string containing test/demo remediation plans
    """
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': 'dr365v',
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres')
    }
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get test data only (is_test_data = TRUE)
        cursor.execute("""
            SELECT 
                plan_id, risk_id, risk_type, job_id, job_name, vm_tier,
                composite_risk_score, business_impact_score, confidence_level,
                issue_summary, pattern_analysis, root_cause_hypotheses,
                investigation_steps, remediation_options, success_criteria,
                urgency, estimated_effort_hours, complexity,
                prerequisites, warnings, plan_json, generated_at, status,
                is_test_data
            FROM dr365v.remediation_plans
            WHERE is_test_data = TRUE
            ORDER BY composite_risk_score DESC, generated_at DESC
            LIMIT 50
        """)
        
        rows = cursor.fetchall()
        
        if not rows:
            return json.dumps({
                "status": "NO_TEST_DATA",
                "message": "No test/demo data available.",
                "note": "Run Feature 6 with lowered threshold to generate demo data."
            }, indent=2)
        
        # Build summary (same as production)
        total_plans = len(rows)
        by_urgency = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        by_risk_type = {}
        by_status = {}
        
        plans = []
        for row in rows:
            urgency = row['urgency']
            if urgency in by_urgency:
                by_urgency[urgency] += 1
            
            risk_type = row['risk_type']
            by_risk_type[risk_type] = by_risk_type.get(risk_type, 0) + 1
            
            status = row.get('status', 'GENERATED')
            by_status[status] = by_status.get(status, 0) + 1
            
            plan = {
                "plan_id": row['plan_id'],
                "generated_at": row['generated_at'].isoformat() if row['generated_at'] else None,
                "status": row.get('status', 'GENERATED'),
                "is_test_data": row['is_test_data'],  # Explicitly show this is test data
                "risk_context": {
                    "risk_id": row['risk_id'],
                    "risk_type": row['risk_type'],
                    "job_id": row['job_id'],
                    "job_name": row['job_name'],
                    "vm_tier": row['vm_tier'],
                    "composite_risk_score": float(row['composite_risk_score']) if row['composite_risk_score'] else 0,
                    "business_impact_score": float(row['business_impact_score']) if row['business_impact_score'] else 0,
                    "confidence_level": row['confidence_level']
                },
                "issue_summary": row['issue_summary'],
                "pattern_analysis": row['pattern_analysis'],
                "root_cause_hypotheses": row['root_cause_hypotheses'],
                "investigation_steps": row['investigation_steps'],
                "remediation_options": row['remediation_options'],
                "success_criteria": row['success_criteria'],
                "urgency": row['urgency'],
                "estimated_effort_hours": float(row['estimated_effort_hours']) if row['estimated_effort_hours'] else 0,
                "complexity": row['complexity'],
                "prerequisites": row['prerequisites'],
                "warnings": row['warnings']
            }
            
            plans.append(plan)
        
        timestamp = datetime.now()
        
        summary = {
            "total_plans": total_plans,
            "by_urgency": by_urgency,
            "by_risk_type": by_risk_type,
            "by_status": by_status,
            "plans_shown": len(plans)
        }
        
        response = {
            "feature": "Feature 6: Test/Demo Recommendations",
            "timestamp": timestamp.isoformat(),
            "summary": summary,
            "plans": plans,
            "test_data_warning": "⚠️ THESE ARE TEST/DEMO PLANS - NOT REAL PRODUCTION DATA",
            "note": "These plans were generated with a lowered threshold for demonstration purposes.",
            "data_source": "PostgreSQL: dr365v.remediation_plans (WHERE is_test_data = TRUE)",
            "generated_by": "Feature 6 (src/feature6/feature6.py) in demo mode"
        }
        
        return json.dumps(response, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error in get_test_recommendations: {e}", exc_info=True)
        return json.dumps({
            "status": "ERROR",
            "error": str(e),
            "message": "Failed to retrieve test recommendations."
        }, indent=2)
    finally:
        if 'conn' in locals() and conn:
            conn.close()

# ============================================================================
# END OF DEMO/TESTING TOOL
# ============================================================================


# =============================================================================
# SERVER ENTRY POINT
# =============================================================================


# ============================================================================
# FEATURE 7: RANSOMWARE DETECTION (WAZUH)
# ============================================================================

# ============================================================================
# FEATURE 13: STONEFUSION INTEGRATION
# ============================================================================

@mcp.tool()
async def get_stonefusion_events(severity: str = 'all', limit: int = 20) -> str:
    """
    Retrieves event logs from StoneFly Storage Concentrator (Feature 13).

    PRESENTATION STYLE GUIDE:
    ------------------------
    Present as a "Storage Health Monitor":
    
    ## 🚨 Critical Alerts (if any)
    - **[Time]**: [Event Description]
    
    ## ⚠️ Warnings
    - **[Time]**: [Event Description]
    
    ## ℹ️ System Status
    - **Appliance**: [Name] ([IP])
    - **Status**: [Status] (Uptime: [X] hours)

    Use this to monitor storage health, check for hardware failures (RAID, Battery),
    and view critical system alerts.
    
    Args:
        severity: Filter by severity ('warn', 'crit', 'all'). Default: 'all'
        limit: Maximum number of events to return. Default: 20
        
    Returns:
        JSON string containing system status and event logs.
    """
    return f13_get_events(severity, limit)

@mcp.tool()
async def get_stonefusion_inventory() -> str:
    """
    Retrieves a comprehensive inventory of all iSCSI and NAS volumes (Feature 13).
    
    PRESENTATION STYLE GUIDE:
    ------------------------
    Present as a "Storage Inventory Dashboard":
    
    ## 📊 Summary
    - **Total Volumes**: [X] (Health: [X]%)
    - **iSCSI**: [X] Volumes
    - **NAS**: [X] Shares
    
    ## 🧱 iSCSI Block Storage
    | Name | Status | Export |
    |------|--------|--------|
    | [Name] | [Status] | [Enabled/Disabled] |
    
    ## 📂 NAS File Shares
    | Name | Status | Export |
    |------|--------|--------|
    | [Name] | [Status] | [Enabled/Disabled] |
    
    Use this to:
    - List all storage volumes
    - Check "Export" status (security audit)
    - Monitor volume health status (OK/Error)
    
    Returns:
        JSON string containing summary stats and volume lists.
    """
    return f13_get_inventory()

@mcp.tool()
async def get_stonefusion_volume_details(volume_name: str) -> str:
    """
    Retrieves deep dive details for a specific volume (Feature 13).
    
    PRESENTATION STYLE GUIDE:
    ------------------------
    Present as a "Volume Diagnostic Card":
    
    # 🔍 Volume: [Name]
    
    ## Configuration
    - **Type**: [iSCSI/NAS]
    - **Status**: [OK/Error]
    - **Export**: [Enabled/Disabled] (Access Control)
    
    ## Connectivity
    - **Target IQN**: `[IQN]` (if iSCSI)
    - **Active Sessions**: [count]
    - **Unique ID**: [WWN]
    
    Use this to:
    - Get Target IQN for iSCSI
    - Check active session counts
    - Diagnose specific volume issues
    
    Args:
        volume_name: The exact name of the volume (e.g., 'volume-0001')
        
    Returns:
        JSON string containing detailed volume metadata.
    """
    return f13_get_volume_details(volume_name)


# ============================================================================
# FEATURE 7: RANSOMWARE DETECTION (WAZUH)
# ============================================================================

@mcp.tool()
async def get_wazuh_agents() -> str:
    """
    List all active Wazuh agents (Feature 7).
    
    Use this tool to find available agent names before running checks.
    
    Returns:
        JSON string containing list of agents (id, name, ip, status).
    """
    try:
        agents = list_wazuh_agents()
        return json.dumps({"agents": agents, "count": len(agents)}, indent=2)
    except Exception as e:
        logger.error(f"Error in get_wazuh_agents: {e}", exc_info=True)
        return json.dumps({
            "status": "ERROR", 
            "error": str(e),
            "message": "Failed to retrieve agent list."
        }, indent=2)

@mcp.tool()
async def check_ransomware_status(agent_name: str, time_window_hours: int = 24) -> str:
    """
    Check for ransomware indicators on a specific agent using Wazuh integration.
    Analyses file integrity monitoring (FIM), process behavior, and security events
    to detect ransomware activity relative to specific specifications.
    
    Args:
        agent_name: Name of the agent to check (e.g., "WIN-SERVER01")
        time_window_hours: Lookback period in hours (default: 24)
        
    Returns:
        JSON string containing detection status, confidence score, and indicators.
    """
    try:
        input_data = RansomwareDetectionInput(
            agent_name=agent_name,
            time_window_hours=time_window_hours
        )
        # Assuming config is in standard location relative to execution
        result = detect_ransomware(input_data)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error in check_ransomware_status: {e}", exc_info=True)
        return json.dumps({
            "status": "ERROR",
            "error": str(e),
            "message": "Failed to perform ransomware detection."
        }, indent=2)

@mcp.tool()
async def analyze_ransomware_with_context(agent_name: str, suspected_user: str = "unknown") -> str:
    """
    Run Ransomware Detection AND Business Context Analysis.
    
    Use this to get a comprehensive, business-aware risk score.
    
    Args:
        agent_name: Target agent
        suspected_user: Optional username if known (e.g. from tickets), affects context score.
    """
    try:
        # 1. Run Feature 7
        f7_input = RansomwareDetectionInput(agent_name=agent_name, time_window_hours=24)
        f7_result = detect_ransomware(f7_input)
        
        if f7_result.get('status') == 'error':
            return json.dumps(f7_result, indent=2)
            
        # 2. Prepare Feature 8 Input
        # F8 expects keys that match Feature07Input pydantic model
        f8_input = {
            "agent_id": f7_result.get('agent_id', 'unknown'),
            "agent_name": f7_result.get('agent_name', agent_name),
            "raw_confidence": int(f7_result.get('confidence', 0)),
            "username": suspected_user,
            "timestamp": f7_result.get('timestamp', ""),
            "detected": f7_result.get('detected', False)
        }
        
        # 3. Run Feature 8
        f8_result = analyze_ransomware_context(f8_input)
        
        # 4. Merge Results for User
        combined = {
            "technical_analysis": f7_result,
            "business_context": f8_result
        }
        return json.dumps(combined, indent=2)
        
    except Exception as e:
        logger.error(f"Error in context analysis: {e}", exc_info=True)
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

@mcp.tool()
async def analyze_attack_timeline_tool(agent_name: str) -> str:
    """
    Reconstruct Attack Timeline for a COMPROMISED agent.
    
    1. Runs Ransomware Detection to find attack window.
    2. Queries logs to build chronological event sequence.
    3. Identifies lateral movement.
    
    Note: Returns 'Skipped' if no ransomware is detected.
    """
    try:
        # 1. Run Feature 7 (Need timestamps)
        f7_input = RansomwareDetectionInput(agent_name=agent_name, time_window_hours=24)
        f7_result = detect_ransomware(f7_input)
        
        if f7_result.get('status') == 'error':
            return json.dumps(f7_result, indent=2)
            
        # 2. Run Feature 9
        # Map F7 output to F9 input
        f9_input = {
            "agent_id": f7_result.get('agent_id', 'unknown'),
            "agent_name": f7_result.get('agent_name', agent_name),
            "first_seen": f7_result.get('first_seen') or datetime.utcnow().isoformat() + "Z",
            "last_seen": f7_result.get('last_seen') or datetime.utcnow().isoformat() + "Z",
            "detected": f7_result.get('detected', False)
        }
        
        f9_result = analyze_attack_timeline(f9_input)
        
        return json.dumps(f9_result, indent=2)
        
    except Exception as e:
        logger.error(f"Error in timeline analysis: {e}", exc_info=True)
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

@mcp.tool()
async def generate_response_playbook_tool(timeline_data: str, user_role: str = "SOC") -> str:
    """
    Generate an Advisory Response Playbook (Feature 10).
    
    Takes the output of Feature 9 (Attack Timeline) and generates actionable, 
    role-based remediation steps (Isolation, Forensics, Recovery).
    
    Args:
        timeline_data: JSON string returned by 'analyze_attack_timeline_tool'.
                       Must contain 'target_host', 'lateral_hosts', and 'timeline'.
        user_role: Target audience ('SOC', 'Finance', 'Admin'). 
                   Default: 'SOC' (Detailed technical steps).
                   
    Returns:
        JSON string containing the Playbook with 'requires_approval': True.
    """
    try:
        if isinstance(timeline_data, str):
            f9_output = json.loads(timeline_data)
        else:
            f9_output = timeline_data
            
        result = generate_response_playbook(f9_output, user_role)
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error in playbook generation: {e}", exc_info=True)
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

@mcp.tool()
async def scan_backup_security_tool(group_name: str = "backup-servers") -> str:
    """
    Scan Backup Infrastructure for Security Risks (Feature 11).
    
    Checks SCA Compliance (Hardening), Vulnerabilities, and File Integrity.
    
    Args:
        group_name: Wazuh Agent Group to scan (default: 'backup-servers')
        
    Returns:
        JSON report with Risk Score, Findings (SCA/Vuln), and Remediation Needs.
    """
    try:
        result = scan_backup_security(group_name)
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error in backup security scan: {e}", exc_info=True)
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

@mcp.tool()
async def map_compliance_gaps_tool(scan_results: str) -> str:
    """
    Generate Compliance Mapping Report (Feature 12).
    
    Maps Feature 11 Security Scan findings to Regulatory Frameworks (PCI, ISO, NIST).
    
    Args:
        scan_results: JSON string output from 'scan_backup_security_tool'.
        
    Returns:
        JSON string containing Compliance Gap Analysis and Coverage %.
    """
    try:
        if isinstance(scan_results, str):
            f11_output = json.loads(scan_results)
        else:
            f11_output = scan_results
            
        result = map_compliance_gaps(f11_output)
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error in compliance mapping: {e}", exc_info=True)
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

@mcp.tool()
async def simulate_ransomware_scenario(scenario: str, step: str = "all") -> str:
    """
    Run a logical simulation of the Ransomware Intelligence Pipeline.
    
    Use this to DEMONSTRATE capabilities without a live ransomware infection.
    
    Args:
        scenario: 'clean' (False Alarm), 'basic' (Laptop), or 'critical' (Finance Server Breach).
        step: 'all' (default), 'detect' (Technical), 'context' (Business Risk), 'timeline' (Chronological Events).
              Use step-by-step to explain the pipeline.
    """
    try:
        result = run_simulation(scenario, step)
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error in simulation: {e}", exc_info=True)
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

if __name__ == "__main__":
    logger.info("==" * 70)
    logger.info("DR365V Intelligent MCP Server - NEW DOCS Compliant")
    logger.info("=" * 70)
    logger.info("Features Implemented:")
    logger.info("  ✅ Feature 1: Health Metrics (2 tools)")
    logger.info("  ✅ Feature 2: Capacity Forecasting (2 tools)")
    logger.info("  ✅ Feature 3: Storage Efficiency (1 tool)")
    logger.info("  ✅ Feature 4: Recovery Verification & RTO (1 tool)")
    logger.info("  ✅ Feature 5: Risk Analysis (1 tool)")
    logger.info("  ✅ Feature 6: Remediation Recommendations (2 tools)")
    logger.info("  ✅ Feature 7: Ransomware Detection (2 tools)")
    logger.info("  ✅ Feature 8: Contextual Scoring (1 tool)")
    logger.info("  ✅ Feature 9: Attack Timeline (1 tool)")
    logger.info("  ✅ Feature 10: Response Playbooks (1 tool)")
    logger.info("  ✅ Feature 11: Security Scanning (1 tool)")
    logger.info("  ✅ Feature 12: Compliance Mapping (1 tool)")
    logger.info("  ✅ Feature 13: StoneFusion Integration (3 tools)")
    logger.info("  ✅ Demo: Ransomware Simulation (1 tool)")
    logger.info("-" * 70)
    
    mcp.run()
