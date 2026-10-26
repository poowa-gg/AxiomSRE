"""
AxiomSRE - Autonomous Multi-Tier Incident Commander & Zero-Day Auto-Remediator
Main Application Entrypoint
"""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, HTMLResponse
from backend.config import settings
from backend.api.routes import router as api_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Autonomous Multi-Tier Incident Commander & Zero-Day Auto-Remediator powered by NVIDIA Nemotron on Nebius Token Factory and Tavily AI Grounding."
)

# Enable CORS for cross-origin developer setups
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router)

# Mount Frontend Static Assets
# On Vercel, static files are served by @vercel/static directly (routes in vercel.json).
# On local dev, FastAPI serves them via StaticFiles mount.
frontend_dir = Path(__file__).parent / "frontend" / "static"
_is_vercel = os.environ.get("VERCEL") == "1"

if frontend_dir.exists() and not _is_vercel:
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = frontend_dir / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"), status_code=200)
    return HTMLResponse(content="<h1>AxiomSRE</h1><p>Frontend assets not found.</p>", status_code=200)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/healthz")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

if __name__ == "__main__":
    import uvicorn
    print(f"[*] Starting {settings.APP_NAME} on http://localhost:{settings.PORT}")
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=False)
