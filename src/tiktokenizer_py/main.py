"""FastAPI application factory: wires settings, the price store, the routes and the static files."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool

from tiktokenizer_py import __version__, api, prices, tokenizers, web
from tiktokenizer_py.errors import install_error_handlers
from tiktokenizer_py.middleware import BodySizeLimitMiddleware
from tiktokenizer_py.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Load every BPE file and build the chat variants before serving the first request.
    await run_in_threadpool(tokenizers.warm_up)
    yield


def create_app(
    settings: Settings | None = None, price_fetcher: prices.Fetcher | None = None
) -> FastAPI:
    app = FastAPI(
        title="tiktokenizer-py",
        version=__version__,
        description="See how OpenAI tokenizers split text, powered by tiktoken.",
        lifespan=lifespan,
        # web.py serves Swagger UI from the vendored copy; ReDoc would load from a CDN.
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = settings = settings or Settings.from_env()
    app.state.prices = prices.PriceStore(
        settings.data_dir, api.model_ids, price_fetcher or prices.fetch_text
    )
    install_error_handlers(app)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.include_router(web.router)
    app.include_router(api.router)
    app.mount("/static", web.StaticFilesNoCache(directory=web.STATIC_DIR), name="static")
    return app


app = create_app()
