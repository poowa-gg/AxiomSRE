from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class IncidentSeverity(str, Enum):
    P0_CRITICAL = "P0_CRITICAL"
    P1_HIGH = "P1_HIGH"
    P2_MEDIUM = "P2_MEDIUM"
    P3_LOW = "P3_LOW"

class IncidentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INVESTIGATING = "INVESTIGATING"
    ROOT_CAUSE_IDENTIFIED = "ROOT_CAUSE_IDENTIFIED"
    REMEDIATION_VERIFIED = "REMEDIATION_VERIFIED"
    RESOLVED = "RESOLVED"

class NodeType(str, Enum):
    ROOT_CAUSE = "ROOT_CAUSE"
    INTERMEDIATE_CASCADE = "INTERMEDIATE_CASCADE"
    SURFACE_SYMPTOM = "SURFACE_SYMPTOM"
    EXTERNAL_FACTOR = "EXTERNAL_FACTOR"

class TelemetryLog(BaseModel):
    timestamp: str
    service: str
    level: str  # ERROR, WARN, INFO, FATAL
    message: str
    latency_ms: Optional[float] = None
    status_code: Optional[int] = None
    trace_id: Optional[str] = None
    stack_trace: Optional[str] = None

class IncidentSignature(BaseModel):
    incident_id: str
    title: str
    service: str
    severity: IncidentSeverity
    primary_error: str
    error_frequency_per_sec: float
    affected_endpoints: List[str]
    suspected_domains: List[str]
    tavily_search_queries: List[str]
    summary: str

class TavilyEvidence(BaseModel):
    title: str
    url: str
    source: str
    snippet: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    publication_time: Optional[str] = None
    is_authoritative: bool = True
    incident_correlation: str

class CausalNode(BaseModel):
    id: str
    label: str
    type: NodeType
    confidence: float = Field(ge=0.0, le=1.0)
    service_or_entity: str
    evidence_snippet: str

class CausalEdge(BaseModel):
    source: str
    target: str
    relationship: str  # e.g., "TRIGGERS", "AMPLIFIES", "BLOCKS", "CORRUPTS"
    confidence: float = Field(ge=0.0, le=1.0)

class CausalGraph(BaseModel):
    nodes: List[CausalNode]
    edges: List[CausalEdge]
    root_cause_node_id: str
    root_cause_explanation: str
    mathematical_confidence: float = Field(ge=0.0, le=1.0)
    counterfactual_proof: str

class SandboxTestResult(BaseModel):
    test_suite_name: str
    tests_run: int
    tests_passed: int
    tests_failed: int
    exit_code: int
    execution_time_ms: float
    raw_output: str
    verified_safe: bool

class RemediationPlan(BaseModel):
    immediate_mitigation: str
    mitigation_command: Optional[str] = None
    target_file: str
    original_code_snippet: str
    patched_code_snippet: str
    unified_git_diff: str
    regression_test_code: str
    sandbox_result: Optional[SandboxTestResult] = None
    rollback_procedure: str
    estimated_downtime_saved_min: int
    financial_loss_prevented_usd: float

class AgentStep(BaseModel):
    step_id: str
    agent_name: str
    model_name: str
    status: str  # "RUNNING", "COMPLETED", "FAILED"
    action: str
    thought_trace: str
    execution_time_ms: float
    artifacts_generated: Optional[Dict[str, Any]] = None

class IncidentAnalysisResponse(BaseModel):
    incident_id: str
    title: str
    service: str
    severity: IncidentSeverity
    status: IncidentStatus
    signature: IncidentSignature
    tavily_evidences: List[TavilyEvidence]
    causal_graph: CausalGraph
    remediation: RemediationPlan
    agent_trace: List[AgentStep]
    total_analysis_time_ms: float
    models_used: Dict[str, str]

class IncidentSummaryItem(BaseModel):
    id: str
    title: str
    service: str
    severity: IncidentSeverity
    status: IncidentStatus
    timestamp: str
    error_rate_pct: float
    p99_latency_ms: float
    financial_burn_rate_usd_per_min: float
    description: str

class PostMortemReport(BaseModel):
    incident_id: str
    title: str
    date: str
    duration_minutes: int
    severity: IncidentSeverity
    lead_sre: str
    executive_summary: str
    impact_metrics: Dict[str, Any]
    timeline: List[Dict[str, str]]
    root_cause_analysis: str
    tavily_external_corroboration: List[Dict[str, str]]
    remediation_applied: str
    action_items_preventative: List[Dict[str, str]]
    markdown_document: str
