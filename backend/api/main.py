from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import assets as assets_router
from backend.api import campaigns as campaigns_router
from backend.api import generations as generations_router
from backend.api import health as health_router
from backend.api import plans as plans_router
from backend.api import projects as projects_router
from backend.api import prompt_studio as prompt_studio_router
from backend.api import storyboards as storyboards_router
from backend.api import workflows as workflows_router
from backend.core import config
from backend.core.security import PathValidationError
from backend.database.db import init_db
from backend.backends import registry
from backend.jobs.service import get_engine, recover_stale_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_data_dirs()
    init_db()
    recovery = recover_stale_jobs()
    if recovery["requeued"] or recovery["failed"]:
        print(
            f"[orvyn] job recovery: {len(recovery['requeued'])} requeued, {len(recovery['failed'])} failed",
            flush=True,
        )
    registry.ensure_registered()
    from backend.exports.service import cleanup_old_exports

    removed_exports = cleanup_old_exports()
    if removed_exports:
        print(f"[orvyn] export cleanup: {removed_exports} file lama dihapus", flush=True)
    engine = get_engine()
    engine.poll_interval = 2.0
    engine.start_background()
    app.state.engine = engine
    yield
    engine.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Orvyn AI Creative Workspace",
        version=config.APP_VERSION,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5170",
            "http://localhost:5170",
            "http://127.0.0.1:8187",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router.router)
    app.include_router(projects_router.router)
    app.include_router(assets_router.router)
    app.include_router(generations_router.router)
    app.include_router(plans_router.router)
    app.include_router(storyboards_router.router)
    app.include_router(campaigns_router.router)
    app.include_router(workflows_router.router)
    app.include_router(prompt_studio_router.router)

    @app.exception_handler(PathValidationError)
    async def path_error_handler(request, exc: PathValidationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/")
    def root():
        return {
            "name": "Orvyn AI Creative Workspace",
            "status": "running",
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
