"""The single HTML page, its static files and the health check."""

from __future__ import annotations

from dataclasses import asdict
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

from tiktokenizer_py import catalogue, chat, prices
from tiktokenizer_py.api import models_response, price_store, prices_response, settings_of
from tiktokenizer_py.examples import EXAMPLES, INTRO_EXAMPLE_ID
from tiktokenizer_py.glossary import GLOSSARY
from tiktokenizer_py.schemas import MAX_MESSAGES
from tiktokenizer_py.settings import Settings

PACKAGE_DIR = Path(__file__).parent
STATIC_DIR = PACKAGE_DIR / "static"
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
# Swagger UI is vendored like Alpine.js, so the API docs work offline.
SWAGGER_UI = "/static/vendor/swagger-ui-dist-5.34.0"

router = APIRouter()


class StaticFilesNoCache(StaticFiles):
    """Static files that browsers revalidate on every load (a cheap 304 when unchanged).

    The page loads JavaScript modules by plain URLs, so a long cache would serve stale code
    after an update.
    """

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


def page_data(settings: Settings, store: prices.PriceStore) -> dict[str, object]:
    """Everything the UI needs at load time, embedded in the page as JSON."""
    return {
        "prices": prices_response(store).model_dump(mode="json"),
        "catalogue": models_response().model_dump(mode="json"),
        "examples": [asdict(e) for e in EXAMPLES],
        "intro_example": INTRO_EXAMPLE_ID,
        "glossary": [asdict(g) for g in GLOSSARY],
        "roles": list(chat.ROLES),
        "limits": {"max_text_chars": settings.max_text_chars, "max_messages": MAX_MESSAGES},
    }


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "tiktoken_version": package_version("tiktoken"),
            "default_model": catalogue.DEFAULT_MODEL,
            "page_data": page_data(settings_of(request), price_store(request)),
        },
    )


@router.get("/docs", response_class=HTMLResponse, include_in_schema=False)
def api_docs(request: Request) -> HTMLResponse:
    return get_swagger_ui_html(
        openapi_url=request.app.openapi_url,
        title=f"{request.app.title} - Swagger UI",
        swagger_js_url=f"{SWAGGER_UI}/swagger-ui-bundle.js",
        swagger_css_url=f"{SWAGGER_UI}/swagger-ui.css",
        swagger_favicon_url="/static/favicon.svg",
    )


@router.get("/healthz", tags=["meta"])
def healthz() -> dict[str, str]:
    return {"status": "ok"}
