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

# Detect Vercel serverless environment — no filesystem StaticFiles mount available
_is_vercel = os.environ.get("VERCEL") == "1"
_root = Path(__file__).parent
_frontend_dir = _root / "frontend" / "static"

# On local dev: mount static files normally via FastAPI
if not _is_vercel and _frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_frontend_dir)), name="static")


def _build_inline_html() -> str:
    """Read CSS + JS and embed them directly into the HTML for Vercel compatibility."""
    html_path = _frontend_dir / "index.html"
    css_path = _frontend_dir / "css" / "style.css"
    js_path = _frontend_dir / "js" / "app.js"

    html = html_path.read_text(encoding="utf-8") if html_path.exists() else "<h1>AxiomSRE</h1>"
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    js = js_path.read_text(encoding="utf-8") if js_path.exists() else ""

    # Replace external /static/... references with inline <style> and <script>
    html = html.replace(
        '<link rel="stylesheet" href="/static/css/style.css">',
        f"<style>\n{css}\n</style>"
    )
    html = html.replace(
        '<script src="/static/js/app.js"></script>',
        f"<script>\n{js}\n</script>"
    )
    return html


# Pre-build the HTML once at startup (fast subsequent requests)
_INLINE_HTML: str = _build_inline_html() if _frontend_dir.exists() else "<h1>AxiomSRE API</h1>"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index():
    return HTMLResponse(content=_INLINE_HTML, status_code=200)


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
