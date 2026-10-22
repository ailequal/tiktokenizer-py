from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tiktokenizer_py.main import create_app
from tiktokenizer_py.settings import Settings

from .helpers import offline_fetcher


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    # The context manager runs the lifespan, which warms every encoding once.
    settings = Settings(max_text_chars=1_000, max_body_bytes=10_000)
    with TestClient(create_app(settings, price_fetcher=offline_fetcher)) as c:
        yield c
