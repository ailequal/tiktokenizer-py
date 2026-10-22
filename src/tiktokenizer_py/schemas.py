"""Request and response models for the JSON API."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from tiktokenizer_py.catalogue import ChatFamily, Group, Kind
from tiktokenizer_py.chat import Role
from tiktokenizer_py.segments import normalize_text

# Request limits. APP_MAX_TEXT_CHARS and APP_MAX_BODY_BYTES override the text and body limits.
# The text limit is enforced in the route so it can answer 413.
MAX_TEXT_CHARS = 200_000
MAX_MESSAGES = 100
MAX_DECODE_TOKENS = 200_000
MAX_BODY_BYTES = 1_000_000
MAX_MERGE_CHUNK_CHARS = 1_000

# JSON can carry lone surrogates ("\ud800"); they cannot be encoded as UTF-8, so replace them
# with U+FFFD on the way in, as tiktoken does.
InputText = Annotated[str, AfterValidator(normalize_text)]

ModelName = Annotated[
    str,
    Field(
        min_length=1, max_length=128, description="Model id or encoding name", examples=["gpt-5"]
    ),
]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatMessage(_Request):
    role: Role
    content: InputText = ""
    name: Annotated[InputText, Field(max_length=64)] = ""


class TokenizeRequest(_Request):
    """Either ``text`` or ``messages`` must be given, not both."""

    model: ModelName
    text: InputText | None = None
    messages: Annotated[list[ChatMessage] | None, Field(max_length=MAX_MESSAGES)] = None
    allow_special: bool = Field(
        default=True,
        description="Tokenize <|...|> sequences in the text as special tokens. "
        "False tokenizes them as plain text (encode_ordinary).",
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"model": "gpt-5", "text": "hello world"},
                {
                    "model": "gpt-5",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant"},
                        {"role": "user", "content": "Hi!"},
                    ],
                },
            ]
        },
    )

    @model_validator(mode="after")
    def _text_xor_messages(self) -> Self:
        if (self.text is None) == (self.messages is None):
            raise ValueError("Provide exactly one of 'text' or 'messages'")
        return self

    def input_chars(self) -> int:
        if self.messages is not None:
            return sum(len(m.content) + len(m.name) for m in self.messages)
        return len(self.text or "")


class TokenRef(BaseModel):
    id: int
    idx: int


class SegmentOut(BaseModel):
    text: str
    tokens: list[TokenRef]
    special: bool


class TokenizeResponse(BaseModel):
    model: str
    encoding: str
    rendered_text: str | None = Field(
        default=None, description="Chat mode only: the messages rendered with chat framing"
    )
    count: int
    characters: int = Field(description="Characters (Unicode code points) in the tokenized text")
    bytes: int = Field(description="UTF-8 bytes in the tokenized text")
    tokens: list[int]
    segments: list[SegmentOut]
    is_estimate: bool
    note: str | None = None


class DecodeRequest(_Request):
    model: ModelName
    # Token ids are unsigned 32-bit integers in tiktoken.
    tokens: Annotated[
        list[Annotated[int, Field(ge=0, le=2**32 - 1)]], Field(max_length=MAX_DECODE_TOKENS)
    ]


class DecodedPiece(BaseModel):
    id: int
    bytes: str = Field(description="Raw token bytes as space separated hex, e.g. 'e2 80 8d'")
    text: str = Field(description="The bytes decoded as UTF-8; U+FFFD marks partial characters")
    special: bool
    partial: bool = Field(description="True when the bytes are only part of a character")


class DecodeResponse(BaseModel):
    model: str
    encoding: str
    text: str
    pieces: list[DecodedPiece]


class ChunkOut(BaseModel):
    text: str
    special: bool = Field(description="A special token, kept whole instead of split and merged")
    tokens: list[int]


class ExplainResponse(BaseModel):
    model: str
    encoding: str
    pattern: str = Field(description="The split pattern (regular expression) of the encoding")
    total_chunks: int
    chunks: list[ChunkOut] = Field(description="The chunks, at most the first 2000")


class MergesRequest(_Request):
    model: ModelName
    chunk: Annotated[InputText, Field(min_length=1, max_length=MAX_MERGE_CHUNK_CHARS)]


class MergePiece(BaseModel):
    bytes: str = Field(description="Raw bytes as space separated hex")
    text: str = Field(description="The bytes decoded as UTF-8; U+FFFD marks partial characters")


class MergeStepOut(BaseModel):
    pieces: list[MergePiece]
    merged: int | None = Field(description="Index of the piece created in this step")


class MergesResponse(BaseModel):
    model: str
    encoding: str
    chunk: str
    steps: list[MergeStepOut] = Field(description="Start state, then one entry per merge")
    tokens: list[int] = Field(description="Final token ids, equal to what tiktoken returns")


class CompareRequest(_Request):
    text: InputText
    allow_special: bool = True


class CompareRow(BaseModel):
    encoding: str
    count: int
    characters_per_token: float | None
    models: list[str] = Field(description="Models in the catalogue that use this encoding")


class CompareResponse(BaseModel):
    characters: int
    rows: list[CompareRow]


class PriceRow(BaseModel):
    """USD per 1M tokens; None where OpenAI lists no price."""

    input: float | None
    cached_input: float | None
    output: float | None
    cache_write_30m: float | None = Field(
        default=None, description="Writing input to the cache with a 30-minute lifetime"
    )
    cache_write_12h: float | None = Field(
        default=None, description="Writing input to the cache with a 12-hour lifetime"
    )


class ModePrice(PriceRow):
    long: PriceRow | None = Field(
        description="Prices for the whole request when the input is above long_context_threshold"
    )


class ModelLimits(BaseModel):
    context_window: int | None
    max_input: int | None
    max_output: int | None


class ModelPricing(BaseModel):
    prices: dict[str, ModePrice] = Field(description="Per mode: standard, batch, flex, fast, ...")
    price_note: str | None
    limits: ModelLimits | None


class PricesResponse(BaseModel):
    origin: Literal["bundled", "fetched"] = Field(
        description="bundled: the snapshot shipped with the app; fetched: refreshed at runtime"
    )
    fetched_at: str = Field(description="When the prices were read from OpenAI (UTC, ISO 8601)")
    long_context_threshold: int
    sources: dict[str, str]
    refresh_interval_s: int
    models: dict[str, ModelPricing]


class RefreshResponse(BaseModel):
    prices: PricesResponse
    changes: list[str] = Field(description="Readable list of prices and limits that changed")
    saved: bool = Field(description="False when the data directory is not writable")


class ReservedTokens(BaseModel):
    count: int
    first: int
    last: int


class EncodingSummary(BaseModel):
    name: str
    source: Literal["tiktoken", "derived"]
    n_vocab: int


class EncodingInfo(BaseModel):
    name: str
    source: Literal["tiktoken", "derived"]
    base: str | None = Field(default=None, description="Base encoding of a derived chat variant")
    n_vocab: int
    eot_token: int | None
    special_tokens: dict[str, int] = Field(description="Special tokens, without <|reserved_N|>")
    reserved_tokens: ReservedTokens | None = None
    pat_str: str
    models: list[str]


class ModelInfo(BaseModel):
    id: str
    kind: Kind
    group: Group
    encoding: str = Field(
        description="Encoding for chat messages and decoding (a chat variant for ChatML models)"
    )
    base_encoding: str = Field(
        description="Encoding reported by tiktoken for this model, used for plain text"
    )
    chat_family: ChatFamily | None
    is_chat: bool
    deprecated: bool


class ModelGroup(BaseModel):
    id: Group
    label: str
    items: list[str]


class ModelsResponse(BaseModel):
    default: str
    groups: list[ModelGroup]
    models: list[ModelInfo]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
