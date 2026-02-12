--
-- PostgreSQL database dump
--

\restrict r1yNdGnyxfzlUakXAyq2VmBrmY1bqwWI3alepXe4i86dbJIOGFjwWSQcc4XFD8K

-- Dumped from database version 15.6
-- Dumped by pg_dump version 17.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: feature1; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA feature1;


ALTER SCHEMA feature1 OWNER TO postgres;

--
-- Name: feature2; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA feature2;


ALTER SCHEMA feature2 OWNER TO postgres;

--
-- Name: feature3; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA feature3;


ALTER SCHEMA feature3 OWNER TO postgres;

--
-- Name: feature4; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA feature4;


ALTER SCHEMA feature4 OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: metrics_health_score; Type: TABLE; Schema: feature1; Owner: postgres
--

CREATE TABLE feature1.metrics_health_score (
    id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    overall_score numeric(5,2) NOT NULL,
    grade character varying(1) NOT NULL,
    risk_level character varying(20) NOT NULL,
    failure_rate_score numeric(5,2) NOT NULL,
    trend_score numeric(5,2) NOT NULL,
    pattern_score numeric(5,2) NOT NULL,
    protected_objects_score numeric(5,2) NOT NULL,
    repository_score numeric(5,2) NOT NULL,
    trend_classification character varying(20) NOT NULL,
    trend_percentage numeric(6,2),
    trend_is_significant boolean DEFAULT false NOT NULL,
    seasonal_pattern character varying(30),
    pattern_classification character varying(30) NOT NULL,
    pattern_confidence character varying(20),
    pattern_detail text,
    correlated_failures boolean DEFAULT false,
    sample_count integer NOT NULL,
    date_range_days integer NOT NULL,
    average_frequency numeric(5,2) NOT NULL,
    confidence_level character varying(20) NOT NULL,
    confidence_multiplier numeric(3,2) NOT NULL,
    quality_flags jsonb DEFAULT '{}'::jsonb NOT NULL,
    last_api_call timestamp without time zone NOT NULL,
    last_session_timestamp timestamp without time zone NOT NULL,
    cache_age_hours numeric(5,2) DEFAULT 0 NOT NULL,
    data_age_hours numeric(5,2) DEFAULT 0 NOT NULL,
    recommendation text NOT NULL,
    created_date date GENERATED ALWAYS AS (date(created_at)) STORED,
    CONSTRAINT metrics_health_score_average_frequency_check CHECK ((average_frequency >= (0)::numeric)),
    CONSTRAINT metrics_health_score_confidence_level_check CHECK (((confidence_level)::text = ANY ((ARRAY['HIGH'::character varying, 'MODERATE'::character varying, 'LOW'::character varying, 'INSUFFICIENT'::character varying])::text[]))),
    CONSTRAINT metrics_health_score_confidence_multiplier_check CHECK (((confidence_multiplier >= 0.0) AND (confidence_multiplier <= 1.0))),
    CONSTRAINT metrics_health_score_date_range_days_check CHECK ((date_range_days >= 0)),
    CONSTRAINT metrics_health_score_failure_rate_score_check CHECK (((failure_rate_score >= (0)::numeric) AND (failure_rate_score <= (100)::numeric))),
    CONSTRAINT metrics_health_score_grade_check CHECK (((grade)::text = ANY ((ARRAY['A'::character varying, 'B'::character varying, 'C'::character varying, 'D'::character varying, 'F'::character varying])::text[]))),
    CONSTRAINT metrics_health_score_overall_score_check CHECK (((overall_score >= (0)::numeric) AND (overall_score <= (100)::numeric))),
    CONSTRAINT metrics_health_score_pattern_classification_check CHECK (((pattern_classification)::text = ANY ((ARRAY['NO_FAILURES'::character varying, 'RANDOM'::character varying, 'INTERMITTENT_IRREGULAR'::character varying, 'INTERMITTENT_REGULAR'::character varying, 'CONSISTENT_WEEKDAY'::character varying, 'CONSISTENT_TIME'::character varying])::text[]))),
    CONSTRAINT metrics_health_score_pattern_confidence_check CHECK (((pattern_confidence)::text = ANY ((ARRAY['HIGH'::character varying, 'MODERATE'::character varying, 'LOW'::character varying, 'N/A'::character varying])::text[]))),
    CONSTRAINT metrics_health_score_pattern_score_check CHECK (((pattern_score >= (0)::numeric) AND (pattern_score <= (100)::numeric))),
    CONSTRAINT metrics_health_score_protected_objects_score_check CHECK (((protected_objects_score >= (0)::numeric) AND (protected_objects_score <= (100)::numeric))),
    CONSTRAINT metrics_health_score_repository_score_check CHECK (((repository_score >= (0)::numeric) AND (repository_score <= (100)::numeric))),
    CONSTRAINT metrics_health_score_risk_level_check CHECK (((risk_level)::text = ANY ((ARRAY['LOW'::character varying, 'MEDIUM'::character varying, 'HIGH'::character varying, 'CRITICAL'::character varying])::text[]))),
    CONSTRAINT metrics_health_score_sample_count_check CHECK ((sample_count >= 0)),
    CONSTRAINT metrics_health_score_trend_classification_check CHECK (((trend_classification)::text = ANY ((ARRAY['IMPROVING'::character varying, 'STABLE'::character varying, 'DEGRADING'::character varying, 'INSUFFICIENT_DATA'::character varying])::text[]))),
    CONSTRAINT metrics_health_score_trend_score_check CHECK (((trend_score >= (0)::numeric) AND (trend_score <= (100)::numeric)))
);


ALTER TABLE feature1.metrics_health_score OWNER TO postgres;

--
-- Name: metrics_health_score_id_seq; Type: SEQUENCE; Schema: feature1; Owner: postgres
--

CREATE SEQUENCE feature1.metrics_health_score_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE feature1.metrics_health_score_id_seq OWNER TO postgres;

--
-- Name: metrics_health_score_id_seq; Type: SEQUENCE OWNED BY; Schema: feature1; Owner: postgres
--

ALTER SEQUENCE feature1.metrics_health_score_id_seq OWNED BY feature1.metrics_health_score.id;


--
-- Name: metrics_job_failures; Type: TABLE; Schema: feature1; Owner: postgres
--

CREATE TABLE feature1.metrics_job_failures (
    id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    job_id character varying(100) NOT NULL,
    job_name character varying(255) NOT NULL,
    job_type character varying(50),
    success_count integer DEFAULT 0 NOT NULL,
    warning_count integer DEFAULT 0 NOT NULL,
    failure_count integer DEFAULT 0 NOT NULL,
    total_sessions integer NOT NULL,
    success_rate numeric(5,2) NOT NULL,
    trend_classification character varying(20) NOT NULL,
    trend_percentage numeric(6,2),
    first_third_success_rate numeric(5,2),
    last_third_success_rate numeric(5,2),
    pattern_classification character varying(30) NOT NULL,
    pattern_confidence character varying(20),
    pattern_detail text,
    last_failure_timestamp timestamp without time zone,
    last_failure_reason text,
    most_common_failure_weekday integer,
    most_common_failure_hour integer,
    average_failure_interval_days numeric(5,2),
    sessions_analyzed integer NOT NULL,
    job_enabled boolean DEFAULT true,
    repository_id character varying(100),
    repository_name character varying(255),
    recommendation text NOT NULL,
    priority character varying(20) DEFAULT 'MEDIUM'::character varying NOT NULL,
    created_date date GENERATED ALWAYS AS (date(created_at)) STORED,
    CONSTRAINT metrics_job_failures_failure_count_check CHECK ((failure_count >= 0)),
    CONSTRAINT metrics_job_failures_most_common_failure_hour_check CHECK (((most_common_failure_hour >= 0) AND (most_common_failure_hour <= 23))),
    CONSTRAINT metrics_job_failures_most_common_failure_weekday_check CHECK (((most_common_failure_weekday >= 0) AND (most_common_failure_weekday <= 6))),
    CONSTRAINT metrics_job_failures_priority_check CHECK (((priority)::text = ANY ((ARRAY['LOW'::character varying, 'MEDIUM'::character varying, 'HIGH'::character varying, 'CRITICAL'::character varying])::text[]))),
    CONSTRAINT metrics_job_failures_success_count_check CHECK ((success_count >= 0)),
    CONSTRAINT metrics_job_failures_success_rate_check CHECK (((success_rate >= (0)::numeric) AND (success_rate <= (100)::numeric))),
    CONSTRAINT metrics_job_failures_total_sessions_check CHECK ((total_sessions >= 0)),
    CONSTRAINT metrics_job_failures_warning_count_check CHECK ((warning_count >= 0))
);


ALTER TABLE feature1.metrics_job_failures OWNER TO postgres;

--
-- Name: metrics_job_failures_id_seq; Type: SEQUENCE; Schema: feature1; Owner: postgres
--

CREATE SEQUENCE feature1.metrics_job_failures_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE feature1.metrics_job_failures_id_seq OWNER TO postgres;

--
-- Name: metrics_job_failures_id_seq; Type: SEQUENCE OWNED BY; Schema: feature1; Owner: postgres
--

ALTER SEQUENCE feature1.metrics_job_failures_id_seq OWNED BY feature1.metrics_job_failures.id;


--
-- Name: capacity_history_raw; Type: TABLE; Schema: feature2; Owner: postgres
--

CREATE TABLE feature2.capacity_history_raw (
    id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    repository_id character varying(100) NOT NULL,
    repository_name character varying(255) NOT NULL,
    total_capacity_bytes bigint NOT NULL,
    used_space_bytes bigint NOT NULL,
    free_space_bytes bigint NOT NULL,
    utilization_pct numeric(5,2) NOT NULL,
    deduplication_ratio numeric(4,2),
    compression_ratio numeric(4,2),
    is_interpolated boolean DEFAULT false,
    is_outlier boolean DEFAULT false,
    source character varying(50) DEFAULT 'veeam_api'::character varying,
    created_date date GENERATED ALWAYS AS (date(created_at)) STORED
);


ALTER TABLE feature2.capacity_history_raw OWNER TO postgres;

--
-- Name: TABLE capacity_history_raw; Type: COMMENT; Schema: feature2; Owner: postgres
--

COMMENT ON TABLE feature2.capacity_history_raw IS 'Feature 2: Historical capacity measurements for polynomial regression';


--
-- Name: COLUMN capacity_history_raw.deduplication_ratio; Type: COMMENT; Schema: feature2; Owner: postgres
--

COMMENT ON COLUMN feature2.capacity_history_raw.deduplication_ratio IS 'Optional: dedup ratio for trend analysis';


--
-- Name: COLUMN capacity_history_raw.source; Type: COMMENT; Schema: feature2; Owner: postgres
--

COMMENT ON COLUMN feature2.capacity_history_raw.source IS 'Data source: veeam_api (real) or backfill (simulated)';


--
-- Name: capacity_history_raw_id_seq; Type: SEQUENCE; Schema: feature2; Owner: postgres
--

CREATE SEQUENCE feature2.capacity_history_raw_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE feature2.capacity_history_raw_id_seq OWNER TO postgres;

--
-- Name: capacity_history_raw_id_seq; Type: SEQUENCE OWNED BY; Schema: feature2; Owner: postgres
--

ALTER SEQUENCE feature2.capacity_history_raw_id_seq OWNED BY feature2.capacity_history_raw.id;


--
-- Name: metrics_capacity_forecast; Type: TABLE; Schema: feature2; Owner: postgres
--

CREATE TABLE feature2.metrics_capacity_forecast (
    id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    repository_id character varying(100) NOT NULL,
    repository_name character varying(255) NOT NULL,
    repository_type character varying(50),
    total_capacity_gb numeric(12,2) NOT NULL,
    current_used_gb numeric(12,2) NOT NULL,
    current_utilization_pct numeric(5,2) NOT NULL,
    days_to_80_percent integer,
    days_to_90_percent integer,
    days_to_100_percent integer,
    days_to_80_ci_lower integer,
    days_to_80_ci_upper integer,
    days_to_100_ci_lower integer,
    days_to_100_ci_upper integer,
    growth_rate_gb_per_day numeric(8,2) NOT NULL,
    acceleration_factor numeric(8,4) DEFAULT 0.0,
    growth_pattern character varying(20) NOT NULL,
    model_type character varying(20) NOT NULL,
    r_squared numeric(5,4) NOT NULL,
    sample_count integer NOT NULL,
    confidence_level character varying(20) NOT NULL,
    confidence_multiplier numeric(3,2) NOT NULL,
    dedup_trend character varying(20),
    dedup_adjustment_applied boolean DEFAULT false,
    current_dedup_ratio numeric(4,2),
    quality_flags jsonb DEFAULT '{}'::jsonb NOT NULL,
    gaps_interpolated integer DEFAULT 0,
    outliers_removed integer DEFAULT 0,
    priority character varying(20) NOT NULL,
    recommendation text NOT NULL,
    recommended_capacity_gb numeric(12,2),
    forecast_accuracy_pct numeric(5,2),
    created_date date GENERATED ALWAYS AS (date(created_at)) STORED,
    CONSTRAINT metrics_capacity_forecast_confidence_level_check CHECK (((confidence_level)::text = ANY ((ARRAY['HIGH'::character varying, 'MODERATE'::character varying, 'LOW'::character varying])::text[]))),
    CONSTRAINT metrics_capacity_forecast_confidence_multiplier_check CHECK (((confidence_multiplier >= (0)::numeric) AND (confidence_multiplier <= 1.0))),
    CONSTRAINT metrics_capacity_forecast_dedup_trend_check CHECK (((dedup_trend)::text = ANY ((ARRAY['IMPROVING'::character varying, 'STABLE'::character varying, 'DEGRADING'::character varying, 'UNKNOWN'::character varying])::text[]))),
    CONSTRAINT metrics_capacity_forecast_growth_pattern_check CHECK (((growth_pattern)::text = ANY ((ARRAY['LINEAR'::character varying, 'QUADRATIC'::character varying, 'DECLINING'::character varying, 'STABLE'::character varying, 'UNKNOWN'::character varying])::text[]))),
    CONSTRAINT metrics_capacity_forecast_model_type_check CHECK (((model_type)::text = ANY ((ARRAY['LINEAR'::character varying, 'QUADRATIC'::character varying])::text[]))),
    CONSTRAINT metrics_capacity_forecast_priority_check CHECK (((priority)::text = ANY ((ARRAY['LOW'::character varying, 'MEDIUM'::character varying, 'HIGH'::character varying, 'URGENT'::character varying])::text[]))),
    CONSTRAINT metrics_capacity_forecast_r_squared_check CHECK (((r_squared >= (0)::numeric) AND (r_squared <= (1)::numeric))),
    CONSTRAINT metrics_capacity_forecast_sample_count_check CHECK ((sample_count >= 0))
);


ALTER TABLE feature2.metrics_capacity_forecast OWNER TO postgres;

--
-- Name: TABLE metrics_capacity_forecast; Type: COMMENT; Schema: feature2; Owner: postgres
--

COMMENT ON TABLE feature2.metrics_capacity_forecast IS 'Feature 2: Capacity forecast predictions with statistical confidence';


--
-- Name: COLUMN metrics_capacity_forecast.days_to_80_percent; Type: COMMENT; Schema: feature2; Owner: postgres
--

COMMENT ON COLUMN feature2.metrics_capacity_forecast.days_to_80_percent IS 'Days until 80% capacity threshold (primary planning metric)';


--
-- Name: COLUMN metrics_capacity_forecast.model_type; Type: COMMENT; Schema: feature2; Owner: postgres
--

COMMENT ON COLUMN feature2.metrics_capacity_forecast.model_type IS 'LINEAR or QUADRATIC based on p-value < 0.05 test';


--
-- Name: COLUMN metrics_capacity_forecast.r_squared; Type: COMMENT; Schema: feature2; Owner: postgres
--

COMMENT ON COLUMN feature2.metrics_capacity_forecast.r_squared IS 'R² goodness-of-fit score (0-1 scale)';


--
-- Name: COLUMN metrics_capacity_forecast.quality_flags; Type: COMMENT; Schema: feature2; Owner: postgres
--

COMMENT ON COLUMN feature2.metrics_capacity_forecast.quality_flags IS 'Quality metadata for Feature 5 consumption';


--
-- Name: metrics_capacity_forecast_id_seq; Type: SEQUENCE; Schema: feature2; Owner: postgres
--

CREATE SEQUENCE feature2.metrics_capacity_forecast_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE feature2.metrics_capacity_forecast_id_seq OWNER TO postgres;

--
-- Name: metrics_capacity_forecast_id_seq; Type: SEQUENCE OWNED BY; Schema: feature2; Owner: postgres
--

ALTER SEQUENCE feature2.metrics_capacity_forecast_id_seq OWNED BY feature2.metrics_capacity_forecast.id;


--
-- Name: metrics_storage_efficiency; Type: TABLE; Schema: feature3; Owner: postgres
--

CREATE TABLE feature3.metrics_storage_efficiency (
    id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    job_id character varying(100) NOT NULL,
    job_name character varying(255) NOT NULL,
    job_type character varying(50),
    overall_score numeric(5,2),
    efficiency_grade character varying(1),
    efficiency_rating character varying(20),
    avg_dedup_ratio numeric(6,2),
    dedup_score numeric(5,2),
    dedup_rating character varying(20),
    dedup_consistency numeric(5,2),
    avg_compression_ratio numeric(6,2),
    compression_score numeric(5,2),
    compression_rating character varying(20),
    compression_consistency numeric(5,2),
    combined_ratio numeric(10,2),
    storage_reduction_pct numeric(5,2),
    trend_classification character varying(20),
    trend_score numeric(5,2),
    trend_percentage numeric(6,2),
    anomalies_detected integer,
    anomaly_score numeric(5,2),
    critical_anomalies boolean DEFAULT false,
    consistency_score numeric(5,2),
    dedup_std_dev numeric(6,2),
    compression_std_dev numeric(6,2),
    optimization_potential_gb numeric(10,2),
    projected_monthly_savings_gb numeric(10,2),
    estimated_cost_savings_annual numeric(10,2),
    priority character varying(20),
    recommendation text,
    sample_count integer,
    confidence_level character varying(20),
    quality_flags jsonb,
    trend_pvalue numeric(6,4),
    created_date date GENERATED ALWAYS AS (date(created_at)) STORED
);


ALTER TABLE feature3.metrics_storage_efficiency OWNER TO postgres;

--
-- Name: TABLE metrics_storage_efficiency; Type: COMMENT; Schema: feature3; Owner: postgres
--

COMMENT ON TABLE feature3.metrics_storage_efficiency IS 'Feature 3: Storage efficiency scores and recommendations';


--
-- Name: COLUMN metrics_storage_efficiency.overall_score; Type: COMMENT; Schema: feature3; Owner: postgres
--

COMMENT ON COLUMN feature3.metrics_storage_efficiency.overall_score IS 'Weighted average of 5 components (0-100)';


--
-- Name: COLUMN metrics_storage_efficiency.efficiency_rating; Type: COMMENT; Schema: feature3; Owner: postgres
--

COMMENT ON COLUMN feature3.metrics_storage_efficiency.efficiency_rating IS 'Overall efficiency classification';


--
-- Name: COLUMN metrics_storage_efficiency.avg_dedup_ratio; Type: COMMENT; Schema: feature3; Owner: postgres
--

COMMENT ON COLUMN feature3.metrics_storage_efficiency.avg_dedup_ratio IS 'Average deduplication ratio (e.g., 3.5x)';


--
-- Name: COLUMN metrics_storage_efficiency.avg_compression_ratio; Type: COMMENT; Schema: feature3; Owner: postgres
--

COMMENT ON COLUMN feature3.metrics_storage_efficiency.avg_compression_ratio IS 'Average compression ratio (e.g., 2.1x)';


--
-- Name: COLUMN metrics_storage_efficiency.combined_ratio; Type: COMMENT; Schema: feature3; Owner: postgres
--

COMMENT ON COLUMN feature3.metrics_storage_efficiency.combined_ratio IS 'Dedup * Compression (total reduction)';


--
-- Name: COLUMN metrics_storage_efficiency.storage_reduction_pct; Type: COMMENT; Schema: feature3; Owner: postgres
--

COMMENT ON COLUMN feature3.metrics_storage_efficiency.storage_reduction_pct IS 'Percentage of storage saved';


--
-- Name: COLUMN metrics_storage_efficiency.optimization_potential_gb; Type: COMMENT; Schema: feature3; Owner: postgres
--

COMMENT ON COLUMN feature3.metrics_storage_efficiency.optimization_potential_gb IS 'Potential GB savings per day';


--
-- Name: COLUMN metrics_storage_efficiency.quality_flags; Type: COMMENT; Schema: feature3; Owner: postgres
--

COMMENT ON COLUMN feature3.metrics_storage_efficiency.quality_flags IS 'Quality metadata for Feature 5 consumption';


--
-- Name: metrics_storage_efficiency_id_seq; Type: SEQUENCE; Schema: feature3; Owner: postgres
--

CREATE SEQUENCE feature3.metrics_storage_efficiency_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE feature3.metrics_storage_efficiency_id_seq OWNER TO postgres;

--
-- Name: metrics_storage_efficiency_id_seq; Type: SEQUENCE OWNED BY; Schema: feature3; Owner: postgres
--

ALTER SEQUENCE feature3.metrics_storage_efficiency_id_seq OWNED BY feature3.metrics_storage_efficiency.id;


--
-- Name: storage_efficiency_history; Type: TABLE; Schema: feature3; Owner: postgres
--

CREATE TABLE feature3.storage_efficiency_history (
    id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    job_id character varying(100) NOT NULL,
    job_name character varying(255) NOT NULL,
    dedup_ratio numeric(6,2),
    compression_ratio numeric(6,2),
    combined_ratio numeric(10,2),
    session_id character varying(100),
    backup_size_gb numeric(10,2),
    stored_size_gb numeric(10,2),
    is_anomaly boolean,
    is_interpolated boolean
);


ALTER TABLE feature3.storage_efficiency_history OWNER TO postgres;

--
-- Name: TABLE storage_efficiency_history; Type: COMMENT; Schema: feature3; Owner: postgres
--

COMMENT ON TABLE feature3.storage_efficiency_history IS 'Feature 3: Historical efficiency data for trend analysis';


--
-- Name: COLUMN storage_efficiency_history.dedup_ratio; Type: COMMENT; Schema: feature3; Owner: postgres
--

COMMENT ON COLUMN feature3.storage_efficiency_history.dedup_ratio IS 'Per-session deduplication ratio';


--
-- Name: COLUMN storage_efficiency_history.compression_ratio; Type: COMMENT; Schema: feature3; Owner: postgres
--

COMMENT ON COLUMN feature3.storage_efficiency_history.compression_ratio IS 'Per-session compression ratio';


--
-- Name: COLUMN storage_efficiency_history.is_anomaly; Type: COMMENT; Schema: feature3; Owner: postgres
--

COMMENT ON COLUMN feature3.storage_efficiency_history.is_anomaly IS 'Flagged as statistical anomaly (3-sigma)';


--
-- Name: storage_efficiency_history_id_seq; Type: SEQUENCE; Schema: feature3; Owner: postgres
--

CREATE SEQUENCE feature3.storage_efficiency_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE feature3.storage_efficiency_history_id_seq OWNER TO postgres;

--
-- Name: storage_efficiency_history_id_seq; Type: SEQUENCE OWNED BY; Schema: feature3; Owner: postgres
--

ALTER SEQUENCE feature3.storage_efficiency_history_id_seq OWNED BY feature3.storage_efficiency_history.id;


--
-- Name: metrics_recovery_verification; Type: TABLE; Schema: feature4; Owner: postgres
--

CREATE TABLE feature4.metrics_recovery_verification (
    id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    job_id character varying(100) NOT NULL,
    job_name character varying(255) NOT NULL,
    job_type character varying(50),
    rto_median_minutes numeric(8,2),
    rto_90th_percentile_minutes numeric(8,2),
    rto_95th_percentile_minutes numeric(8,2),
    rto_confidence_interval_lower numeric(8,2),
    rto_confidence_interval_upper numeric(8,2),
    overall_confidence_score numeric(5,2) NOT NULL,
    recovery_grade character varying(1) NOT NULL,
    test_success_rate_score numeric(5,2) NOT NULL,
    test_recency_score numeric(5,2) NOT NULL,
    rto_predictability_score numeric(5,2) NOT NULL,
    sla_compliance_score numeric(5,2) NOT NULL,
    test_coverage_score numeric(5,2) NOT NULL,
    surebackup_enabled boolean DEFAULT false NOT NULL,
    surebackup_available boolean DEFAULT false NOT NULL,
    surebackup_confidence_score numeric(5,2),
    surebackup_vm_boot_time_ms integer,
    surebackup_verified_drives integer,
    surebackup_failed_drives integer,
    successful_tests integer DEFAULT 0 NOT NULL,
    failed_tests integer DEFAULT 0 NOT NULL,
    total_test_attempts integer DEFAULT 0 NOT NULL,
    success_rate_percentage numeric(5,2),
    last_test_date timestamp without time zone,
    days_since_last_test integer,
    test_recency_status character varying(20),
    target_rto_minutes numeric(8,2),
    predicted_rto_minutes numeric(8,2),
    sla_compliance_status character varying(20),
    sla_buffer_percentage numeric(5,2),
    single_restore_rto_minutes numeric(8,2),
    max_concurrent_restores integer,
    recommended_concurrent_limit integer,
    failure_pattern character varying(50),
    failure_root_cause text,
    priority character varying(20),
    recommendation text NOT NULL,
    next_test_recommended_date date,
    sample_count integer NOT NULL,
    confidence_level character varying(20),
    quality_flags jsonb DEFAULT '{}'::jsonb,
    created_date date GENERATED ALWAYS AS (date(created_at)) STORED,
    CONSTRAINT metrics_recovery_verification_confidence_level_check CHECK (((confidence_level)::text = ANY ((ARRAY['HIGH'::character varying, 'MODERATE'::character varying, 'LOW'::character varying])::text[]))),
    CONSTRAINT metrics_recovery_verification_overall_confidence_score_check CHECK (((overall_confidence_score >= (0)::numeric) AND (overall_confidence_score <= (100)::numeric))),
    CONSTRAINT metrics_recovery_verification_priority_check CHECK (((priority)::text = ANY ((ARRAY['LOW'::character varying, 'MEDIUM'::character varying, 'HIGH'::character varying, 'CRITICAL'::character varying])::text[]))),
    CONSTRAINT metrics_recovery_verification_recovery_grade_check CHECK (((recovery_grade)::text = ANY ((ARRAY['A'::character varying, 'B'::character varying, 'C'::character varying, 'D'::character varying, 'F'::character varying])::text[]))),
    CONSTRAINT metrics_recovery_verification_sla_compliance_status_check CHECK (((sla_compliance_status)::text = ANY ((ARRAY['COMPLIANT'::character varying, 'AT_RISK'::character varying, 'NON_COMPLIANT'::character varying])::text[]))),
    CONSTRAINT metrics_recovery_verification_test_recency_status_check CHECK (((test_recency_status)::text = ANY ((ARRAY['FRESH'::character varying, 'CURRENT'::character varying, 'STALE'::character varying, 'CRITICAL'::character varying])::text[])))
);


ALTER TABLE feature4.metrics_recovery_verification OWNER TO postgres;

--
-- Name: metrics_recovery_verification_id_seq; Type: SEQUENCE; Schema: feature4; Owner: postgres
--

CREATE SEQUENCE feature4.metrics_recovery_verification_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE feature4.metrics_recovery_verification_id_seq OWNER TO postgres;

--
-- Name: metrics_recovery_verification_id_seq; Type: SEQUENCE OWNED BY; Schema: feature4; Owner: postgres
--

ALTER SEQUENCE feature4.metrics_recovery_verification_id_seq OWNED BY feature4.metrics_recovery_verification.id;


--
-- Name: recovery_test_history; Type: TABLE; Schema: feature4; Owner: postgres
--

CREATE TABLE feature4.recovery_test_history (
    id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    restore_session_id character varying(100) NOT NULL,
    job_id character varying(100) NOT NULL,
    job_name character varying(255) NOT NULL,
    start_time timestamp without time zone NOT NULL,
    end_time timestamp without time zone NOT NULL,
    duration_minutes numeric(8,2) NOT NULL,
    result character varying(20) NOT NULL,
    restored_objects_count integer DEFAULT 0 NOT NULL,
    avg_throughput_mbps numeric(8,2),
    peak_throughput_mbps numeric(8,2),
    destination_host character varying(255),
    restore_type character varying(50) NOT NULL,
    surebackup_test_result character varying(20),
    surebackup_boot_time_ms integer,
    surebackup_verified_drives integer DEFAULT 0,
    surebackup_failed_drives integer DEFAULT 0,
    CONSTRAINT recovery_test_history_result_check CHECK (((result)::text = ANY ((ARRAY['Success'::character varying, 'Failed'::character varying, 'Warning'::character varying])::text[]))),
    CONSTRAINT recovery_test_history_surebackup_test_result_check CHECK (((surebackup_test_result)::text = ANY ((ARRAY['Success'::character varying, 'Partial'::character varying, 'Failed'::character varying])::text[])))
);


ALTER TABLE feature4.recovery_test_history OWNER TO postgres;

--
-- Name: recovery_test_history_id_seq; Type: SEQUENCE; Schema: feature4; Owner: postgres
--

CREATE SEQUENCE feature4.recovery_test_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE feature4.recovery_test_history_id_seq OWNER TO postgres;

--
-- Name: recovery_test_history_id_seq; Type: SEQUENCE OWNED BY; Schema: feature4; Owner: postgres
--

ALTER SEQUENCE feature4.recovery_test_history_id_seq OWNED BY feature4.recovery_test_history.id;


--
-- Name: metrics_health_score id; Type: DEFAULT; Schema: feature1; Owner: postgres
--

ALTER TABLE ONLY feature1.metrics_health_score ALTER COLUMN id SET DEFAULT nextval('feature1.metrics_health_score_id_seq'::regclass);


--
-- Name: metrics_job_failures id; Type: DEFAULT; Schema: feature1; Owner: postgres
--

ALTER TABLE ONLY feature1.metrics_job_failures ALTER COLUMN id SET DEFAULT nextval('feature1.metrics_job_failures_id_seq'::regclass);


--
-- Name: capacity_history_raw id; Type: DEFAULT; Schema: feature2; Owner: postgres
--

ALTER TABLE ONLY feature2.capacity_history_raw ALTER COLUMN id SET DEFAULT nextval('feature2.capacity_history_raw_id_seq'::regclass);


--
-- Name: metrics_capacity_forecast id; Type: DEFAULT; Schema: feature2; Owner: postgres
--

ALTER TABLE ONLY feature2.metrics_capacity_forecast ALTER COLUMN id SET DEFAULT nextval('feature2.metrics_capacity_forecast_id_seq'::regclass);


--
-- Name: metrics_storage_efficiency id; Type: DEFAULT; Schema: feature3; Owner: postgres
--

ALTER TABLE ONLY feature3.metrics_storage_efficiency ALTER COLUMN id SET DEFAULT nextval('feature3.metrics_storage_efficiency_id_seq'::regclass);


--
-- Name: storage_efficiency_history id; Type: DEFAULT; Schema: feature3; Owner: postgres
--

ALTER TABLE ONLY feature3.storage_efficiency_history ALTER COLUMN id SET DEFAULT nextval('feature3.storage_efficiency_history_id_seq'::regclass);


--
-- Name: metrics_recovery_verification id; Type: DEFAULT; Schema: feature4; Owner: postgres
--

ALTER TABLE ONLY feature4.metrics_recovery_verification ALTER COLUMN id SET DEFAULT nextval('feature4.metrics_recovery_verification_id_seq'::regclass);


--
-- Name: recovery_test_history id; Type: DEFAULT; Schema: feature4; Owner: postgres
--

ALTER TABLE ONLY feature4.recovery_test_history ALTER COLUMN id SET DEFAULT nextval('feature4.recovery_test_history_id_seq'::regclass);


--
-- Name: metrics_health_score metrics_health_score_pkey; Type: CONSTRAINT; Schema: feature1; Owner: postgres
--

ALTER TABLE ONLY feature1.metrics_health_score
    ADD CONSTRAINT metrics_health_score_pkey PRIMARY KEY (id);


--
-- Name: metrics_job_failures metrics_job_failures_pkey; Type: CONSTRAINT; Schema: feature1; Owner: postgres
--

ALTER TABLE ONLY feature1.metrics_job_failures
    ADD CONSTRAINT metrics_job_failures_pkey PRIMARY KEY (id);


--
-- Name: metrics_health_score unique_health_per_day; Type: CONSTRAINT; Schema: feature1; Owner: postgres
--

ALTER TABLE ONLY feature1.metrics_health_score
    ADD CONSTRAINT unique_health_per_day UNIQUE (created_date);


--
-- Name: metrics_job_failures unique_job_failure_per_day; Type: CONSTRAINT; Schema: feature1; Owner: postgres
--

ALTER TABLE ONLY feature1.metrics_job_failures
    ADD CONSTRAINT unique_job_failure_per_day UNIQUE (job_id, created_date);


--
-- Name: capacity_history_raw capacity_history_raw_pkey; Type: CONSTRAINT; Schema: feature2; Owner: postgres
--

ALTER TABLE ONLY feature2.capacity_history_raw
    ADD CONSTRAINT capacity_history_raw_pkey PRIMARY KEY (id);


--
-- Name: metrics_capacity_forecast metrics_capacity_forecast_pkey; Type: CONSTRAINT; Schema: feature2; Owner: postgres
--

ALTER TABLE ONLY feature2.metrics_capacity_forecast
    ADD CONSTRAINT metrics_capacity_forecast_pkey PRIMARY KEY (id);


--
-- Name: capacity_history_raw unique_capacity_history_raw_per_day; Type: CONSTRAINT; Schema: feature2; Owner: postgres
--

ALTER TABLE ONLY feature2.capacity_history_raw
    ADD CONSTRAINT unique_capacity_history_raw_per_day UNIQUE (repository_id, created_date);


--
-- Name: metrics_capacity_forecast unique_metrics_capacity_forecast_per_day; Type: CONSTRAINT; Schema: feature2; Owner: postgres
--

ALTER TABLE ONLY feature2.metrics_capacity_forecast
    ADD CONSTRAINT unique_metrics_capacity_forecast_per_day UNIQUE (repository_id, created_date);


--
-- Name: metrics_storage_efficiency metrics_storage_efficiency_pkey; Type: CONSTRAINT; Schema: feature3; Owner: postgres
--

ALTER TABLE ONLY feature3.metrics_storage_efficiency
    ADD CONSTRAINT metrics_storage_efficiency_pkey PRIMARY KEY (id);


--
-- Name: storage_efficiency_history storage_efficiency_history_pkey; Type: CONSTRAINT; Schema: feature3; Owner: postgres
--

ALTER TABLE ONLY feature3.storage_efficiency_history
    ADD CONSTRAINT storage_efficiency_history_pkey PRIMARY KEY (id);


--
-- Name: metrics_storage_efficiency unique_efficiency_per_day; Type: CONSTRAINT; Schema: feature3; Owner: postgres
--

ALTER TABLE ONLY feature3.metrics_storage_efficiency
    ADD CONSTRAINT unique_efficiency_per_day UNIQUE (job_id, created_date);


--
-- Name: storage_efficiency_history unique_session_id; Type: CONSTRAINT; Schema: feature3; Owner: postgres
--

ALTER TABLE ONLY feature3.storage_efficiency_history
    ADD CONSTRAINT unique_session_id UNIQUE (session_id);


--
-- Name: metrics_recovery_verification metrics_recovery_verification_pkey; Type: CONSTRAINT; Schema: feature4; Owner: postgres
--

ALTER TABLE ONLY feature4.metrics_recovery_verification
    ADD CONSTRAINT metrics_recovery_verification_pkey PRIMARY KEY (id);


--
-- Name: recovery_test_history recovery_test_history_pkey; Type: CONSTRAINT; Schema: feature4; Owner: postgres
--

ALTER TABLE ONLY feature4.recovery_test_history
    ADD CONSTRAINT recovery_test_history_pkey PRIMARY KEY (id);


--
-- Name: recovery_test_history recovery_test_history_restore_session_id_key; Type: CONSTRAINT; Schema: feature4; Owner: postgres
--

ALTER TABLE ONLY feature4.recovery_test_history
    ADD CONSTRAINT recovery_test_history_restore_session_id_key UNIQUE (restore_session_id);


--
-- Name: metrics_recovery_verification unique_job_per_day; Type: CONSTRAINT; Schema: feature4; Owner: postgres
--

ALTER TABLE ONLY feature4.metrics_recovery_verification
    ADD CONSTRAINT unique_job_per_day UNIQUE (job_id, created_date);


--
-- Name: idx_metrics_health_score_confidence_level; Type: INDEX; Schema: feature1; Owner: postgres
--

CREATE INDEX idx_metrics_health_score_confidence_level ON feature1.metrics_health_score USING btree (confidence_level);


--
-- Name: idx_metrics_health_score_created_at; Type: INDEX; Schema: feature1; Owner: postgres
--

CREATE INDEX idx_metrics_health_score_created_at ON feature1.metrics_health_score USING btree (created_at DESC);


--
-- Name: idx_metrics_health_score_grade; Type: INDEX; Schema: feature1; Owner: postgres
--

CREATE INDEX idx_metrics_health_score_grade ON feature1.metrics_health_score USING btree (grade);


--
-- Name: idx_metrics_health_score_quality_flags; Type: INDEX; Schema: feature1; Owner: postgres
--

CREATE INDEX idx_metrics_health_score_quality_flags ON feature1.metrics_health_score USING gin (quality_flags);


--
-- Name: idx_metrics_health_score_risk_level; Type: INDEX; Schema: feature1; Owner: postgres
--

CREATE INDEX idx_metrics_health_score_risk_level ON feature1.metrics_health_score USING btree (risk_level);


--
-- Name: idx_metrics_job_failures_created_at; Type: INDEX; Schema: feature1; Owner: postgres
--

CREATE INDEX idx_metrics_job_failures_created_at ON feature1.metrics_job_failures USING btree (created_at DESC);


--
-- Name: idx_metrics_job_failures_job_id; Type: INDEX; Schema: feature1; Owner: postgres
--

CREATE INDEX idx_metrics_job_failures_job_id ON feature1.metrics_job_failures USING btree (job_id);


--
-- Name: idx_metrics_job_failures_job_name; Type: INDEX; Schema: feature1; Owner: postgres
--

CREATE INDEX idx_metrics_job_failures_job_name ON feature1.metrics_job_failures USING btree (job_name);


--
-- Name: idx_metrics_job_failures_job_time; Type: INDEX; Schema: feature1; Owner: postgres
--

CREATE INDEX idx_metrics_job_failures_job_time ON feature1.metrics_job_failures USING btree (job_id, created_at DESC);


--
-- Name: idx_metrics_job_failures_priority; Type: INDEX; Schema: feature1; Owner: postgres
--

CREATE INDEX idx_metrics_job_failures_priority ON feature1.metrics_job_failures USING btree (priority);


--
-- Name: idx_capacity_forecast_confidence; Type: INDEX; Schema: feature2; Owner: postgres
--

CREATE INDEX idx_capacity_forecast_confidence ON feature2.metrics_capacity_forecast USING btree (confidence_level);


--
-- Name: idx_capacity_forecast_created_at; Type: INDEX; Schema: feature2; Owner: postgres
--

CREATE INDEX idx_capacity_forecast_created_at ON feature2.metrics_capacity_forecast USING btree (created_at DESC);


--
-- Name: idx_capacity_forecast_days_80; Type: INDEX; Schema: feature2; Owner: postgres
--

CREATE INDEX idx_capacity_forecast_days_80 ON feature2.metrics_capacity_forecast USING btree (days_to_80_percent) WHERE (days_to_80_percent IS NOT NULL);


--
-- Name: idx_capacity_forecast_priority; Type: INDEX; Schema: feature2; Owner: postgres
--

CREATE INDEX idx_capacity_forecast_priority ON feature2.metrics_capacity_forecast USING btree (priority);


--
-- Name: idx_capacity_forecast_quality; Type: INDEX; Schema: feature2; Owner: postgres
--

CREATE INDEX idx_capacity_forecast_quality ON feature2.metrics_capacity_forecast USING gin (quality_flags);


--
-- Name: idx_capacity_forecast_repo_id; Type: INDEX; Schema: feature2; Owner: postgres
--

CREATE INDEX idx_capacity_forecast_repo_id ON feature2.metrics_capacity_forecast USING btree (repository_id);


--
-- Name: idx_capacity_history_created_at; Type: INDEX; Schema: feature2; Owner: postgres
--

CREATE INDEX idx_capacity_history_created_at ON feature2.capacity_history_raw USING btree (created_at);


--
-- Name: idx_capacity_history_repo_time; Type: INDEX; Schema: feature2; Owner: postgres
--

CREATE INDEX idx_capacity_history_repo_time ON feature2.capacity_history_raw USING btree (repository_id, created_at DESC);


--
-- Name: idx_efficiency_history_created; Type: INDEX; Schema: feature3; Owner: postgres
--

CREATE INDEX idx_efficiency_history_created ON feature3.storage_efficiency_history USING btree (created_at);


--
-- Name: idx_efficiency_history_job_time; Type: INDEX; Schema: feature3; Owner: postgres
--

CREATE INDEX idx_efficiency_history_job_time ON feature3.storage_efficiency_history USING btree (job_id, created_at DESC);


--
-- Name: idx_storage_efficiency_created; Type: INDEX; Schema: feature3; Owner: postgres
--

CREATE INDEX idx_storage_efficiency_created ON feature3.metrics_storage_efficiency USING btree (created_at DESC);


--
-- Name: idx_storage_efficiency_grade; Type: INDEX; Schema: feature3; Owner: postgres
--

CREATE INDEX idx_storage_efficiency_grade ON feature3.metrics_storage_efficiency USING btree (efficiency_grade);


--
-- Name: idx_storage_efficiency_job; Type: INDEX; Schema: feature3; Owner: postgres
--

CREATE INDEX idx_storage_efficiency_job ON feature3.metrics_storage_efficiency USING btree (job_id);


--
-- Name: idx_storage_efficiency_priority; Type: INDEX; Schema: feature3; Owner: postgres
--

CREATE INDEX idx_storage_efficiency_priority ON feature3.metrics_storage_efficiency USING btree (priority);


--
-- Name: idx_storage_efficiency_rating; Type: INDEX; Schema: feature3; Owner: postgres
--

CREATE INDEX idx_storage_efficiency_rating ON feature3.metrics_storage_efficiency USING btree (efficiency_rating);


--
-- Name: idx_recovery_verification_created; Type: INDEX; Schema: feature4; Owner: postgres
--

CREATE INDEX idx_recovery_verification_created ON feature4.metrics_recovery_verification USING btree (created_at DESC);


--
-- Name: idx_recovery_verification_job; Type: INDEX; Schema: feature4; Owner: postgres
--

CREATE INDEX idx_recovery_verification_job ON feature4.metrics_recovery_verification USING btree (job_id);


--
-- Name: idx_recovery_verification_priority; Type: INDEX; Schema: feature4; Owner: postgres
--

CREATE INDEX idx_recovery_verification_priority ON feature4.metrics_recovery_verification USING btree (priority);


--
-- Name: idx_recovery_verification_surebackup; Type: INDEX; Schema: feature4; Owner: postgres
--

CREATE INDEX idx_recovery_verification_surebackup ON feature4.metrics_recovery_verification USING btree (surebackup_enabled, surebackup_available);


--
-- Name: idx_test_history_job; Type: INDEX; Schema: feature4; Owner: postgres
--

CREATE INDEX idx_test_history_job ON feature4.recovery_test_history USING btree (job_id);


--
-- Name: idx_test_history_result; Type: INDEX; Schema: feature4; Owner: postgres
--

CREATE INDEX idx_test_history_result ON feature4.recovery_test_history USING btree (result);


--
-- Name: idx_test_history_time; Type: INDEX; Schema: feature4; Owner: postgres
--

CREATE INDEX idx_test_history_time ON feature4.recovery_test_history USING btree (start_time DESC);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT ALL ON SCHEMA public TO feature1_user;


--
-- Name: TABLE metrics_health_score; Type: ACL; Schema: feature1; Owner: postgres
--

GRANT SELECT,INSERT,DELETE ON TABLE feature1.metrics_health_score TO feature1_user;


--
-- Name: SEQUENCE metrics_health_score_id_seq; Type: ACL; Schema: feature1; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE feature1.metrics_health_score_id_seq TO feature1_user;


--
-- Name: TABLE metrics_job_failures; Type: ACL; Schema: feature1; Owner: postgres
--

GRANT SELECT,INSERT,DELETE ON TABLE feature1.metrics_job_failures TO feature1_user;


--
-- Name: SEQUENCE metrics_job_failures_id_seq; Type: ACL; Schema: feature1; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE feature1.metrics_job_failures_id_seq TO feature1_user;


--
-- PostgreSQL database dump complete
--

\unrestrict r1yNdGnyxfzlUakXAyq2VmBrmY1bqwWI3alepXe4i86dbJIOGFjwWSQcc4XFD8K

