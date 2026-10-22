"""Reference prices and context limits, read from OpenAI's official documentation.

OpenAI publishes every documentation page as Markdown by appending ``.md`` to its URL:

- ``pricing.md`` has the price tables for every mode (Standard, Batch, Flex, Fast, Ultrafast),
  including the prices for long requests (more than 272K input tokens).
- ``models/<id>.md`` lists a model's context window, maximum input and maximum output.

``build_snapshot`` turns those pages into a small JSON snapshot for the models in the catalogue.
Every expectation about the page layout is checked; if anything does not match, it raises
``PricingLayoutError`` with the list of problems and no snapshot is produced, so the previous
one stays in use. A hand-kept overrides file covers what the pages do not: aliases priced under
a dated snapshot name, models without a reference price, and retired models.

The snapshot bundled in the package is used by default. ``PriceStore.refresh`` fetches fresh
pages at runtime, checks them the same way and saves the result in the data directory.
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, Final

PRICING_URL: Final = "https://developers.openai.com/api/docs/pricing.md"
MODEL_URL: Final = "https://developers.openai.com/api/docs/models/{model}.md"
PRICING_PAGE: Final = "https://developers.openai.com/api/docs/pricing"
USER_AGENT: Final = "tiktokenizer-py price update (+https://github.com/ailequal/tiktokenizer-py)"

MODES: Final = ("standard", "batch", "flex", "fast", "ultrafast")
REQUIRED_MODES: Final = ("standard", "batch", "flex", "fast")
SNAPSHOT_FILE: Final = "openai_prices.json"
# Version 2 added the cache-write prices; saved snapshots of another version are ignored.
SCHEMA_VERSION: Final = 2

# Fetch limits: the pages are about 25 KB and 4 KB today.
MAX_PAGE_BYTES: Final = 2_000_000
FETCH_TIMEOUT_S: Final = 10
FETCH_WORKERS: Final = 8
REFRESH_INTERVAL_S: Final = 600
# After a failed attempt (no network, layout changed) a retry is allowed sooner.
RETRY_AFTER_FAILURE_S: Final = 30
# Sanity limits for parsed values; anything outside means the layout was misread.
MAX_PRICE_PER_M: Final = 10_000.0
MAX_TOKENS: Final = 100_000_000

Snapshot = dict[str, Any]
Fetcher = Callable[[str], str | None]


class PricingLayoutError(ValueError):
    """OpenAI's pages no longer look the way the parser expects."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


class PricingFetchError(RuntimeError):
    """A page could not be downloaded."""


# --- parsing ----------------------------------------------------------------------------

_MODE_LINES: Final = {
    "standard": "standard",
    "batch": "batch",
    "flex": "flex",
    "fast": "fast",
    "ultrafast": "ultrafast",
    "### standard pricing data": "standard",
    "### batch pricing data": "batch",
    "#### batch": "batch",
    "#### flex": "flex",
    "### fast pricing data": "fast",
    "### ultrafast pricing data": "ultrafast",
}

# Column positions of input, output and cached input, per table layout.
_LONG_HEADER: Final = (
    "model",
    "short context input",
    "short context output",
    "short context cached input",
    "short context 30m write",
    "short context 12h write",
    "long context input",
    "long context output",
    "long context cached input",
    "long context 30m write",
    "long context 12h write",
)
_SIMPLE_HEADER: Final = ("model", "input", "output", "cached input")
_CATEGORY_HEADER: Final = ("category", "model", "input", "output", "cached input")

_THRESHOLD_RE: Final = re.compile(r"Short context:\s*≤\s*(\d+)K input tokens", re.IGNORECASE)
_MODEL_SUFFIX_RE: Final = re.compile(r"\s*\(.*\)\s*$")
_PRICE_RE: Final = re.compile(r"^\$(\d[\d,]*(?:\.\d+)?)$")


@dataclass(frozen=True, slots=True)
class Price:
    """USD per 1M tokens; None when OpenAI lists no price ("-").

    The cache-write prices (30-minute and 12-hour lifetimes) exist only for newer models.
    """

    input: float | None
    cached_input: float | None
    output: float | None
    cache_write_30m: float | None = None
    cache_write_12h: float | None = None

    def as_json(self) -> dict[str, float | None]:
        return {
            "input": self.input,
            "cached_input": self.cached_input,
            "output": self.output,
            "cache_write_30m": self.cache_write_30m,
            "cache_write_12h": self.cache_write_12h,
        }


@dataclass(frozen=True, slots=True)
class ModePrices:
    short: Price
    long: Price | None


@dataclass(frozen=True, slots=True)
class ParsedPricing:
    long_context_threshold: int
    # model name -> mode -> prices
    models: dict[str, dict[str, ModePrices]]
    modes_seen: frozenset[str]


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _price(cell: str, where: str, problems: list[str]) -> float | None:
    if cell == "-":
        return None
    match = _PRICE_RE.match(cell)
    if not match:
        problems.append(f"{where}: unexpected price {cell!r}")
        return None
    value = float(match.group(1).replace(",", ""))
    if not 0 <= value <= MAX_PRICE_PER_M:
        problems.append(f"{where}: price {value} is outside the expected range")
    return value


def parse_pricing(markdown: str, wanted: Iterable[str]) -> ParsedPricing:
    """Read the price tables of ``pricing.md`` for the models in ``wanted``.

    Rows for other models are skipped without being parsed, so unrelated table changes on the
    page (images, audio, tools) cannot break the update.
    """
    wanted_set = set(wanted)
    problems: list[str] = []
    models: dict[str, dict[str, ModePrices]] = {}
    modes_seen: set[str] = set()
    headers_seen: set[tuple[str, ...]] = set()
    mode: str | None = None
    layout: tuple[str, ...] | None = None

    threshold_match = _THRESHOLD_RE.search(markdown)
    threshold = int(threshold_match.group(1)) * 1000 if threshold_match else 0
    if not threshold_match:
        problems.append(
            "the long-context threshold sentence ('Short context: ≤NK input tokens') is missing"
        )

    for raw in markdown.splitlines():
        line = raw.strip()
        lowered = line.lower()
        if lowered in _MODE_LINES:
            mode = _MODE_LINES[lowered]
            # Only real section headings prove that a mode's prices are on the page.
            if lowered.startswith("#"):
                modes_seen.add(mode)
            layout = None
            continue
        if not line.startswith("|"):
            if line:
                layout = None
            continue
        cells = _cells(line)
        if all(set(c) <= {"-", ":"} for c in cells):
            continue
        header = tuple(c.lower() for c in cells)
        if header in (_LONG_HEADER, _SIMPLE_HEADER, _CATEGORY_HEADER):
            layout = header
            headers_seen.add(header)
            continue
        if layout is None or mode is None:
            continue
        name_cell = cells[1] if layout == _CATEGORY_HEADER else cells[0]
        name = _MODEL_SUFFIX_RE.sub("", name_cell)
        if name not in wanted_set or len(cells) != len(layout):
            continue
        where = f"{mode} price of {name}"
        if layout == _LONG_HEADER:
            # Input, cached input, output, 30-minute write, 12-hour write.
            short = Price(*(_price(cells[i], where, problems) for i in (1, 3, 2, 4, 5)))
            long_values = [_price(cells[i], where, problems) for i in (6, 8, 7, 9, 10)]
            long = Price(*long_values) if any(v is not None for v in long_values[:3]) else None
        elif layout == _SIMPLE_HEADER:
            short = Price(*(_price(cells[i], where, problems) for i in (1, 3, 2)))
            long = None
        else:
            short = Price(*(_price(cells[i], where, problems) for i in (2, 4, 3)))
            long = None
        # The first row for a model wins; the page lists each model once per mode.
        models.setdefault(name, {}).setdefault(mode, ModePrices(short=short, long=long))

    for required in REQUIRED_MODES:
        if required not in modes_seen:
            problems.append(f"the {required!r} price section is missing")
    for header in (_LONG_HEADER, _SIMPLE_HEADER, _CATEGORY_HEADER):
        if header not in headers_seen:
            problems.append(f"no table with the columns {' | '.join(header)}")
    if problems:
        raise PricingLayoutError(problems)
    return ParsedPricing(threshold, models, frozenset(modes_seen))


_LIMIT_PATTERNS: Final = {
    "context_window": re.compile(r"^- ([\d,]+) context window$"),
    "max_input": re.compile(r"^- Maximum input tokens: ([\d,]+)$"),
    "max_output": re.compile(r"^- ([\d,]+) max output tokens$"),
}


def parse_limits(markdown: str) -> dict[str, int | None]:
    """Context limits from a model page's details list; missing ones are None."""
    limits: dict[str, int | None] = dict.fromkeys(_LIMIT_PATTERNS)
    for raw in markdown.splitlines():
        line = raw.strip()
        for key, pattern in _LIMIT_PATTERNS.items():
            match = pattern.match(line)
            if match and limits[key] is None:
                limits[key] = int(match.group(1).replace(",", ""))
    return limits


# --- overrides and snapshot -------------------------------------------------------------


def load_overrides() -> dict[str, Any]:
    text = resources.files("tiktokenizer_py").joinpath("data/price_overrides.json").read_text()
    data: dict[str, Any] = json.loads(text)
    return data


def pages_to_fetch(model_ids: Iterable[str], overrides: Mapping[str, Any]) -> list[str]:
    """Model pages worth fetching: every model except the retired ones."""
    retired = set(overrides.get("retired", ()))
    return [m for m in model_ids if m not in retired]


def build_snapshot(
    pricing_md: str,
    model_pages: Mapping[str, str | None],
    model_ids: Iterable[str],
    overrides: Mapping[str, Any],
    fetched_at: str,
) -> Snapshot:
    """Combine the pages and the overrides into a snapshot, or raise PricingLayoutError."""
    ids = list(model_ids)
    retired = set(overrides.get("retired", ()))
    model_overrides: Mapping[str, Mapping[str, Any]] = overrides.get("models", {})
    price_name = {m: model_overrides.get(m, {}).get("price_from", m) for m in ids}
    pricing = parse_pricing(pricing_md, price_name.values())
    problems: list[str] = []
    models: dict[str, Any] = {}

    for model in ids:
        override = model_overrides.get(model, {})
        entry: dict[str, Any] = {"prices": {}, "price_note": None, "limits": None}
        if model in retired:
            entry["price_note"] = override.get(
                "no_price", "Retired: no longer listed on OpenAI's pricing page."
            )
            models[model] = entry
            continue

        page = model_pages.get(model)
        if page is None:
            problems.append(f"the model page for {model} could not be found")
        limits = parse_limits(page) if page else dict.fromkeys(_LIMIT_PATTERNS)
        for key, value in override.get("limits", {}).items():
            limits[key] = value
        for key, value in limits.items():
            if value is not None and not 0 < value <= MAX_TOKENS:
                problems.append(f"{model}: {key} {value} is outside the expected range")
        entry["limits"] = limits if any(v is not None for v in limits.values()) else None

        if "no_price" in override:
            entry["price_note"] = override["no_price"]
            models[model] = entry
            continue

        rows = pricing.models.get(price_name[model])
        if not rows or "standard" not in rows:
            problems.append(
                f"no Standard price for {price_name[model]} on the pricing page"
                + (f" (used for {model})" if price_name[model] != model else "")
            )
            continue
        if limits["context_window"] is None and limits["max_input"] is None:
            problems.append(f"the model page for {model} lists no context window")
        if price_name[model] != model:
            entry["price_note"] = override.get("note")
        entry["prices"] = {mode: _mode_json(rows[mode]) for mode in MODES if mode in rows}
        models[model] = entry

    if problems:
        raise PricingLayoutError(problems)
    return {
        "schema": SCHEMA_VERSION,
        "fetched_at": fetched_at,
        "sources": {"pricing": PRICING_URL, "models": MODEL_URL, "page": PRICING_PAGE},
        "long_context_threshold": pricing.long_context_threshold,
        "models": models,
    }


def _mode_json(prices: ModePrices) -> dict[str, Any]:
    long = prices.long.as_json() if prices.long is not None else None
    return {**prices.short.as_json(), "long": long}


# --- fetching ---------------------------------------------------------------------------


def fetch_text(url: str) -> str | None:
    """Download one documentation page; None for a 404. Only OpenAI's docs host is allowed."""
    if not url.startswith("https://developers.openai.com/"):
        raise PricingFetchError(f"refusing to fetch {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_S) as response:
            ctype = response.headers.get("content-type", "")
            if not ctype.startswith(("text/markdown", "text/plain")):
                raise PricingFetchError(f"{url} answered with {ctype or 'no content type'}")
            body: bytes = response.read(MAX_PAGE_BYTES + 1)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise PricingFetchError(f"{url} answered {err.code} {err.reason}") from err
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        raise PricingFetchError(f"could not reach {url}: {err}") from err
    if len(body) > MAX_PAGE_BYTES:
        raise PricingFetchError(f"{url} is larger than {MAX_PAGE_BYTES} bytes")
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as err:
        raise PricingFetchError(f"{url} is not valid UTF-8") from err


def fetch_snapshot(
    model_ids: Iterable[str], fetcher: Fetcher = fetch_text, now: datetime | None = None
) -> Snapshot:
    """Fetch the pricing page and the model pages and build a checked snapshot."""
    ids = list(model_ids)
    overrides = load_overrides()
    pricing_md = fetcher(PRICING_URL)
    if pricing_md is None:
        raise PricingFetchError(f"{PRICING_URL} was not found")
    names = pages_to_fetch(ids, overrides)
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        pages = dict(
            zip(names, pool.map(lambda m: fetcher(MODEL_URL.format(model=m)), names), strict=True)
        )
    stamp = (now or datetime.now(UTC)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return build_snapshot(pricing_md, pages, ids, overrides, stamp)


# --- storage ----------------------------------------------------------------------------


def load_bundled() -> Snapshot:
    text = resources.files("tiktokenizer_py").joinpath(f"data/{SNAPSHOT_FILE}").read_text()
    data: Snapshot = json.loads(text)
    return data


def _valid(snapshot: Any) -> bool:
    return (
        isinstance(snapshot, dict)
        and snapshot.get("schema") == SCHEMA_VERSION
        and isinstance(snapshot.get("fetched_at"), str)
        and isinstance(snapshot.get("models"), dict)
    )


def load_saved(data_dir: Path | None) -> Snapshot | None:
    if data_dir is None:
        return None
    path = data_dir / SNAPSHOT_FILE
    try:
        snapshot = json.loads(path.read_text())
    except OSError, ValueError:
        return None
    return snapshot if _valid(snapshot) else None


def save(snapshot: Snapshot, path: Path) -> None:
    """Write atomically, so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def changes(old: Snapshot, new: Snapshot) -> list[str]:
    """Readable list of price and limit differences between two snapshots."""
    lines: list[str] = []
    old_models: Mapping[str, Any] = old.get("models", {})
    for model, entry in new["models"].items():
        before = old_models.get(model)
        if before is None:
            lines.append(f"{model}: new")
            continue
        for mode, prices in entry["prices"].items():
            previous = before.get("prices", {}).get(mode)
            if previous != prices:
                lines.append(f"{model} {mode}: {_brief(previous)} -> {_brief(prices)}")
        for mode in set(before.get("prices", {})) - set(entry["prices"]):
            lines.append(f"{model} {mode}: removed")
        if before.get("limits") != entry["limits"]:
            lines.append(f"{model} limits: {before.get('limits')} -> {entry['limits']}")
    for model in set(old_models) - set(new["models"]):
        lines.append(f"{model}: removed")
    return lines


def _brief(prices: Mapping[str, Any] | None) -> str:
    if not prices:
        return "none"
    text = f"${prices['input']} in / ${prices['cached_input']} cached / ${prices['output']} out"
    if prices.get("cache_write_30m") is not None:
        text += (
            f" / ${prices['cache_write_30m']} 30m write / ${prices['cache_write_12h']} 12h write"
        )
    if prices.get("long"):
        text += " (long-request prices too)"
    return text


@dataclass
class RefreshResult:
    snapshot: Snapshot
    changes: list[str]
    saved: bool


class RefreshTooSoonError(RuntimeError):
    def __init__(self, wait_s: int) -> None:
        self.wait_s = wait_s
        super().__init__(f"prices were fetched recently; try again in {wait_s} seconds")


class PriceStore:
    """The snapshot in use: the bundled one, or a newer one fetched at runtime."""

    def __init__(
        self,
        data_dir: Path | None,
        model_ids: Callable[[], Iterable[str]],
        fetcher: Fetcher = fetch_text,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.data_dir = data_dir
        self._model_ids = model_ids
        self._fetcher = fetcher
        self._clock = clock
        self._lock = threading.Lock()
        # Monotonic time before which a new refresh is refused.
        self._next_allowed: float | None = None
        bundled = load_bundled()
        saved = load_saved(data_dir)
        # A saved snapshot wins only if it is newer than the one shipped with this version.
        use_saved = saved is not None and saved["fetched_at"] > bundled["fetched_at"]
        self.snapshot: Snapshot = saved if use_saved and saved else bundled
        self.origin = "fetched" if use_saved else "bundled"

    def refresh(self) -> RefreshResult:
        """Fetch, check and apply new prices; on any error the current ones stay."""
        with self._lock:
            now = self._clock()
            if self._next_allowed is not None and now < self._next_allowed:
                raise RefreshTooSoonError(int(self._next_allowed - now) + 1)
            # Set before fetching, so concurrent or repeated clicks cannot pile up requests.
            self._next_allowed = now + RETRY_AFTER_FAILURE_S
            snapshot = fetch_snapshot(self._model_ids(), self._fetcher)
            self._next_allowed = now + REFRESH_INTERVAL_S
            diff = changes(self.snapshot, snapshot)
            saved = False
            if self.data_dir is not None:
                try:
                    save(snapshot, self.data_dir / SNAPSHOT_FILE)
                    saved = True
                except OSError:
                    saved = False
            self.snapshot = snapshot
            self.origin = "fetched"
            return RefreshResult(snapshot=snapshot, changes=diff, saved=saved)
