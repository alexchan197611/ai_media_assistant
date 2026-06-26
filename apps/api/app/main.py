from contextlib import asynccontextmanager
import sys
from pathlib import Path

MEDIA_CORE_SRC = Path(__file__).resolve().parents[3] / "packages" / "media_core" / "src"
if str(MEDIA_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(MEDIA_CORE_SRC))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.api.routes.assets import router as assets_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.media import router as media_router
from app.api.routes.projects import router as projects_router
from app.config import settings
from app.db.base import Base
from app.db.session import engine

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield

app = FastAPI(title="AI Media Assistant API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(assets_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(media_router, prefix="/api")
app.include_router(projects_router, prefix="/api")

WEB_DIST = Path(__file__).resolve().parents[3] / "apps" / "web" / "dist"
if (WEB_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="web-assets")


@app.get("/{path:path}", include_in_schema=False)
def serve_web_app(path: str = ""):
    index = WEB_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return HTMLResponse(
        "<h1>AI Media Assistant API is running</h1>"
        "<p>Run <code>npm run build</code> to serve the Web UI from this address, "
        "or use <code>npm run dev</code> for the Vite development server.</p>"
    )
