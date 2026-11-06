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

The split pattern is evaluated by the ``regex`` module, tiktoken evaluates it in Rust. The two
ship different Unicode tables, so a code point that one assigns to a letter category and the
other does not (usually one assigned in a recent Unicode version) can be cut differently. The
tokens are always taken from tiktoken: when the replayed chunks disagree with it, the chunks are
realigned on tiktoken's token borders (see ``_realign``).
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
        guessed = [
            Chunk(text=match, special=False, tokens=chunk_tokens(enc, match))
            for match in pattern.findall(text)
        ]
        expected = enc.encode_ordinary(text)
        if [t for c in guessed for t in c.tokens] == expected:
            chunks.extend(guessed)
        else:
            chunks.extend(_realign(enc, guessed, expected))

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


def _realign(enc: tiktoken.Encoding, guessed: list[Chunk], expected: list[int]) -> list[Chunk]:
    """Rebuild ``guessed`` so that its tokens are exactly ``expected``, tiktoken's own result.

    Tokens never cross a chunk border, so a border that falls inside one of tiktoken's tokens
    is wrong: such chunks are joined with the next until the border lands between two tokens.
    A joined run is then cut again between tokens wherever the pieces are whole characters
    and reproduce their tokens on their own, so the merge replay of each chunk stays exact.
    When that is not possible the run stays one chunk carrying tiktoken's tokens.
    """
    token_bytes = [enc.decode_single_token_bytes(t) for t in expected]
    ends: dict[int, int] = {}  # byte offset where a token ends -> index of the next token
    pos = 0
    for i, raw in enumerate(token_bytes):
        pos += len(raw)
        ends[pos] = i + 1

    result: list[Chunk] = []
    offset = 0
    first = 0  # index of the first token of the current run
    run: list[Chunk] = []
    for chunk in guessed:
        run.append(chunk)
        offset += len(chunk.text.encode("utf-8"))
        if offset not in ends:
            continue
        last = ends[offset]
        slice_ = expected[first:last]
        if len(run) == 1 and run[0].tokens == slice_:
            result.append(run[0])
        else:
            result.extend(_cut(enc, "".join(c.text for c in run), token_bytes[first:last], slice_))
        first, run = last, []
    return result


def _cut(
    enc: tiktoken.Encoding, text: str, token_bytes: list[bytes], tokens: list[int]
) -> list[Chunk]:
    """Cut ``text`` between its tokens into chunks that each reproduce their tokens."""
    pieces: list[Chunk] = []
    acc = bytearray()
    start = 0
    for i, raw in enumerate(token_bytes):
        acc += raw
        try:
            piece = acc.decode("utf-8")
        except UnicodeDecodeError:
            continue  # the border falls inside a character; keep going
        piece_tokens = tokens[start : i + 1]
        if chunk_tokens(enc, piece) != piece_tokens:
            return [Chunk(text=text, special=False, tokens=tokens)]
        pieces.append(Chunk(text=piece, special=False, tokens=piece_tokens))
        acc, start = bytearray(), i + 1
    return pieces
