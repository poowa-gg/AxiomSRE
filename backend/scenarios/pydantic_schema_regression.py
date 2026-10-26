"""
Scenario 2: Upstream Library Breaking Change (Pydantic v2 Migration Regression)
Demonstrates:
- Code parsing and AST inspection with NVIDIA Nemotron
- Live GitHub Issue & Changelog Triangulation via Tavily Search
- Formal verification of schema contracts via Nemotron-3 Ultra
- Automated sandbox test execution and Git patch generation
"""

from typing import Dict, Any, List
from backend.api.schemas import (
    IncidentSeverity,
    IncidentStatus,
    NodeType,
    TelemetryLog,
    IncidentSignature,
    TavilyEvidence,
    CausalNode,
    CausalEdge,
    CausalGraph,
    RemediationPlan,
    SandboxTestResult
)

SCENARIO_ID = "INC-4022-PYDANTIC-BREAK"
TITLE = "Authentication Service 500 Spike on Nullable JWT Metadata Claims"
SERVICE = "identity-auth-service"
SEVERITY = IncidentSeverity.P1_HIGH
ERROR_RATE_PCT = 34.6
P99_LATENCY_MS = 240.0
BURN_RATE_USD = 4200.0  # $4,200 per minute

SAMPLE_LOGS: List[TelemetryLog] = [
    TelemetryLog(
        timestamp="2026-10-26T01:18:10.420Z",
        service="identity-auth-service",
        level="ERROR",
        message="pydantic_core._pydantic_core.ValidationError: 1 validation error for UserSessionToken\norganization_id\n  Input should be a valid string [type=string_type, input_value=None, input_type=NoneType]",
        latency_ms=12.4,
        status_code=500,
        trace_id="tr-auth-9901-x1",
        stack_trace="ValidationError in auth_middleware.py:42 in validate_session_token"
    ),
    TelemetryLog(
        timestamp="2026-10-26T01:18:11.890Z",
        service="identity-auth-service",
        level="ERROR",
        message="Failed to unpack session claim for individual consumer user_id=usr_991823: organization_id is None",
        latency_ms=8.1,
        status_code=500,
        trace_id="tr-auth-9901-x2",
        stack_trace="pydantic.errors.PydanticCustomError: Schema validation failure in session.py:64"
    ),
    TelemetryLog(
        timestamp="2026-10-26T01:18:12.301Z",
        service="identity-auth-service",
        level="WARN",
        message="Upstream consumer login drop: 34.6% of requests failing OAuth callback across B2C mobile apps",
        latency_ms=None,
        status_code=500,
        trace_id="tr-auth-9901-x3",
        stack_trace=None
    )
]

ORIGINAL_BUGGY_CODE = '''from typing import Optional
from pydantic import BaseModel, Field

class UserSessionToken(BaseModel):
    user_id: str
    email: str
    role: str = "member"
    # BUG: Under Pydantic v2, `str = None` is strictly disallowed and raises ValidationError
    # when input_value is None. In v1, it implicitly defaulted to Optional[str].
    organization_id: str = None
    workspace_slug: str = None

def validate_session_token(payload: dict) -> UserSessionToken:
    return UserSessionToken.model_validate(payload)
'''

PATCHED_CODE = '''from typing import Optional
from pydantic import BaseModel, Field

class UserSessionToken(BaseModel):
    user_id: str
    email: str
    role: str = "member"
    # FIXED: Explicit Optional[str] with explicit None default satisfies Pydantic v2 strict type invariants
    organization_id: Optional[str] = Field(default=None, description="Optional organization identifier for enterprise accounts")
    workspace_slug: Optional[str] = Field(default=None, description="Optional workspace slug")

def validate_session_token(payload: dict) -> UserSessionToken:
    return UserSessionToken.model_validate(payload)
'''

REGRESSION_TEST_CODE = '''import pytest
from pydantic import ValidationError

def test_pydantic_v2_nullable_session_token_validation():
    from auth_middleware import UserSessionToken, validate_session_token

    # Case 1: Individual consumer user with None organization_id
    consumer_payload = {
        "user_id": "usr_991823",
        "email": "sarah.chen@example.com",
        "role": "consumer",
        "organization_id": None,
        "workspace_slug": None
    }
    token = validate_session_token(consumer_payload)
    assert token.user_id == "usr_991823"
    assert token.organization_id is None

    # Case 2: Enterprise user with populated organization_id
    enterprise_payload = {
        "user_id": "usr_551002",
        "email": "alex@enterprise.com",
        "role": "admin",
        "organization_id": "org_nebius_ai_99",
        "workspace_slug": "global-infra"
    }
    enterprise_token = validate_session_token(enterprise_payload)
    assert enterprise_token.organization_id == "org_nebius_ai_99"
'''

UNIFIED_DIFF = '''--- a/auth_middleware.py
+++ b/auth_middleware.py
@@ -1,13 +1,13 @@
 from typing import Optional
 from pydantic import BaseModel, Field

 class UserSessionToken(BaseModel):
     user_id: str
     email: str
     role: str = "member"
-    organization_id: str = None
-    workspace_slug: str = None
+    organization_id: Optional[str] = Field(default=None, description="Optional organization identifier for enterprise accounts")
+    workspace_slug: Optional[str] = Field(default=None, description="Optional workspace slug")

 def validate_session_token(payload: dict) -> UserSessionToken:
     return UserSessionToken.model_validate(payload)
'''

def get_scenario_data() -> Dict[str, Any]:
    signature = IncidentSignature(
        incident_id=SCENARIO_ID,
        title=TITLE,
        service=SERVICE,
        severity=SEVERITY,
        primary_error="pydantic_core.ValidationError: Input should be a valid string [type=string_type, input_value=None]",
        error_frequency_per_sec=32.4,
        affected_endpoints=["/v1/auth/callback", "/v1/auth/session/verify"],
        suspected_domains=["github.com/pydantic/pydantic", "docs.pydantic.dev"],
        tavily_search_queries=[
            "site:github.com/pydantic/pydantic 'Input should be a valid string' NoneType v2 migration",
            "pydantic v2 breaking changes nullable fields Optional default None",
            "pydantic.errors.PydanticCustomError organization_id is None"
        ],
        summary="A recent automated library upgrade to Pydantic v2 introduced breaking validation behavior on nullable schema fields that previously defaulted to None in Pydantic v1."
    )

    tavily_evidences = [
        TavilyEvidence(
            title="Pydantic Migration Guide: Required fields and explicit typing in V2",
            url="https://docs.pydantic.dev/latest/migration/#required-optional-and-nullable-fields",
            source="docs.pydantic.dev",
            snippet="In Pydantic V1, `field: str = None` implicitly converted the field to nullable `Optional[str]`. In Pydantic V2, this is strictly enforced: `str` requires an actual string, and `None` is rejected with 'Input should be a valid string'. You must use `Optional[str] = Field(default=None)`.",
            relevance_score=0.99,
            publication_time="Official Documentation",
            is_authoritative=True,
            incident_correlation="Exact root cause: Dependabot merged pydantic 2.x which broke all B2C session tokens lacking organization_id."
        ),
        TavilyEvidence(
            title="GitHub Issue #6532: Pydantic v2 ValidationError when passing None to field with default None",
            url="https://github.com/pydantic/pydantic/issues/6532",
            source="github.com",
            snippet="Issue: 'Input should be a valid string' occurs when fields with `field: str = None` receive explicit `{\"field\": null}` in incoming JSON payloads. Resolution: specify `Optional[str] = Field(default=None)`.",
            relevance_score=0.96,
            publication_time="GitHub Discussion",
            is_authoritative=True,
            incident_correlation="Corroborates the exact error stack trace logged in auth_middleware.py line 42."
        )
    ]

    causal_nodes = [
        CausalNode(
            id="NODE-DEP-UPGRADE",
            label="Automated Dependabot Merge: Pydantic v1.10 -> v2.6.4",
            type=NodeType.EXTERNAL_FACTOR,
            confidence=0.99,
            service_or_entity="GitHub Repository / Dependencies",
            evidence_snippet="Commit 4a89fbc updated requirements.txt without updating model type annotations."
        ),
        CausalNode(
            id="NODE-ROOT-SCHEMA",
            label="Implicit Nullability Type Annotation Defect in UserSessionToken",
            type=NodeType.ROOT_CAUSE,
            confidence=0.98,
            service_or_entity="identity-auth-service",
            evidence_snippet="organization_id: str = None rejects explicit null values in Pydantic v2."
        ),
        CausalNode(
            id="NODE-INT-B2C",
            label="Consumer Session Invalidation (34.6% of Traffic)",
            type=NodeType.INTERMEDIATE_CASCADE,
            confidence=0.95,
            service_or_entity="identity-auth-service",
            evidence_snippet="Consumer accounts have no organization_id; JWT claim carries explicit 'organization_id': null."
        ),
        CausalNode(
            id="NODE-SYM-LOGIN",
            label="OAuth Callback Outage for Consumer Accounts",
            type=NodeType.SURFACE_SYMPTOM,
            confidence=1.00,
            service_or_entity="identity-auth-service",
            evidence_snippet="HTTP 500 error spikes on /v1/auth/callback with $4,200/min burn rate."
        )
    ]

    causal_edges = [
        CausalEdge(source="NODE-DEP-UPGRADE", target="NODE-ROOT-SCHEMA", relationship="TRIGGERS_BREAKING_SEMANTICS", confidence=0.99),
        CausalEdge(source="NODE-ROOT-SCHEMA", target="NODE-INT-B2C", relationship="FAILS_SCHEMA_VALIDATION", confidence=0.98),
        CausalEdge(source="NODE-INT-B2C", target="NODE-SYM-LOGIN", relationship="CAUSES_OAUTH_FAILURE", confidence=0.99)
    ]

    causal_graph = CausalGraph(
        nodes=causal_nodes,
        edges=causal_edges,
        root_cause_node_id="NODE-ROOT-SCHEMA",
        root_cause_explanation="Automated dependency upgrade to Pydantic v2 triggered strict type validation. In UserSessionToken, organization_id and workspace_slug were declared as `str = None` instead of `Optional[str] = Field(default=None)`, causing Pydantic v2 to reject incoming consumer tokens carrying null values.",
        mathematical_confidence=0.985,
        counterfactual_proof="Theorem: Re-annotating fields as Optional[str] restores backward compatibility with null JSON tokens while maintaining strict validation for enterprise non-null fields."
    )

    remediation = RemediationPlan(
        immediate_mitigation="Temporarily pin Pydantic to ==1.10.15 or hot-patch UserSessionToken schema.",
        mitigation_command="pip install 'pydantic<2.0.0' && kill -HUP $(pgrep uvicorn)",
        target_file="auth_middleware.py",
        original_code_snippet=ORIGINAL_BUGGY_CODE,
        patched_code_snippet=PATCHED_CODE,
        unified_git_diff=UNIFIED_DIFF,
        regression_test_code=REGRESSION_TEST_CODE,
        sandbox_result=SandboxTestResult(
            test_suite_name="test_pydantic_v2_nullable_session_token_validation",
            tests_run=2,
            tests_passed=2,
            tests_failed=0,
            exit_code=0,
            execution_time_ms=88.4,
            raw_output="tests/test_auth_middleware.py::test_consumer_null_org_id PASSED [ 50%]\ntests/test_auth_middleware.py::test_enterprise_valid_org_id PASSED [100%]\n======================= 2 passed in 0.09s =======================",
            verified_safe=True
        ),
        rollback_procedure="git checkout HEAD~1 auth_middleware.py",
        estimated_downtime_saved_min=30,
        financial_loss_prevented_usd=126000.0
    )

    return {
        "id": SCENARIO_ID,
        "title": TITLE,
        "service": SERVICE,
        "severity": SEVERITY,
        "status": IncidentStatus.REMEDIATION_VERIFIED,
        "signature": signature,
        "tavily_evidences": tavily_evidences,
        "causal_graph": causal_graph,
        "remediation": remediation,
        "logs": SAMPLE_LOGS
    }
