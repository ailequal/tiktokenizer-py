"""Group tokens into segments that line up with the grapheme clusters of the input.

A single token can hold part of a multi-byte character, and a single grapheme (a ZWJ emoji
family, a flag, a letter with combining marks) can span several tokens. The algorithm
accumulates token bytes until they decode to whole graphemes of the input, then emits that run
of tokens as one segment.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import regex
import tiktoken

_GRAPHEME = regex.compile(r"\X")


@dataclass(frozen=True, slots=True)
class TokenRef:
    id: int
    idx: int  # position of the token in the full token list


@dataclass(frozen=True, slots=True)
class Segment:
    text: str
    tokens: list[TokenRef] = field(default_factory=list)
    special: bool = False


def normalize_text(text: str) -> str:
    """Replace lone surrogates with U+FFFD, as tiktoken does before encoding."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    return text


def encode(enc: tiktoken.Encoding, text: str, *, allow_special: bool = True) -> list[int]:
    """Encode ``text``; special tokens typed in the text count as special when allowed."""
    if allow_special:
        return enc.encode(text, allowed_special="all")
    return enc.encode_ordinary(text)


def encode_parts(
    enc: tiktoken.Encoding, parts: Sequence[tuple[str, bool]], *, allow_special: bool = True
) -> list[int]:
    """Encode rendered chat parts: framing parts are always special tokens, the text between
    them follows ``allow_special``. tiktoken splits text on special tokens before encoding, so
    this equals encoding the joined text when ``allow_special`` is true."""
    tokens: list[int] = []
    for text, special in parts:
        if special:
            tokens.append(enc.encode_single_token(text))
        else:
            tokens += encode(enc, text, allow_special=allow_special)
    return tokens


def segment_tokens(enc: tiktoken.Encoding, text: str, tokens: list[int]) -> list[Segment]:
    """Group ``tokens`` (the encoding of ``text``) into grapheme-aligned segments."""
    pending = _GRAPHEME.findall(normalize_text(text))
    segments: list[Segment] = []
    byte_acc = bytearray()
    token_acc: list[TokenRef] = []
    pos = 0

    for idx, token in enumerate(tokens):
        byte_acc += enc.decode_single_token_bytes(token)
        token_acc.append(TokenRef(id=token, idx=idx))
        # An incomplete UTF-8 sequence decodes to U+FFFD, which never matches the input.
        piece = byte_acc.decode("utf-8", errors="replace")
        graphemes = _GRAPHEME.findall(piece)
        if graphemes == pending[pos : pos + len(graphemes)]:
            special = len(token_acc) == 1 and enc.is_special_token(token)
            segments.append(Segment(text=piece, tokens=token_acc, special=special))
            byte_acc = bytearray()
            token_acc = []
            pos += len(graphemes)

    if token_acc:
        # Only reachable if decoding does not round-trip; keep every token visible anyway.
        segments.append(Segment(text=byte_acc.decode("utf-8", errors="replace"), tokens=token_acc))
    return segments


def tokenize(
    enc: tiktoken.Encoding, text: str, *, allow_special: bool = True
) -> tuple[list[int], list[Segment]]:
    """Encode ``text`` and return the tokens with their segments."""
    tokens = encode(enc, text, allow_special=allow_special)
    return tokens, segment_tokens(enc, text, tokens)
