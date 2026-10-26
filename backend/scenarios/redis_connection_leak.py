"""
Scenario 3: Concurrency Deadlock & Socket Leak in Async Redis Connection Pool
Demonstrates:
- Async concurrency and resource exhaustion analysis via NVIDIA Nemotron
- Live Security & CVE Advisory Triangulation via Tavily Search
- Deadlock proof via Nemotron-3 Ultra (550B)
- Safe async context manager patch and concurrency sandbox validation
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

SCENARIO_ID = "INC-7109-REDIS-LEAK"
TITLE = "Async Connection Pool Saturation & Event Loop Freezes"
SERVICE = "cache-session-manager"
SEVERITY = IncidentSeverity.P0_CRITICAL
ERROR_RATE_PCT = 58.2
P99_LATENCY_MS = 30000.0
BURN_RATE_USD = 11200.0  # $11,200 per minute

SAMPLE_LOGS: List[TelemetryLog] = [
    TelemetryLog(
        timestamp="2026-10-26T01:22:04.101Z",
        service="cache-session-manager",
        level="ERROR",
        message="asyncio.exceptions.TimeoutError: Connection pool limit (max_connections=50) exhausted while acquiring connection",
        latency_ms=5004.2,
        status_code=500,
        trace_id="tr-redis-9912",
        stack_trace="TimeoutError in redis_pool.py:38 in acquire_connection"
    ),
    TelemetryLog(
        timestamp="2026-10-26T01:22:05.412Z",
        service="cache-session-manager",
        level="FATAL",
        message="OS file descriptor limit approaching: 1,012 open TCP sockets in CLOSE_WAIT state on 127.0.0.1:6379",
        latency_ms=None,
        status_code=None,
        trace_id="tr-redis-sys",
        stack_trace="OSError: [Errno 24] Too many open files in connection.py:192"
    ),
    TelemetryLog(
        timestamp="2026-10-26T01:22:06.880Z",
        service="cache-session-manager",
        level="ERROR",
        message="Event loop lag spike: 1,450ms lag detected on main asyncio thread",
        latency_ms=1450.0,
        status_code=503,
        trace_id="tr-redis-lag",
        stack_trace=None
    )
]

ORIGINAL_BUGGY_CODE = '''import asyncio

class AsyncRedisPoolManager:
    def __init__(self, max_connections: int = 50):
        self.max_connections = max_connections
        self.active_connections = 0
        self.lock = asyncio.Lock()

    async def execute_cache_command(self, key: str, value: str) -> bool:
        # BUG: Missing try/finally or async context manager.
        # If an unhandled exception or cancelled task occurs, connection is never decremented!
        async with self.lock:
            if self.active_connections >= self.max_connections:
                raise TimeoutError("Connection pool exhausted")
            self.active_connections += 1

        # Simulate network I/O that may raise an exception
        if "malformed" in key:
            raise ValueError("Malformed key format")

        # Connection release is skipped on exception
        async with self.lock:
            self.active_connections -= 1
        return True
'''

PATCHED_CODE = '''import asyncio
from contextlib import asynccontextmanager

class AsyncRedisPoolManager:
    def __init__(self, max_connections: int = 50):
        self.max_connections = max_connections
        self.active_connections = 0
        self.lock = asyncio.Lock()

    @asynccontextmanager
    async def connection_lease(self):
        # Guaranteed acquisition and release regardless of exceptions or task cancellation
        async with self.lock:
            if self.active_connections >= self.max_connections:
                raise TimeoutError("Connection pool exhausted")
            self.active_connections += 1
        try:
            yield
        finally:
            async with self.lock:
                self.active_connections -= 1

    async def execute_cache_command(self, key: str, value: str) -> bool:
        async with self.connection_lease():
            if "malformed" in key:
                raise ValueError("Malformed key format")
            return True
'''

REGRESSION_TEST_CODE = '''import asyncio
import pytest

def test_redis_pool_leak_prevention_on_exceptions():
    from redis_pool import AsyncRedisPoolManager

    async def _async_runner():
        manager = AsyncRedisPoolManager(max_connections=5)

        # Trigger 10 commands that throw unhandled exceptions
        for i in range(10):
            try:
                await manager.execute_cache_command("malformed_key", "data")
            except ValueError:
                pass

        # Invariants check: active_connections must return strictly to 0
        assert manager.active_connections == 0, f"Leaked connections detected: {manager.active_connections}"

        # Verify new valid requests succeed without pool exhaustion
        success = await manager.execute_cache_command("valid_key", "data")
        assert success is True
        assert manager.active_connections == 0

    asyncio.run(_async_runner())
'''

UNIFIED_DIFF = '''--- a/redis_pool.py
+++ b/redis_pool.py
@@ -1,23 +1,28 @@
 import asyncio
+from contextlib import asynccontextmanager

 class AsyncRedisPoolManager:
     def __init__(self, max_connections: int = 50):
         self.max_connections = max_connections
         self.active_connections = 0
         self.lock = asyncio.Lock()

+    @asynccontextmanager
+    async def connection_lease(self):
+        async with self.lock:
+            if self.active_connections >= self.max_connections:
+                raise TimeoutError("Connection pool exhausted")
+            self.active_connections += 1
+        try:
+            yield
+        finally:
+            async with self.lock:
+                self.active_connections -= 1
+
     async def execute_cache_command(self, key: str, value: str) -> bool:
-        async with self.lock:
-            if self.active_connections >= self.max_connections:
-                raise TimeoutError("Connection pool exhausted")
-            self.active_connections += 1
-
-        if "malformed" in key:
-            raise ValueError("Malformed key format")
-
-        async with self.lock:
-            self.active_connections -= 1
-        return True
+        async with self.connection_lease():
+            if "malformed" in key:
+                raise ValueError("Malformed key format")
+            return True
'''

def get_scenario_data() -> Dict[str, Any]:
    signature = IncidentSignature(
        incident_id=SCENARIO_ID,
        title=TITLE,
        service=SERVICE,
        severity=SEVERITY,
        primary_error="TimeoutError: Connection pool limit exhausted & OSError: Too many open files",
        error_frequency_per_sec=74.1,
        affected_endpoints=["/v1/session/store", "/v1/cache/token"],
        suspected_domains=["github.com/redis/redis-py", "redis.io"],
        tavily_search_queries=[
            "site:github.com/redis/redis-py 'TimeoutError' connection pool leak async context manager",
            "redis asyncio connection leak CLOSE_WAIT file descriptor saturation",
            "cve redis connection pool resource exhaustion asyncio"
        ],
        summary="Async Redis connection pool leaks socket handles on unhandled exceptions, accumulating over 1,000 dangling TCP connections and freezing the main event loop."
    )

    tavily_evidences = [
        TavilyEvidence(
            title="Redis-Py Issue #2341: Asyncio connection pool leak when coroutine raises or is cancelled",
            url="https://github.com/redis/redis-py/issues/2341",
            source="github.com/redis/redis-py",
            snippet="When executing commands without an explicit async context manager, any ValueError, Timeout, or CancelledError prevents connection release back to the pool. Over time this causes Errno 24 (Too many open files).",
            relevance_score=0.98,
            publication_time="GitHub Issues",
            is_authoritative=True,
            incident_correlation="Exact root cause: Early return / unhandled exception in execute_cache_command leaked connections."
        ),
        TavilyEvidence(
            title="CVE-2024-Resource-Exhaustion in High-Throughput Async Connection Pools",
            url="https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2024-ResourceLeak",
            source="cve.mitre.org",
            snippet="Improper socket release in asynchronous network multiplexers leads to memory growth and eventual complete denial of service for worker processes.",
            relevance_score=0.92,
            publication_time="NVD Advisory",
            is_authoritative=True,
            incident_correlation="Corroborates the 1,012 open TCP sockets in CLOSE_WAIT observed in system telemetry."
        )
    ]

    causal_nodes = [
        CausalNode(
            id="NODE-ROOT-LEAK",
            label="Missing Async Context Manager in Connection Lifecycle",
            type=NodeType.ROOT_CAUSE,
            confidence=0.99,
            service_or_entity="cache-session-manager",
            evidence_snippet="execute_cache_command increments active_connections but skips decrement when payload validation raises ValueError."
        ),
        CausalNode(
            id="NODE-INT-FD",
            label="Socket Descriptor Exhaustion (1,012 CLOSE_WAIT Sockets)",
            type=NodeType.INTERMEDIATE_CASCADE,
            confidence=0.97,
            service_or_entity="Operating System / Kernel",
            evidence_snippet="OSError: [Errno 24] Too many open files reported during socket alloc."
        ),
        CausalNode(
            id="NODE-SYM-DEADLOCK",
            label="Event Loop Latency Freezes & 58.2% Session Store Failure Rate",
            type=NodeType.SURFACE_SYMPTOM,
            confidence=1.00,
            service_or_entity="cache-session-manager",
            evidence_snippet="30,000ms timeouts on /v1/session/store with $11,200/min burn rate."
        )
    ]

    causal_edges = [
        CausalEdge(source="NODE-ROOT-LEAK", target="NODE-INT-FD", relationship="ACCUMULATES_ORPHANED_SOCKETS", confidence=0.98),
        CausalEdge(source="NODE-INT-FD", target="NODE-SYM-DEADLOCK", relationship="BLOCKS_EVENT_LOOP", confidence=0.99)
    ]

    causal_graph = CausalGraph(
        nodes=causal_nodes,
        edges=causal_edges,
        root_cause_node_id="NODE-ROOT-LEAK",
        root_cause_explanation="In execute_cache_command, connection acquisition was not guarded by a resilient `finally:` block or async context manager. When malformed payloads raised ValueError, the connection was orphaned forever, rapidly saturating the 50-connection ceiling and exhausting operating system file descriptors.",
        mathematical_confidence=0.991,
        counterfactual_proof="Theorem: Implementing an @asynccontextmanager lease with guaranteed finally block ensures active_connections decreases monotonically to 0 regardless of exception types."
    )

    remediation = RemediationPlan(
        immediate_mitigation="Restart worker processes to flush leaked file descriptors and increase pool ceiling temporarily.",
        mitigation_command="systemctl restart cache-session-worker && ulimit -n 65535",
        target_file="redis_pool.py",
        original_code_snippet=ORIGINAL_BUGGY_CODE,
        patched_code_snippet=PATCHED_CODE,
        unified_git_diff=UNIFIED_DIFF,
        regression_test_code=REGRESSION_TEST_CODE,
        sandbox_result=SandboxTestResult(
            test_suite_name="test_redis_pool_leak_prevention_on_exceptions",
            tests_run=2,
            tests_passed=2,
            tests_failed=0,
            exit_code=0,
            execution_time_ms=115.3,
            raw_output="tests/test_redis_pool.py::test_zero_leaks_on_exceptions PASSED [ 50%]\ntests/test_redis_pool.py::test_concurrency_stress_ceiling PASSED [100%]\n======================= 2 passed in 0.12s =======================",
            verified_safe=True
        ),
        rollback_procedure="git checkout HEAD~1 redis_pool.py",
        estimated_downtime_saved_min=60,
        financial_loss_prevented_usd=672000.0
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
