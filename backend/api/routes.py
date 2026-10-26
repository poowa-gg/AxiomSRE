"""
AxiomSRE FastAPI Routes
REST Endpoints powering the SRE Mission Control Dashboard
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from backend.config import settings
from backend.api.schemas import (
    IncidentSummaryItem,
    IncidentAnalysisResponse,
    PostMortemReport,
    SandboxTestResult
)
from backend.services.orchestrator import IncidentOrchestrator
from backend.services.postmortem_service import PostMortemGenerator
from backend.services.sandbox_executor import SandboxExecutor

router = APIRouter(prefix="/api", tags=["AxiomSRE"])
orchestrator = IncidentOrchestrator()

@router.get("/status")
async def get_system_status() -> Dict[str, Any]:
    """
    Returns platform health, Nebius Token Factory endpoints, and active NVIDIA models.
    """
    return {
        "status": "ONLINE",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "nebius_token_factory": {
            "base_url": settings.NEBIUS_BASE_URL,
            "connected": orchestrator.nebius_client.is_live,
            "tier1_fast_model": settings.NVIDIA_FAST_MODEL,
            "tier2_reasoning_model": settings.NVIDIA_REASONING_MODEL,
            "code_model": settings.NVIDIA_CODE_MODEL
        },
        "tavily_grounding": {
            "endpoint": settings.TAVILY_BASE_URL,
            "connected": orchestrator.tavily_client.is_live
        },
        "sandbox_runtime": {
            "environment": "Isolated Subprocess (Pytest)",
            "status": "READY"
        }
    }

@router.get("/incidents", response_model=List[IncidentSummaryItem])
async def list_active_incidents():
    """
    List all active production incidents available for autonomous analysis.
    """
    return orchestrator.list_incidents()

@router.get("/incidents/{incident_id}")
async def get_incident_details(incident_id: str) -> Dict[str, Any]:
    """
    Returns raw telemetry logs, metrics, and metadata for a specific incident.
    """
    scenario = orchestrator.scenarios.get(incident_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    data = scenario.get_scenario_data()
    return {
        "id": data["id"],
        "title": data["title"],
        "service": data["service"],
        "severity": data["severity"],
        "logs": [l.model_dump() for l in data["logs"]],
        "signature": data["signature"].model_dump()
    }

@router.post("/incidents/{incident_id}/analyze", response_model=IncidentAnalysisResponse)
async def analyze_incident(incident_id: str):
    """
    Triggers the 4-tier autonomous remediation workflow:
    Nemotron Super -> Tavily AI -> Nemotron Ultra 550B -> Sandbox Engine.
    """
    if incident_id not in orchestrator.scenarios:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return await orchestrator.analyze_incident(incident_id)

@router.post("/incidents/{incident_id}/sandbox-run", response_model=SandboxTestResult)
async def execute_sandbox_test(incident_id: str):
    """
    Runs the sandbox regression test suite on demand, certifying that the patch passes.
    """
    scenario = orchestrator.scenarios.get(incident_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    data = scenario.get_scenario_data()
    rem = data["remediation"]
    return SandboxExecutor.execute_regression_suite(
        target_file=rem.target_file,
        code_content=rem.patched_code_snippet,
        test_content=rem.regression_test_code
    )

@router.post("/incidents/{incident_id}/postmortem", response_model=PostMortemReport)
async def generate_postmortem(incident_id: str):
    """
    Generates the official enterprise Post-Mortem report (Markdown & JSON).
    """
    analysis = await orchestrator.analyze_incident(incident_id)
    return PostMortemGenerator.generate(analysis)
