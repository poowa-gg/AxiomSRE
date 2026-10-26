"""
Scenario 1: External Cloudflare Edge CDN Degradation with Internal Cascading Thundering Herd
Demonstrates:
- High-speed anomaly extraction via Nemotron-3 Super
- Live Web Grounding via Tavily Search (detecting external cloud provider incidents)
- Deep Causal DAG construction via Nemotron-3 Ultra (550B)
- Safe circuit-breaker patch synthesis and isolated test execution
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

SCENARIO_ID = "INC-8921-CF-OUTAGE"
TITLE = "Cascading 504 Gateway Timeouts in Payment Webhook Dispatcher"
SERVICE = "checkout-webhook-service"
SEVERITY = IncidentSeverity.P0_CRITICAL
ERROR_RATE_PCT = 42.8
P99_LATENCY_MS = 14850.0
BURN_RATE_USD = 8400.0  # $8,400 per minute revenue loss

SAMPLE_LOGS: List[TelemetryLog] = [
    TelemetryLog(
        timestamp="2026-10-26T01:14:02.102Z",
        service="checkout-webhook-service",
        level="ERROR",
        message="HTTP POST https://api.gateway.enterprise.com/v1/payments/verify timed out after 10000ms",
        latency_ms=10002.4,
        status_code=504,
        trace_id="tr-88912-aa01",
        stack_trace="httpx.ReadTimeout: The read operation timed out at client.post() in webhook_dispatcher.py:48"
    ),
    TelemetryLog(
        timestamp="2026-10-26T01:14:03.450Z",
        service="checkout-webhook-service",
        level="ERROR",
        message="Connection reset by peer while establishing TLS handshake to edge proxy 104.16.132.229:443",
        latency_ms=480.1,
        status_code=502,
        trace_id="tr-88912-aa02",
        stack_trace="ConnectionResetError: [Errno 104] Connection reset by peer in socket.py:728"
    ),
    TelemetryLog(
        timestamp="2026-10-26T01:14:05.118Z",
        service="checkout-webhook-service",
        level="WARN",
        message="Worker thread pool exhaustion warning: 96/100 active connections waiting on blocked I/O",
        latency_ms=None,
        status_code=None,
        trace_id="tr-88912-sys01",
        stack_trace=None
    ),
    TelemetryLog(
        timestamp="2026-10-26T01:14:06.882Z",
        service="checkout-webhook-service",
        level="FATAL",
        message="Circuit breaker absent. Retrying all 1,420 unacknowledged transactions immediately. Queue size: 14,200",
        latency_ms=None,
        status_code=503,
        trace_id="tr-88912-fatal",
        stack_trace="RuntimeError: ThreadPoolExecutor saturated in webhook_dispatcher.py:112"
    )
]

ORIGINAL_BUGGY_CODE = '''import time
import httpx

class WebhookDispatcher:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.client = httpx.Client(timeout=10.0)

    def dispatch(self, payload: dict) -> bool:
        # BUG: Blind aggressive retries with 0 jitter when upstream edge fails
        retries = 5
        for attempt in range(retries):
            try:
                response = self.client.post(self.endpoint, json=payload)
                if response.status_code == 200:
                    return True
            except (httpx.TimeoutException, httpx.NetworkError):
                # Immediate retry floods the connection pool during edge degradation
                time.sleep(0.1)
        return False
'''

PATCHED_CODE = '''import time
import random
import httpx

class CircuitBreakerOpenException(Exception):
    pass

class WebhookDispatcher:
    def __init__(self, endpoint: str, failure_threshold: int = 3, reset_timeout: float = 30.0):
        self.endpoint = endpoint
        self.client = httpx.Client(timeout=3.0)
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.consecutive_failures = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def dispatch(self, payload: dict) -> bool:
        now = time.time()
        # Fast-fail if circuit breaker is open to prevent thread starvation
        if self.state == "OPEN":
            if now - self.last_failure_time > self.reset_timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenException("Circuit breaker is OPEN. Fast-failing downstream requests.")

        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                response = self.client.post(self.endpoint, json=payload)
                if response.status_code == 200:
                    self.consecutive_failures = 0
                    self.state = "CLOSED"
                    return True
                self.consecutive_failures += 1
            except (httpx.TimeoutException, httpx.NetworkError):
                self.consecutive_failures += 1
                if self.consecutive_failures >= self.failure_threshold:
                    self.state = "OPEN"
                    self.last_failure_time = now
                    raise CircuitBreakerOpenException("Upstream edge failure threshold exceeded. Tripping circuit breaker.")
                # Exponential backoff with full jitter to avoid thundering herd
                backoff = (2 ** attempt) * 0.5 + random.uniform(0.1, 0.5)
                time.sleep(backoff)
        return False
'''

REGRESSION_TEST_CODE = '''import pytest
import httpx
from unittest.mock import patch, MagicMock

def test_circuit_breaker_trips_and_prevents_thundering_herd():
    from webhook_dispatcher import WebhookDispatcher, CircuitBreakerOpenException

    dispatcher = WebhookDispatcher(endpoint="https://api.gateway.enterprise.com/v1/payments", failure_threshold=2)

    # Mock timeout failures simulating Cloudflare edge outage
    with patch.object(dispatcher.client, "post", side_effect=httpx.ReadTimeout("Edge timeout")):
        # First attempt fails and increments counter
        with pytest.raises(CircuitBreakerOpenException):
            dispatcher.dispatch({"order_id": "ORD-1001", "amount": 99.50})
        
        assert dispatcher.state == "OPEN", "Circuit breaker must transition to OPEN upon exceeding failure threshold"

        # Subsequent attempts must immediately fast-fail with 0 network latency, protecting thread pool
        with pytest.raises(CircuitBreakerOpenException) as excinfo:
            dispatcher.dispatch({"order_id": "ORD-1002", "amount": 45.00})
        
        assert "Circuit breaker is OPEN" in str(excinfo.value)
'''

UNIFIED_DIFF = '''--- a/webhook_dispatcher.py
+++ b/webhook_dispatcher.py
@@ -1,17 +1,41 @@
 import time
+import random
 import httpx

+class CircuitBreakerOpenException(Exception):
+    pass
+
 class WebhookDispatcher:
-    def __init__(self, endpoint: str):
+    def __init__(self, endpoint: str, failure_threshold: int = 3, reset_timeout: float = 30.0):
         self.endpoint = endpoint
-        self.client = httpx.Client(timeout=10.0)
+        self.client = httpx.Client(timeout=3.0)
+        self.failure_threshold = failure_threshold
+        self.reset_timeout = reset_timeout
+        self.consecutive_failures = 0
+        self.last_failure_time = 0.0
+        self.state = "CLOSED"

     def dispatch(self, payload: dict) -> bool:
-        retries = 5
-        for attempt in range(retries):
+        now = time.time()
+        if self.state == "OPEN":
+            if now - self.last_failure_time > self.reset_timeout:
+                self.state = "HALF_OPEN"
+            else:
+                raise CircuitBreakerOpenException("Circuit breaker is OPEN. Fast-failing downstream requests.")
+
+        max_attempts = 2
+        for attempt in range(max_attempts):
             try:
                 response = self.client.post(self.endpoint, json=payload)
                 if response.status_code == 200:
+                    self.consecutive_failures = 0
+                    self.state = "CLOSED"
                     return True
+                self.consecutive_failures += 1
             except (httpx.TimeoutException, httpx.NetworkError):
-                time.sleep(0.1)
+                self.consecutive_failures += 1
+                if self.consecutive_failures >= self.failure_threshold:
+                    self.state = "OPEN"
+                    self.last_failure_time = now
+                    raise CircuitBreakerOpenException("Upstream edge failure threshold exceeded. Tripping circuit breaker.")
+                backoff = (2 ** attempt) * 0.5 + random.uniform(0.1, 0.5)
+                time.sleep(backoff)
         return False
'''

def get_scenario_data() -> Dict[str, Any]:
    signature = IncidentSignature(
        incident_id=SCENARIO_ID,
        title=TITLE,
        service=SERVICE,
        severity=SEVERITY,
        primary_error="504 Gateway Timeout & ConnectionResetError: [Errno 104]",
        error_frequency_per_sec=48.2,
        affected_endpoints=["/v1/payments/verify", "/v1/orders/webhook"],
        suspected_domains=["cloudflarestatus.com", "gateway.enterprise.com", "api.stripe.com"],
        tavily_search_queries=[
            "site:cloudflarestatus.com 'degraded performance' OR 'incident'",
            "Cloudflare edge 504 Gateway Timeout North America network incident today",
            "httpx ReadTimeout connection reset by peer edge proxy mitigation"
        ],
        summary="Upstream Edge CDN (Cloudflare) experiencing severe packet drops in us-east region. Internal webhook dispatcher lacks a circuit breaker, causing aggressive unjittered retries that saturated the thread pool."
    )

    tavily_evidences = [
        TavilyEvidence(
            title="Cloudflare Status: Degradation in North America Core Edge Routers",
            url="https://www.cloudflarestatus.com/incidents/cf-na-20261025-edge",
            source="cloudflarestatus.com",
            snippet="Identified: We are observing elevated latency and 502/504 errors affecting edge TLS handshakes and upstream proxying across multiple US East points of presence (IAD, EWR, ATL). Engineers are applying route mitigation.",
            relevance_score=0.98,
            publication_time="14 minutes ago",
            is_authoritative=True,
            incident_correlation="Direct causal origin: 94% of failed requests originate from or route through affected us-east edge nodes."
        ),
        TavilyEvidence(
            title="NVD & High-Volume SRE Advisory: Mitigating Thundering Herd During CDN Outages",
            url="https://sre.google/sre-book/addressing-cascading-failures/",
            source="sre.google",
            snippet="When an external dependency suffers latency degradation, client retry storms turn a temporary external slowdown into an internal total system blackout. Adaptive circuit breaking with full jitter backoff is mandatory.",
            relevance_score=0.91,
            publication_time="2026 Reference",
            is_authoritative=True,
            incident_correlation="Explains why internal thread pool of 100 workers collapsed under 1,420 unacknowledged transactions."
        )
    ]

    causal_nodes = [
        CausalNode(
            id="NODE-EXT-CF",
            label="Cloudflare US-East Edge Router Packet Drop (CF-INC-99120)",
            type=NodeType.EXTERNAL_FACTOR,
            confidence=0.99,
            service_or_entity="Cloudflare Edge Network",
            evidence_snippet="Cloudflare official status advisory confirmed packet loss and TLS reset across IAD/EWR edge nodes."
        ),
        CausalNode(
            id="NODE-ROOT-CB",
            label="Missing Circuit Breaker & Unjittered Retry Storm",
            type=NodeType.ROOT_CAUSE,
            confidence=0.96,
            service_or_entity="checkout-webhook-service",
            evidence_snippet="webhook_dispatcher.py loops 5 times with static 0.1s sleep upon 504 timeout."
        ),
        CausalNode(
            id="NODE-INT-POOL",
            label="Thread Pool Exhaustion (96/100 Workers Blocked)",
            type=NodeType.INTERMEDIATE_CASCADE,
            confidence=0.94,
            service_or_entity="checkout-webhook-service",
            evidence_snippet="10000ms read timeouts holding socket descriptors open for 10s per worker."
        ),
        CausalNode(
            id="NODE-SYM-504",
            label="Payment Webhook Ingress Complete Outage (42.8% Error Rate)",
            type=NodeType.SURFACE_SYMPTOM,
            confidence=1.00,
            service_or_entity="api.gateway.enterprise.com",
            evidence_snippet="14,200 pending customer orders blocked with $8,400/min burn rate."
        )
    ]

    causal_edges = [
        CausalEdge(source="NODE-EXT-CF", target="NODE-ROOT-CB", relationship="EXPOSES_DEFECT", confidence=0.98),
        CausalEdge(source="NODE-ROOT-CB", target="NODE-INT-POOL", relationship="AMPLIFIES_THROUGH_RETRIES", confidence=0.96),
        CausalEdge(source="NODE-INT-POOL", target="NODE-SYM-504", relationship="TRIGGERS_SYSTEM_SATURATION", confidence=0.99)
    ]

    causal_graph = CausalGraph(
        nodes=causal_nodes,
        edges=causal_edges,
        root_cause_node_id="NODE-ROOT-CB",
        root_cause_explanation="While the initial trigger was an external Cloudflare US-East edge latency degradation, the critical system outage was caused by the lack of a circuit breaker and exponential backoff in webhook_dispatcher.py, which converted an external 12% packet loss into a 100% thread pool starvation (thundering herd).",
        mathematical_confidence=0.972,
        counterfactual_proof="Theorem: Had a 3-strike circuit breaker with full jitter backoff been active, blocked worker threads would have peaked at 4/100 instead of 96/100, reducing internal error propagation by 91.6%."
    )

    remediation = RemediationPlan(
        immediate_mitigation="Temporarily enable ingress edge bypass via secondary DNS route (us-west failover) and scale webhook worker replicas from 4 to 12.",
        mitigation_command="kubectl scale deployment checkout-webhook --replicas=12 -n production",
        target_file="webhook_dispatcher.py",
        original_code_snippet=ORIGINAL_BUGGY_CODE,
        patched_code_snippet=PATCHED_CODE,
        unified_git_diff=UNIFIED_DIFF,
        regression_test_code=REGRESSION_TEST_CODE,
        sandbox_result=SandboxTestResult(
            test_suite_name="test_circuit_breaker_trips_and_prevents_thundering_herd",
            tests_run=2,
            tests_passed=2,
            tests_failed=0,
            exit_code=0,
            execution_time_ms=142.6,
            raw_output="tests/test_webhook_dispatcher.py::test_circuit_breaker_trips PASSED [ 50%]\ntests/test_webhook_dispatcher.py::test_fast_fail_prevents_starvation PASSED [100%]\n======================= 2 passed in 0.14s =======================",
            verified_safe=True
        ),
        rollback_procedure="git checkout HEAD~1 webhook_dispatcher.py && kubectl rollout undo deployment/checkout-webhook",
        estimated_downtime_saved_min=45,
        financial_loss_prevented_usd=378000.0
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
