import json
from pathlib import Path
from typing import Any, Self

import pytest
from fastapi.testclient import TestClient

from tiktokenizer_py import catalogue, prices
from tiktokenizer_py.api import _wait_text
from tiktokenizer_py.main import create_app
from tiktokenizer_py.settings import Settings

from .helpers import offline_fetcher

# A small page in the layout of OpenAI's pricing.md (our own text, not a copy of the page).
LONG = (
    "| Model | Short context input | Short context output | Short context cached input | "
    "Short context 30m write | Short context 12h write | Long context input | Long context output "
    "| Long context cached input | Long context 30m write | Long context 12h write |"
)
SEP11 = "| " + " | ".join(["---"] * 11) + " |"
BIG_ROW = "| big-model | $4.00 | $20.00 | $0.40 | $5.00 | $10.00 | $8.00 | $30.00 | $0.80 | " + (
    "$10.00 | $20.00 |"
)
MID_ROW = "| mid-model (<272K context length) | $2.50 | $15.00 | $0.25 | - | - | $5.00 | " + (
    "$22.50 | $0.50 | - | - |"
)
PRICING = f"""# Pricing

Flagship models

Standard

### Standard pricing data

{LONG}
{SEP11}
{BIG_ROW}
{MID_ROW}

| Model | Input | Output | Cached input |
| --- | --- | --- | --- |
| small-model | $0.15 | $0.60 | $0.075 |
| old-model-0613 | $30.00 | $60.00 | - |
| small-model | $99.00 | $99.00 | $99.00 |

Batch

### Batch pricing data

#### Batch

| Model | Input | Output | Cached input |
| --- | --- | --- | --- |
| small-model | $0.075 | $0.30 | - |

#### Flex

| Model | Input | Output | Cached input |
| --- | --- | --- | --- |
| big-model | $2.00 | $10.00 | $0.20 |

Fast

### Fast pricing data

| Model | Input | Output | Cached input |
| --- | --- | --- | --- |
| big-model | $8.00 | $40.00 | $0.80 |

Short context: ≤272K input tokens. Long context: >272K input tokens.

Image generation models

### Grouped Pricing Table data

| Model | Modality | Input | Output | Cached input |
| --- | --- | --- | --- | --- |
| image-model | Image | Free | weird | ? |

Specialized models

Standard

### Grouped Pricing Table data

| Category | Model | Input | Output | Cached input |
| --- | --- | --- | --- | --- |
| Embedding | embed-model | $0.02 | - | - |
| Moderation | moderation-model | Free | - | - |
"""

MODEL_PAGE = """# Big model

## Model details

- Default snapshot: `big-model`
- 1,050,000 context window
- Maximum input tokens: 922,000
- 128,000 max output tokens
- It has a 1M token context window, mentioned in prose.
"""

WANTED = ["big-model", "mid-model", "small-model", "old-model-0613", "embed-model"]


def test_parse_pricing_reads_every_table_layout() -> None:
    parsed = prices.parse_pricing(PRICING, WANTED)
    assert parsed.long_context_threshold == 272_000
    big = parsed.models["big-model"]
    # Input, cached input, output, then the 30-minute and 12-hour cache-write prices.
    assert big["standard"].short == prices.Price(4.0, 0.4, 20.0, 5.0, 10.0)
    assert big["standard"].long == prices.Price(8.0, 0.8, 30.0, 10.0, 20.0)
    assert big["flex"].short == prices.Price(2.0, 0.2, 10.0)
    assert big["fast"].short == prices.Price(8.0, 0.8, 40.0)
    assert parsed.models["mid-model"]["standard"].long == prices.Price(5.0, 0.5, 22.5)
    # The first row wins; "-" means no price.
    assert parsed.models["small-model"]["standard"].short == prices.Price(0.15, 0.075, 0.6)
    assert parsed.models["small-model"]["batch"].short == prices.Price(0.075, None, 0.3)
    assert parsed.models["old-model-0613"]["standard"].short.cached_input is None
    assert parsed.models["embed-model"]["standard"].short == prices.Price(0.02, None, None)


def test_parse_pricing_skips_rows_it_does_not_need() -> None:
    # "Free", "weird" and "?" cells belong to models nobody asked for, so they are not errors.
    parsed = prices.parse_pricing(PRICING, ["big-model"])
    assert set(parsed.models) == {"big-model"}


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (("Short context: ≤272K", "Short context: up to 272K"), "threshold"),
        (("### Fast pricing data", "### Speedy pricing data"), "'fast' price section"),
        (("Short context cached input", "Short cached input"), "no table with the columns"),
        (("| Category | Model |", "| Kind | Model |"), "no table with the columns"),
        (("| small-model | $0.15 |", "| small-model | 0.15 USD |"), "unexpected price"),
        (("| big-model | $4.00 |", "| big-model | $40,000.00 |"), "outside the expected range"),
    ],
)
def test_parse_pricing_reports_layout_changes(change: tuple[str, str], problem: str) -> None:
    with pytest.raises(prices.PricingLayoutError) as err:
        prices.parse_pricing(PRICING.replace(*change, 1), WANTED)
    assert any(problem in p for p in err.value.problems)


def test_parse_limits() -> None:
    assert prices.parse_limits(MODEL_PAGE) == {
        "context_window": 1_050_000,
        "max_input": 922_000,
        "max_output": 128_000,
    }
    assert prices.parse_limits("- 16,384 max output tokens") == {
        "context_window": None,
        "max_input": None,
        "max_output": 16_384,
    }


OVERRIDES: dict[str, Any] = {
    "models": {
        "old-model": {"price_from": "old-model-0613", "note": "Priced as old-model-0613."},
        "open-model": {"no_price": "Open-weight model."},
        "embed-model": {"limits": {"max_input": 8192}},
    },
    "retired": ["gone-model"],
}
IDS = ["big-model", "small-model", "old-model", "open-model", "embed-model", "gone-model"]


def pages(**extra: str | None) -> dict[str, str | None]:
    base: dict[str, str | None] = {m: MODEL_PAGE for m in IDS if m != "gone-model"}
    base["embed-model"] = "# Embeddings\n"
    base.update(extra)
    return base


def test_build_snapshot() -> None:
    snap = prices.build_snapshot(PRICING, pages(), IDS, OVERRIDES, "2026-10-22T10:00:00Z")
    models = snap["models"]
    assert snap["long_context_threshold"] == 272_000
    assert snap["fetched_at"] == "2026-10-22T10:00:00Z"
    assert models["big-model"]["prices"]["standard"]["long"]["input"] == 8.0
    assert set(models["big-model"]["prices"]) == {"standard", "flex", "fast"}
    assert models["old-model"]["prices"]["standard"]["input"] == 30.0
    assert models["old-model"]["price_note"] == "Priced as old-model-0613."
    assert models["open-model"]["prices"] == {}
    assert models["open-model"]["limits"]["context_window"] == 1_050_000
    assert models["embed-model"]["limits"] == {
        "context_window": None,
        "max_input": 8192,
        "max_output": None,
    }
    assert models["gone-model"] == {
        "prices": {},
        "price_note": "Retired: no longer listed on OpenAI's pricing page.",
        "limits": None,
    }
    json.dumps(snap)  # the snapshot is plain JSON


@pytest.mark.parametrize(
    ("page_changes", "pricing", "problem"),
    [
        ({"big-model": None}, PRICING, "model page for big-model could not be found"),
        ({"small-model": "# no details\n"}, PRICING, "lists no context window"),
        (
            {},
            PRICING.replace("| small-model | $0.15 | $0.60 | $0.075 |\n", "").replace(
                "| small-model | $99.00 | $99.00 | $99.00 |\n", ""
            ),
            "no Standard price for small-model",
        ),
    ],
)
def test_build_snapshot_reports_problems(
    page_changes: dict[str, str | None], pricing: str, problem: str
) -> None:
    with pytest.raises(prices.PricingLayoutError) as err:
        prices.build_snapshot(pricing, pages(**page_changes), IDS, OVERRIDES, "now")
    assert any(problem in p for p in err.value.problems)


def test_fetch_text_only_allows_openai_docs() -> None:
    with pytest.raises(prices.PricingFetchError):
        prices.fetch_text("https://example.com/pricing.md")


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.headers = {"content-type": "text/markdown; charset=utf-8"}
        self.body = body

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


def test_fetch_text_rejects_a_page_that_is_not_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        prices.urllib.request, "urlopen", lambda *a, **k: _FakeResponse(b"price \xff\xfe")
    )
    with pytest.raises(prices.PricingFetchError, match="not valid UTF-8"):
        prices.fetch_text(prices.PRICING_URL)


def test_fetch_snapshot_uses_the_fetcher() -> None:
    requested: list[str] = []

    def fetcher(url: str) -> str | None:
        requested.append(url)
        return PRICING if url == prices.PRICING_URL else MODEL_PAGE

    snap = prices.fetch_snapshot(["big-model", "small-model"], fetcher)
    assert prices.PRICING_URL in requested
    assert prices.MODEL_URL.format(model="big-model") in requested
    assert snap["models"]["small-model"]["prices"]["batch"]["input"] == 0.075


def test_changes_lists_differences() -> None:
    old = prices.build_snapshot(PRICING, pages(), IDS, OVERRIDES, "a")
    new = prices.build_snapshot(
        PRICING.replace("| small-model | $0.15", "| small-model | $0.20"),
        pages(),
        IDS,
        OVERRIDES,
        "b",
    )
    diff = prices.changes(old, new)
    assert len(diff) == 1
    assert diff[0].startswith("small-model standard: $0.15 in")
    assert "$0.2 in" in diff[0]


# --- the overrides and the bundled snapshot -------------------------------------------------


MODEL_IDS = [e.id for e in catalogue.entries() if e.kind == "model"]


def test_overrides_only_name_catalogue_models() -> None:
    overrides = prices.load_overrides()
    assert set(overrides["models"]) <= set(MODEL_IDS)
    assert set(overrides["retired"]) <= set(MODEL_IDS)


def test_bundled_snapshot_covers_every_model() -> None:
    snap = prices.load_bundled()
    assert snap["schema"] == prices.SCHEMA_VERSION
    assert snap["long_context_threshold"] == 272_000
    assert set(snap["models"]) == set(MODEL_IDS)
    for model, entry in snap["models"].items():
        # Every model has prices or a reason why not, never a silent gap.
        assert entry["prices"] or entry["price_note"], model
        for mode, row in entry["prices"].items():
            assert mode in prices.MODES
            assert row["input"] is not None and row["input"] >= 0, model


def test_bundled_snapshot_values() -> None:
    models = prices.load_bundled()["models"]
    assert models["gpt-5.6-sol"]["limits"]["max_input"] == 922_000
    assert models["gpt-5.6-sol"]["prices"]["standard"]["long"] is not None
    assert models["gpt-4o"]["limits"]["context_window"] == 128_000
    assert models["gpt-oss-120b"]["prices"] == {}
    assert models["text-embedding-3-small"]["limits"]["max_input"] == 8192


# --- the store ----------------------------------------------------------------------------


def newer_snapshot() -> dict[str, Any]:
    snap = prices.load_bundled()
    snap = json.loads(json.dumps(snap))
    snap["fetched_at"] = "2999-01-01T00:00:00Z"
    snap["models"]["gpt-4o"]["prices"]["standard"]["input"] = 1.0
    return snap


def test_store_prefers_a_newer_saved_snapshot(tmp_path: Path) -> None:
    store = prices.PriceStore(None, lambda: MODEL_IDS)
    assert store.origin == "bundled"
    prices.save(newer_snapshot(), tmp_path / prices.SNAPSHOT_FILE)
    store = prices.PriceStore(tmp_path, lambda: MODEL_IDS)
    assert store.origin == "fetched"
    assert store.snapshot["models"]["gpt-4o"]["prices"]["standard"]["input"] == 1.0


def test_store_ignores_older_or_broken_saved_files(tmp_path: Path) -> None:
    old = prices.load_bundled()
    old["fetched_at"] = "2000-01-01T00:00:00Z"
    prices.save(old, tmp_path / prices.SNAPSHOT_FILE)
    assert prices.PriceStore(tmp_path, lambda: MODEL_IDS).origin == "bundled"
    (tmp_path / prices.SNAPSHOT_FILE).write_text("{not json")
    assert prices.PriceStore(tmp_path, lambda: MODEL_IDS).origin == "bundled"


def test_store_refresh_saves_and_rate_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(prices, "fetch_snapshot", lambda ids, fetcher: newer_snapshot())
    now = [1000.0]
    store = prices.PriceStore(tmp_path, lambda: MODEL_IDS, clock=lambda: now[0])
    result = store.refresh()
    assert result.saved
    assert any(line.startswith("gpt-4o standard") for line in result.changes)
    assert prices.load_saved(tmp_path) == newer_snapshot()
    with pytest.raises(prices.RefreshTooSoonError):
        store.refresh()
    now[0] += prices.REFRESH_INTERVAL_S
    store.refresh()


def test_store_allows_a_quick_retry_after_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def flaky(ids: object, fetcher: object) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise prices.PricingFetchError("offline")
        return newer_snapshot()

    monkeypatch.setattr(prices, "fetch_snapshot", flaky)
    now = [0.0]
    store = prices.PriceStore(None, lambda: MODEL_IDS, clock=lambda: now[0])
    with pytest.raises(prices.PricingFetchError):
        store.refresh()
    with pytest.raises(prices.RefreshTooSoonError) as err:
        store.refresh()
    assert err.value.wait_s <= prices.RETRY_AFTER_FAILURE_S + 1
    now[0] += prices.RETRY_AFTER_FAILURE_S
    assert store.refresh().snapshot["fetched_at"].startswith("2999")


@pytest.mark.parametrize(
    "error", [prices.PricingLayoutError(["layout changed"]), prices.PricingFetchError("offline")]
)
def test_store_keeps_prices_when_refresh_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def failing(ids: object, fetcher: object) -> dict[str, Any]:
        raise error

    monkeypatch.setattr(prices, "fetch_snapshot", failing)
    store = prices.PriceStore(tmp_path, lambda: MODEL_IDS)
    before = store.snapshot
    with pytest.raises(type(error)):
        store.refresh()
    assert store.snapshot is before
    assert not (tmp_path / prices.SNAPSHOT_FILE).exists()


def test_store_refresh_without_writable_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(prices, "fetch_snapshot", lambda ids, fetcher: newer_snapshot())
    blocked = tmp_path / "file"
    blocked.write_text("not a directory")
    result = prices.PriceStore(blocked, lambda: MODEL_IDS).refresh()
    assert not result.saved
    assert result.snapshot["fetched_at"].startswith("2999")


# --- API ------------------------------------------------------------------------------------


def test_api_prices(client: TestClient) -> None:
    data = client.get("/api/prices").json()
    assert data["origin"] == "bundled"
    assert data["refresh_interval_s"] == prices.REFRESH_INTERVAL_S
    assert data["models"]["gpt-5.6-sol"]["prices"]["standard"]["output"] > 0
    assert data["sources"]["pricing"] == prices.PRICING_URL


def test_api_refresh_failure_keeps_prices(client: TestClient) -> None:
    before = client.get("/api/prices").json()
    res = client.post("/api/prices/refresh")
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "prices_fetch_failed"
    assert client.get("/api/prices").json() == before


def test_api_refresh_success_and_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prices, "fetch_snapshot", lambda ids, fetcher: newer_snapshot())
    app = create_app(Settings(data_dir=tmp_path), price_fetcher=offline_fetcher)
    with TestClient(app) as c:
        res = c.post("/api/prices/refresh")
        assert res.status_code == 200
        body = res.json()
        assert body["saved"] is True
        assert body["prices"]["origin"] == "fetched"
        assert body["prices"]["models"]["gpt-4o"]["prices"]["standard"]["input"] == 1.0
        assert any("gpt-4o standard" in line for line in body["changes"])
        again = c.post("/api/prices/refresh")
        assert again.status_code == 429
        assert again.json()["error"]["code"] == "refresh_too_soon"
        assert again.json()["error"]["message"].endswith("Try again in 10 minutes.")
        retry_after = int(again.headers["retry-after"])
        assert retry_after == again.json()["error"]["details"]["retry_after_s"]
        assert 0 < retry_after <= prices.REFRESH_INTERVAL_S


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(1, "1 second"), (45, "45 seconds"), (60, "1 minute"), (61, "2 minutes"), (600, "10 minutes")],
)
def test_wait_text_rounds_up(seconds: int, text: str) -> None:
    assert _wait_text(seconds) == text


def test_api_refresh_layout_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(ids: object, fetcher: object) -> dict[str, Any]:
        raise prices.PricingLayoutError(["the 'fast' price section is missing"])

    monkeypatch.setattr(prices, "fetch_snapshot", failing)
    with TestClient(create_app(Settings(data_dir=tmp_path), price_fetcher=offline_fetcher)) as c:
        res = c.post("/api/prices/refresh")
    assert res.status_code == 502
    error = res.json()["error"]
    assert error["code"] == "prices_layout_changed"
    assert error["details"]["problems"] == ["the 'fast' price section is missing"]


def test_api_refresh_unexpected_error_keeps_the_error_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(ids: object, fetcher: object) -> dict[str, Any]:
        raise RuntimeError("bug")

    monkeypatch.setattr(prices, "fetch_snapshot", broken)
    app = create_app(Settings(), price_fetcher=offline_fetcher)
    with TestClient(app, raise_server_exceptions=False) as c:
        res = c.post("/api/prices/refresh")
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "internal_server_error"


def test_settings_reads_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    assert Settings.from_env().data_dir == tmp_path
