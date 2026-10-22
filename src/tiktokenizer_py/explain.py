"""Show how tiktoken turns text into tokens, one stage at a time.

tiktoken works in two stages:

1. **Split.** Special tokens (when allowed) are cut out first. The rest of the text is cut into
   chunks by the encoding's split pattern (words with their leading space, numbers of up to
   three digits in newer encodings, punctuation, whitespace runs). Tokens never cross a chunk
   border.
2. **Merge.** Each chunk starts as single bytes. The pair of neighbours with the lowest rank in
   the encoding's merge list is joined, again and again, until no known pair is left. Every
   remaining piece is a token, and its rank is its id.

This module replays both stages with the encoding's own data, so the result equals what
``Encoding.encode`` returns (the tests check this).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cache

import regex
import tiktoken

# Above this many chunks the response lists only the first ones; the count covers all.
MAX_CHUNKS = 2000


@dataclass(frozen=True, slots=True)
class Chunk:
    text: str
    special: bool
    tokens: list[int] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class MergeStep:
    pieces: list[bytes]
    merged: int | None  # index of the piece created in this step; None for the start


@cache
def _pattern(pat_str: str) -> regex.Pattern[str]:
    return regex.compile(pat_str)


@cache
def _special_pattern(enc: tiktoken.Encoding) -> regex.Pattern[str] | None:
    specials = enc.special_tokens_set
    if not specials:
        return None
    # Longest first, so a token that is a prefix of another never wins.
    alternatives = sorted(specials, key=len, reverse=True)
    return regex.compile("|".join(regex.escape(s) for s in alternatives))


def merge_steps(ranks: dict[bytes, int], piece: bytes) -> list[MergeStep]:
    """Replay byte pair merging for one chunk, as tiktoken's ``byte_pair_merge`` does.

    The lowest-ranked pair is merged first; on equal ranks the leftmost pair wins.
    """
    parts = [bytes([b]) for b in piece]
    steps = [MergeStep(pieces=list(parts), merged=None)]
    while len(parts) > 1:
        best: tuple[int, int] | None = None
        for i in range(len(parts) - 1):
            rank = ranks.get(parts[i] + parts[i + 1])
            if rank is not None and (best is None or rank < best[0]):
                best = (rank, i)
        if best is None:
            break
        i = best[1]
        parts = [*parts[:i], parts[i] + parts[i + 1], *parts[i + 2 :]]
        steps.append(MergeStep(pieces=list(parts), merged=i))
    return steps


def chunk_tokens(enc: tiktoken.Encoding, chunk: str) -> list[int]:
    """Token ids for one ordinary chunk."""
    ranks = enc._mergeable_ranks
    raw = chunk.encode("utf-8")
    # tiktoken looks the whole chunk up first, then falls back to merging.
    if raw in ranks:
        return [ranks[raw]]
    return [ranks[p] for p in merge_steps(ranks, raw)[-1].pieces]


def split_chunks(
    enc: tiktoken.Encoding, parts: Sequence[tuple[str, bool]], *, allow_special: bool
) -> list[Chunk]:
    """Split rendered parts into chunks with their tokens.

    ``parts`` is a list of ``(text, is_framing_special_token)``. Plain text is one ordinary part.
    """
    pattern = _pattern(enc._pat_str)
    specials = _special_pattern(enc)
    chunks: list[Chunk] = []

    def ordinary(text: str) -> None:
        for match in pattern.findall(text):
            chunks.append(Chunk(text=match, special=False, tokens=chunk_tokens(enc, match)))

    for text, framing in parts:
        if framing:
            chunks.append(Chunk(text=text, special=True, tokens=[enc.encode_single_token(text)]))
            continue
        if not allow_special or specials is None:
            ordinary(text)
            continue
        start = 0
        for found in specials.finditer(text):
            ordinary(text[start : found.start()])
            token = found.group()
            chunks.append(Chunk(text=token, special=True, tokens=[enc.encode_single_token(token)]))
            start = found.end()
        ordinary(text[start:])
    return chunks
