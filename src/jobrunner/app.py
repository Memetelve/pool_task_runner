"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .api.router import api_router
from .config import settings
from .database import init_db


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        summary="JobRunner API",
        description="REST API for scheduling and tracking regression job batches.",
    )
    app.include_router(api_router, prefix=settings.api_prefix)

    templates = Jinja2Templates(
        directory=str(Path(__file__).resolve().parent / "templates")
    )

    @app.on_event("startup")
    async def apply_schema_upgrades() -> None:
        """Ensure DB schema (including new columns) exists before serving traffic."""
        await init_db()

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(
        request: Request,
    ) -> HTMLResponse:  # pragma: no cover - HTML response
        return templates.TemplateResponse(
            "dashboard.html", {"request": request, "app_name": settings.app_name}
        )

    @app.get("/batches/{batch_id}", response_class=HTMLResponse)
    async def batch_detail(
        request: Request, batch_id: str
    ) -> HTMLResponse:  # pragma: no cover - HTML response
        return templates.TemplateResponse(
            "batch_detail.html",
            {"request": request, "app_name": settings.app_name, "batch_id": batch_id},
        )

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    async def job_detail(
        request: Request, job_id: str
    ) -> HTMLResponse:  # pragma: no cover - HTML response
        return templates.TemplateResponse(
            "job_detail.html",
            {"request": request, "app_name": settings.app_name, "job_id": job_id},
        )

    @app.get("/admin/limits", response_class=HTMLResponse)
    async def admin_limits(
        request: Request,
    ) -> HTMLResponse:  # pragma: no cover - HTML response
        return templates.TemplateResponse(
            "admin_limits.html",
            {"request": request, "app_name": settings.app_name},
        )

    return app


app = create_app()
