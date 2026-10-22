"""JSON API under ``/api``: tokenize, explain, compare, decode, prices, models and encodings."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import tiktoken
from fastapi import APIRouter, Request, status

from tiktokenizer_py import catalogue, chat, explain, prices, segments, tokenizers
from tiktokenizer_py.errors import ApiError
from tiktokenizer_py.schemas import (
    ChunkOut,
    CompareRequest,
    CompareResponse,
    CompareRow,
    DecodedPiece,
    DecodeRequest,
    DecodeResponse,
    EncodingInfo,
    EncodingSummary,
    ErrorResponse,
    ExplainResponse,
    MergePiece,
    MergesRequest,
    MergesResponse,
    MergeStepOut,
    ModelGroup,
    ModelInfo,
    ModelsResponse,
    PricesResponse,
    RefreshResponse,
    ReservedTokens,
    SegmentOut,
    TokenizeRequest,
    TokenizeResponse,
    TokenRef,
)
from tiktokenizer_py.settings import Settings

ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    413: {"model": ErrorResponse, "description": "Input or body too large"},
    422: {"model": ErrorResponse, "description": "Invalid request or unknown model"},
}

router = APIRouter(prefix="/api", tags=["api"])


def settings_of(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _lookup(name: str) -> catalogue.CatalogueEntry:
    try:
        return catalogue.lookup(name)
    except KeyError:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unknown_model",
            f"Unknown model or encoding {name!r}. See details.valid for the accepted names.",
            details={"valid": catalogue.ids()},
        ) from None


def _segments_out(segs: list[segments.Segment]) -> list[SegmentOut]:
    return [
        SegmentOut(
            text=s.text,
            tokens=[TokenRef(id=t.id, idx=t.idx) for t in s.tokens],
            special=s.special,
        )
        for s in segs
    ]


def model_ids() -> list[str]:
    return [e.id for e in catalogue.entries() if e.kind == "model"]


def price_store(request: Request) -> prices.PriceStore:
    store: prices.PriceStore = request.app.state.prices
    return store


def _wait_text(seconds: int) -> str:
    """A wait as "45 seconds" or "3 minutes", rounded up so the retry is never too early."""
    if seconds < 60:
        return f"{seconds} second" + ("" if seconds == 1 else "s")
    minutes = -(-seconds // 60)
    return f"{minutes} minute" + ("" if minutes == 1 else "s")


def prices_response(store: prices.PriceStore) -> PricesResponse:
    return PricesResponse.model_validate(
        {
            **store.snapshot,
            "origin": store.origin,
            "refresh_interval_s": prices.REFRESH_INTERVAL_S,
        }
    )


@dataclass(frozen=True, slots=True)
class _Prepared:
    entry: catalogue.CatalogueEntry
    enc: tiktoken.Encoding
    text: str
    parts: list[tuple[str, bool]]  # (text, is_framing_special_token)
    rendered: chat.RenderedChat | None


def _check_length(chars: int, request: Request) -> None:
    limit = settings_of(request).max_text_chars
    if chars > limit:
        raise ApiError(
            status.HTTP_413_CONTENT_TOO_LARGE,
            "input_too_large",
            f"Input is {chars:,} characters, longer than the limit of {limit:,}.",
            details={"limit": limit, "length": chars},
        )


def _prepare(body: TokenizeRequest, request: Request) -> _Prepared:
    """Resolve the model and the exact text to tokenize (plain text or rendered chat)."""
    _check_length(body.input_chars(), request)
    entry = _lookup(body.model)
    if body.messages is None:
        text = body.text or ""
        # Plain text uses exactly the encoding tiktoken reports for the model.
        return _Prepared(entry, tokenizers.resolve(entry.id), text, [(text, False)], None)
    if entry.chat_family is None:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "not_a_chat_model",
            f"{entry.id!r} is not a chat model; send 'text' instead of 'messages'",
        )
    messages = [chat.Message(role=m.role, content=m.content, name=m.name) for m in body.messages]
    rendered = chat.render(messages, entry.chat_family)
    enc = tokenizers.resolve(entry.id, chat=True)
    return _Prepared(entry, enc, rendered.text, list(rendered.parts), rendered)


# Sync routes run in the threadpool, so a large prompt does not block the event loop.
@router.post("/tokenize", responses=ERROR_RESPONSES)
def tokenize(body: TokenizeRequest, request: Request) -> TokenizeResponse:
    prep = _prepare(body, request)
    if prep.rendered is None:
        tokens = segments.encode(prep.enc, prep.text, allow_special=body.allow_special)
    else:
        tokens = segments.encode_parts(prep.enc, prep.parts, allow_special=body.allow_special)
    return TokenizeResponse(
        model=prep.entry.id,
        encoding=prep.enc.name,
        rendered_text=prep.rendered.text if prep.rendered else None,
        count=len(tokens),
        characters=len(prep.text),
        bytes=len(prep.text.encode("utf-8")),
        tokens=tokens,
        segments=_segments_out(segments.segment_tokens(prep.enc, prep.text, tokens)),
        is_estimate=prep.rendered.is_estimate if prep.rendered else False,
        note=prep.rendered.note if prep.rendered else None,
    )


@router.post("/explain", responses=ERROR_RESPONSES)
def explain_tokens(body: TokenizeRequest, request: Request) -> ExplainResponse:
    """The chunks the split pattern makes, and the tokens inside each chunk."""
    prep = _prepare(body, request)
    chunks = explain.split_chunks(prep.enc, prep.parts, allow_special=body.allow_special)
    return ExplainResponse(
        model=prep.entry.id,
        encoding=prep.enc.name,
        pattern=prep.enc._pat_str,
        total_chunks=len(chunks),
        chunks=[
            ChunkOut(text=c.text, special=c.special, tokens=c.tokens)
            for c in chunks[: explain.MAX_CHUNKS]
        ],
    )


@router.post("/merges", responses=ERROR_RESPONSES)
def merges(body: MergesRequest) -> MergesResponse:
    """Replay the byte pair merges that turn one chunk into tokens."""
    entry = _lookup(body.model)
    enc = tokenizers.resolve(entry.id)
    steps = explain.merge_steps(enc._mergeable_ranks, body.chunk.encode("utf-8"))
    return MergesResponse(
        model=entry.id,
        encoding=enc.name,
        chunk=body.chunk,
        steps=[
            MergeStepOut(
                pieces=[
                    MergePiece(bytes=p.hex(" "), text=p.decode("utf-8", errors="replace"))
                    for p in step.pieces
                ],
                merged=step.merged,
            )
            for step in steps
        ],
        tokens=explain.chunk_tokens(enc, body.chunk),
    )


@router.post("/compare", responses=ERROR_RESPONSES)
def compare(body: CompareRequest, request: Request) -> CompareResponse:
    """Token counts for the same text under every tiktoken encoding."""
    _check_length(len(body.text), request)
    rows = []
    for name in catalogue.tiktoken_encoding_names():
        enc = tokenizers.get_encoding(name)
        count = len(segments.encode(enc, body.text, allow_special=body.allow_special))
        rows.append(
            CompareRow(
                encoding=name,
                count=count,
                characters_per_token=round(len(body.text) / count, 2) if count else None,
                models=catalogue.models_using(name),
            )
        )
    return CompareResponse(characters=len(body.text), rows=rows)


@router.get("/prices")
def get_prices(request: Request) -> PricesResponse:
    """Reference prices (USD per 1M tokens) and context limits for the catalogue models."""
    return prices_response(price_store(request))


@router.post(
    "/prices/refresh",
    responses={
        429: {"model": ErrorResponse, "description": "Fetched too recently"},
        502: {"model": ErrorResponse, "description": "OpenAI's pages could not be read"},
    },
)
def refresh_prices(request: Request) -> RefreshResponse:
    """Fetch OpenAI's pricing and model pages again; on any error the current prices stay."""
    store = price_store(request)
    try:
        result = store.refresh()
    except prices.RefreshTooSoonError as err:
        raise ApiError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "refresh_too_soon",
            f"Prices were fetched or tried very recently. Try again in {_wait_text(err.wait_s)}.",
            details={"retry_after_s": err.wait_s},
            headers={"Retry-After": str(err.wait_s)},
        ) from None
    except prices.PricingLayoutError as err:
        raise ApiError(
            status.HTTP_502_BAD_GATEWAY,
            "prices_layout_changed",
            "OpenAI's pricing pages no longer match the expected layout, so the current "
            "prices were kept.",
            details={"problems": err.problems},
        ) from None
    except prices.PricingFetchError as err:
        raise ApiError(
            status.HTTP_502_BAD_GATEWAY,
            "prices_fetch_failed",
            f"Could not download OpenAI's pricing pages, so the current prices were kept. {err}",
        ) from None
    return RefreshResponse(
        prices=prices_response(store), changes=result.changes, saved=result.saved
    )


def _is_utf8(raw: bytes) -> bool:
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


@router.post("/decode", responses=ERROR_RESPONSES)
def decode(body: DecodeRequest) -> DecodeResponse:
    entry = _lookup(body.model)
    # The chat variant is a superset, so ids of chat framing tokens decode too.
    enc = tokenizers.resolve(entry.id, chat=True)
    pieces: list[DecodedPiece] = []
    invalid: list[int] = []
    for token in body.tokens:
        try:
            raw = enc.decode_single_token_bytes(token)
        except KeyError, OverflowError:
            invalid.append(token)
            continue
        pieces.append(
            DecodedPiece(
                id=token,
                bytes=raw.hex(" "),
                text=raw.decode("utf-8", errors="replace"),
                special=enc.is_special_token(token),
                partial=not _is_utf8(raw),
            )
        )
    if invalid:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_token",
            f"Token ids not in {enc.name}: {invalid[:20]}",
            details={"invalid": invalid},
        )
    return DecodeResponse(
        model=entry.id,
        encoding=enc.name,
        text=enc.decode(body.tokens, errors="replace"),
        pieces=pieces,
    )


@cache
def models_response() -> ModelsResponse:
    return ModelsResponse(
        default=catalogue.DEFAULT_MODEL,
        groups=[
            ModelGroup(id=group, label=catalogue.GROUP_LABELS[group], items=[e.id for e in items])
            for group, items in catalogue.groups()
        ],
        models=[
            ModelInfo(
                id=e.id,
                kind=e.kind,
                group=e.group,
                encoding=tokenizers.encoding_name_for(e),
                base_encoding=e.encoding,
                chat_family=e.chat_family,
                is_chat=e.is_chat,
                deprecated=e.deprecated,
            )
            for e in catalogue.entries()
        ],
    )


@router.get("/models")
def list_models() -> ModelsResponse:
    return models_response()


@router.get("/encodings")
def list_encodings() -> list[EncodingSummary]:
    return [
        EncodingSummary(
            name=name,
            source="derived" if name in catalogue.CHAT_VARIANTS else "tiktoken",
            n_vocab=tokenizers.get_encoding(name).n_vocab,
        )
        for name in tokenizers.all_encoding_names()
    ]


_RESERVED_PREFIX = "<|reserved_"


@cache
def encoding_info(name: str) -> EncodingInfo:
    enc = tokenizers.get_encoding(name)
    special = enc._special_tokens
    reserved = sorted(v for k, v in special.items() if k.startswith(_RESERVED_PREFIX))
    return EncodingInfo(
        name=name,
        source="derived" if name in catalogue.CHAT_VARIANTS else "tiktoken",
        base=catalogue.CHAT_VARIANTS.get(name),
        n_vocab=enc.n_vocab,
        eot_token=special.get("<|endoftext|>"),
        special_tokens=dict(
            sorted(
                ((k, v) for k, v in special.items() if not k.startswith(_RESERVED_PREFIX)),
                key=lambda kv: kv[1],
            )
        ),
        reserved_tokens=(
            ReservedTokens(count=len(reserved), first=reserved[0], last=reserved[-1])
            if reserved
            else None
        ),
        pat_str=enc._pat_str,
        models=catalogue.models_using(name),
    )


@router.get("/encodings/{name}", responses={404: {"model": ErrorResponse}})
def get_encoding_info(name: str) -> EncodingInfo:
    if name not in tokenizers.all_encoding_names():
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            "unknown_encoding",
            f"Unknown encoding {name!r}",
            details={"valid": tokenizers.all_encoding_names()},
        )
    return encoding_info(name)
