"""Resolve catalogue entries to tiktoken ``Encoding`` objects.

ChatML models (the ``im_sep`` family) are tokenized with a derived
``<base>_chat`` encoding that adds ``<|im_start|>``, ``<|im_end|>`` and ``<|im_sep|>`` as special
tokens. Building an ``Encoding`` constructs a new Rust ``CoreBPE``, so variants are cached per
process and built once at startup by ``warm_up``.
"""

from __future__ import annotations

import threading
from functools import cache

import tiktoken

from tiktokenizer_py import catalogue
from tiktokenizer_py.catalogue import (
    CHAT_VARIANT_SPECIAL_TOKENS,
    CHAT_VARIANTS,
    CatalogueEntry,
    ChatFamily,
)

_variant_lock = threading.Lock()


@cache
def _build_chat_variant(base_name: str) -> tiktoken.Encoding:
    base = tiktoken.get_encoding(base_name)
    # tiktoken documents extending an encoding through these private attributes.
    return tiktoken.Encoding(
        name=catalogue.chat_variant_name(base_name),
        pat_str=base._pat_str,
        mergeable_ranks=base._mergeable_ranks,
        special_tokens={**base._special_tokens, **CHAT_VARIANT_SPECIAL_TOKENS[base_name]},
    )


def chat_variant(base_name: str) -> tiktoken.Encoding:
    """Return ``base_name`` extended with the ChatML special tokens (cached)."""
    if base_name not in CHAT_VARIANT_SPECIAL_TOKENS:
        raise KeyError(f"No chat variant for encoding {base_name!r}")
    # The lock stops two threads from building the same large CoreBPE at once.
    with _variant_lock:
        return _build_chat_variant(base_name)


def encoding_name_for(entry: CatalogueEntry, *, chat: bool = True) -> str:
    """Name of the encoding for ``entry``.

    Plain text uses exactly the encoding tiktoken reports for the model. With ``chat`` (chat
    rendering and decoding), ChatML models use the derived ``<base>_chat`` encoding, a superset
    that also knows the framing tokens.
    """
    is_chatml = entry.chat_family is ChatFamily.IM_SEP
    if chat and entry.kind == "model" and is_chatml:
        return catalogue.chat_variant_name(entry.encoding)
    return entry.encoding


def get_encoding(name: str) -> tiktoken.Encoding:
    """Load a tiktoken encoding or one of the derived chat variants by name."""
    if name in CHAT_VARIANTS:
        return chat_variant(CHAT_VARIANTS[name])
    return tiktoken.get_encoding(name)


def resolve(model_or_encoding: str, *, chat: bool = False) -> tiktoken.Encoding:
    """Return the encoding for a catalogue model id or encoding name.

    ``chat=False`` gives the encoding tiktoken itself uses for plain text; ``chat=True`` gives the
    encoding for rendered chat messages and for decoding ids. Raises KeyError when the name is not
    in the catalogue.
    """
    return get_encoding(encoding_name_for(catalogue.lookup(model_or_encoding), chat=chat))


def all_encoding_names() -> list[str]:
    return [*catalogue.tiktoken_encoding_names(), *CHAT_VARIANTS]


def warm_up() -> None:
    """Load every encoding and build the chat variants so the first request is fast."""
    for name in all_encoding_names():
        get_encoding(name)
