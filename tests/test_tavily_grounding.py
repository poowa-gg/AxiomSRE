import asyncio
import pytest
from backend.services.tavily_client import TavilyGroundingClient

def test_tavily_grounding_initialization():
    async def _runner():
        client = TavilyGroundingClient()
        # In test environment, client safely handles queries without crashing
        results = await client.search("site:cloudflarestatus.com test query")
        assert isinstance(results, list)

    asyncio.run(_runner())
