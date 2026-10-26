import asyncio
import pytest
from backend.services.nebius_client import NebiusClient
from backend.api.schemas import IncidentSignature, IncidentSeverity

def test_nebius_client_signature_extraction():
    async def _runner():
        client = NebiusClient()
        logs = [
            {"timestamp": "2026-10-26T01:00:00Z", "level": "ERROR", "message": "504 Gateway Timeout"}
        ]
        result = await client.analyze_telemetry_signature("test-service", logs)
        assert "model_used" in result
        assert result["status"] == "COMPLETED"

    asyncio.run(_runner())

def test_nebius_client_causal_dag():
    async def _runner():
        client = NebiusClient()
        sig = IncidentSignature(
            incident_id="TEST-INC",
            title="Test Incident",
            service="test-service",
            severity=IncidentSeverity.P1_HIGH,
            primary_error="504 Timeout",
            error_frequency_per_sec=10.0,
            affected_endpoints=["/api/test"],
            suspected_domains=["cloudflarestatus.com"],
            tavily_search_queries=["test query"],
            summary="Test summary"
        )
        result = await client.reason_causal_dag(sig, [], [])
        assert "model_used" in result
        assert result["status"] == "COMPLETED"

    asyncio.run(_runner())
