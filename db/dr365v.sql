--
-- PostgreSQL database dump
--

\restrict LWZTsRGFysKsAeGaiWF3eOEpXFsahvr3cOucQlePtNVK6g8YmzVxLunnS2BcRUa

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
-- Name: dr365v; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA dr365v;


ALTER SCHEMA dr365v OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: metrics_risk_analysis_consolidated; Type: TABLE; Schema: dr365v; Owner: postgres
--

CREATE TABLE dr365v.metrics_risk_analysis_consolidated (
    id integer NOT NULL,
    job_id uuid NOT NULL,
    job_name character varying(255) NOT NULL,
    vm_tier character varying(50) NOT NULL,
    tier_weight numeric(3,2) NOT NULL,
    job_failure_risk_score integer,
    capacity_risk_score integer,
    efficiency_risk_score integer,
    recovery_risk_score integer,
    data_quality_risk_score integer,
    composite_risk_score integer,
    overall_data_confidence numeric(3,2),
    business_impact_score integer,
    risk_category character varying(50),
    feature_1_status character varying(50),
    feature_2_status character varying(50),
    feature_3_status character varying(50),
    feature_4_status character varying(50),
    quality_flags character varying(255)[],
    analysis_date timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE dr365v.metrics_risk_analysis_consolidated OWNER TO postgres;

--
-- Name: metrics_risk_analysis_consolidated_id_seq; Type: SEQUENCE; Schema: dr365v; Owner: postgres
--

CREATE SEQUENCE dr365v.metrics_risk_analysis_consolidated_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE dr365v.metrics_risk_analysis_consolidated_id_seq OWNER TO postgres;

--
-- Name: metrics_risk_analysis_consolidated_id_seq; Type: SEQUENCE OWNED BY; Schema: dr365v; Owner: postgres
--

ALTER SEQUENCE dr365v.metrics_risk_analysis_consolidated_id_seq OWNED BY dr365v.metrics_risk_analysis_consolidated.id;


--
-- Name: remediation_plans; Type: TABLE; Schema: dr365v; Owner: postgres
--

CREATE TABLE dr365v.remediation_plans (
    plan_id uuid DEFAULT gen_random_uuid() NOT NULL,
    generated_at timestamp without time zone DEFAULT now() NOT NULL,
    risk_id character varying(100) NOT NULL,
    risk_type character varying(50) NOT NULL,
    job_id character varying(100),
    job_name character varying(255),
    vm_tier character varying(50),
    composite_risk_score numeric(5,2) NOT NULL,
    business_impact_score numeric(5,2) NOT NULL,
    confidence_level character varying(20),
    issue_summary text NOT NULL,
    pattern_analysis text,
    root_cause_hypotheses text[],
    investigation_steps jsonb NOT NULL,
    remediation_options jsonb NOT NULL,
    success_criteria text NOT NULL,
    urgency character varying(20),
    estimated_effort_hours numeric(5,2),
    complexity character varying(20),
    prerequisites text[],
    warnings text[],
    plan_json jsonb NOT NULL,
    status character varying(20) DEFAULT 'GENERATED'::character varying,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    is_test_data boolean DEFAULT false,
    CONSTRAINT remediation_plans_business_impact_score_check CHECK (((business_impact_score >= (0)::numeric) AND (business_impact_score <= (100)::numeric))),
    CONSTRAINT remediation_plans_complexity_check CHECK (((complexity)::text = ANY ((ARRAY['LOW'::character varying, 'MEDIUM'::character varying, 'HIGH'::character varying])::text[]))),
    CONSTRAINT remediation_plans_composite_risk_score_check CHECK (((composite_risk_score >= (0)::numeric) AND (composite_risk_score <= (100)::numeric))),
    CONSTRAINT remediation_plans_confidence_level_check CHECK (((confidence_level)::text = ANY ((ARRAY['HIGH'::character varying, 'MODERATE'::character varying, 'LOW'::character varying, 'INSUFFICIENT'::character varying])::text[]))),
    CONSTRAINT remediation_plans_estimated_effort_hours_check CHECK ((estimated_effort_hours >= (0)::numeric)),
    CONSTRAINT remediation_plans_risk_type_check CHECK (((risk_type)::text = ANY ((ARRAY['job_failure'::character varying, 'capacity'::character varying, 'efficiency'::character varying, 'recovery'::character varying, 'data_quality'::character varying])::text[]))),
    CONSTRAINT remediation_plans_status_check CHECK (((status)::text = ANY ((ARRAY['GENERATED'::character varying, 'REVIEWED'::character varying, 'INVESTIGATING'::character varying, 'IMPLEMENTING'::character varying, 'COMPLETED'::character varying, 'CANCELLED'::character varying])::text[]))),
    CONSTRAINT remediation_plans_urgency_check CHECK (((urgency)::text = ANY ((ARRAY['LOW'::character varying, 'MEDIUM'::character varying, 'HIGH'::character varying, 'CRITICAL'::character varying])::text[]))),
    CONSTRAINT remediation_plans_vm_tier_check CHECK (((vm_tier)::text = ANY ((ARRAY['CRITICAL'::character varying, 'HIGH'::character varying, 'MEDIUM'::character varying, 'LOW'::character varying])::text[])))
);


ALTER TABLE dr365v.remediation_plans OWNER TO postgres;

--
-- Name: TABLE remediation_plans; Type: COMMENT; Schema: dr365v; Owner: postgres
--

COMMENT ON TABLE dr365v.remediation_plans IS 'Remediation guidance plans generated by Feature 6 (planning only, no execution)';


--
-- Name: COLUMN remediation_plans.plan_json; Type: COMMENT; Schema: dr365v; Owner: postgres
--

COMMENT ON COLUMN dr365v.remediation_plans.plan_json IS 'Complete plan in JSON format for MCP server consumption';


--
-- Name: COLUMN remediation_plans.status; Type: COMMENT; Schema: dr365v; Owner: postgres
--

COMMENT ON COLUMN dr365v.remediation_plans.status IS 'Lifecycle status of the plan';


--
-- Name: COLUMN remediation_plans.is_test_data; Type: COMMENT; Schema: dr365v; Owner: postgres
--

COMMENT ON COLUMN dr365v.remediation_plans.is_test_data IS 'TRUE if plan was generated for demo/testing purposes (not production)';


--
-- Name: metrics_risk_analysis_consolidated id; Type: DEFAULT; Schema: dr365v; Owner: postgres
--

ALTER TABLE ONLY dr365v.metrics_risk_analysis_consolidated ALTER COLUMN id SET DEFAULT nextval('dr365v.metrics_risk_analysis_consolidated_id_seq'::regclass);


--
-- Name: metrics_risk_analysis_consolidated metrics_risk_analysis_consolidated_pkey; Type: CONSTRAINT; Schema: dr365v; Owner: postgres
--

ALTER TABLE ONLY dr365v.metrics_risk_analysis_consolidated
    ADD CONSTRAINT metrics_risk_analysis_consolidated_pkey PRIMARY KEY (id);


--
-- Name: remediation_plans remediation_plans_pkey; Type: CONSTRAINT; Schema: dr365v; Owner: postgres
--

ALTER TABLE ONLY dr365v.remediation_plans
    ADD CONSTRAINT remediation_plans_pkey PRIMARY KEY (plan_id);


--
-- Name: idx_remediation_plans_active; Type: INDEX; Schema: dr365v; Owner: postgres
--

CREATE INDEX idx_remediation_plans_active ON dr365v.remediation_plans USING btree (urgency, composite_risk_score) WHERE ((status)::text = ANY ((ARRAY['GENERATED'::character varying, 'REVIEWED'::character varying, 'INVESTIGATING'::character varying])::text[]));


--
-- Name: idx_remediation_plans_generated; Type: INDEX; Schema: dr365v; Owner: postgres
--

CREATE INDEX idx_remediation_plans_generated ON dr365v.remediation_plans USING btree (generated_at DESC);


--
-- Name: idx_remediation_plans_job_id; Type: INDEX; Schema: dr365v; Owner: postgres
--

CREATE INDEX idx_remediation_plans_job_id ON dr365v.remediation_plans USING btree (job_id);


--
-- Name: idx_remediation_plans_job_risk; Type: INDEX; Schema: dr365v; Owner: postgres
--

CREATE UNIQUE INDEX idx_remediation_plans_job_risk ON dr365v.remediation_plans USING btree (job_id, risk_type);


--
-- Name: idx_remediation_plans_json_gin; Type: INDEX; Schema: dr365v; Owner: postgres
--

CREATE INDEX idx_remediation_plans_json_gin ON dr365v.remediation_plans USING gin (plan_json);


--
-- Name: idx_remediation_plans_risk_id; Type: INDEX; Schema: dr365v; Owner: postgres
--

CREATE INDEX idx_remediation_plans_risk_id ON dr365v.remediation_plans USING btree (risk_id);


--
-- Name: idx_remediation_plans_risk_score; Type: INDEX; Schema: dr365v; Owner: postgres
--

CREATE INDEX idx_remediation_plans_risk_score ON dr365v.remediation_plans USING btree (composite_risk_score DESC);


--
-- Name: idx_remediation_plans_risk_type; Type: INDEX; Schema: dr365v; Owner: postgres
--

CREATE INDEX idx_remediation_plans_risk_type ON dr365v.remediation_plans USING btree (risk_type);


--
-- Name: idx_remediation_plans_status; Type: INDEX; Schema: dr365v; Owner: postgres
--

CREATE INDEX idx_remediation_plans_status ON dr365v.remediation_plans USING btree (status);


--
-- Name: idx_remediation_plans_urgency; Type: INDEX; Schema: dr365v; Owner: postgres
--

CREATE INDEX idx_remediation_plans_urgency ON dr365v.remediation_plans USING btree (urgency);


--
-- Name: idx_risk_consolidated_date; Type: INDEX; Schema: dr365v; Owner: postgres
--

CREATE INDEX idx_risk_consolidated_date ON dr365v.metrics_risk_analysis_consolidated USING btree (analysis_date DESC);


--
-- Name: idx_risk_consolidated_impact; Type: INDEX; Schema: dr365v; Owner: postgres
--

CREATE INDEX idx_risk_consolidated_impact ON dr365v.metrics_risk_analysis_consolidated USING btree (business_impact_score DESC);


--
-- PostgreSQL database dump complete
--

\unrestrict LWZTsRGFysKsAeGaiWF3eOEpXFsahvr3cOucQlePtNVK6g8YmzVxLunnS2BcRUa

