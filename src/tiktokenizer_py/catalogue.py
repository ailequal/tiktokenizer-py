"""Catalogue of the OpenAI models and encodings shown in the selector.

Model ids come from the OpenAI models page. The encoding of every model is always taken from
``tiktoken.encoding_name_for_model``: there is no override map, so a model only appears here
once tiktoken knows how to tokenize it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from typing import Literal

import tiktoken


class Group(StrEnum):
    POPULAR = "popular"
    CURRENT = "current"
    LEGACY = "legacy"
    ENCODINGS = "encodings"


GROUP_LABELS: dict[Group, str] = {
    Group.POPULAR: "Popular",
    Group.CURRENT: "OpenAI models",
    Group.LEGACY: "Legacy OpenAI models",
    Group.ENCODINGS: "OpenAI encodings",
}


class ChatFamily(StrEnum):
    """How chat messages are framed with special tokens before tokenizing."""

    IM_SEP = "im_sep"  # ChatML: <|im_start|>role<|im_sep|>content<|im_end|>
    HARMONY = "harmony"  # gpt-oss: <|start|>role<|message|>content<|end|>


Kind = Literal["model", "encoding"]


@dataclass(frozen=True, slots=True)
class CatalogueEntry:
    id: str
    kind: Kind
    encoding: str
    group: Group
    chat_family: ChatFamily | None = None
    deprecated: bool = False
    encoding_source: Literal["tiktoken", "derived"] = "tiktoken"

    @property
    def is_chat(self) -> bool:
        return self.chat_family is not None


# Extra special tokens used by the community-documented ChatML framing. They are not part of
# tiktoken's public encodings, so the derived "<base>_chat" encodings add them.
CHAT_VARIANT_SPECIAL_TOKENS: dict[str, dict[str, int]] = {
    "cl100k_base": {"<|im_start|>": 100264, "<|im_end|>": 100265, "<|im_sep|>": 100266},
    "o200k_base": {"<|im_start|>": 200264, "<|im_end|>": 200265, "<|im_sep|>": 200266},
}


def chat_variant_name(base: str) -> str:
    return f"{base}_chat"


CHAT_VARIANTS: dict[str, str] = {chat_variant_name(b): b for b in CHAT_VARIANT_SPECIAL_TOKENS}

# OpenAI model ids that tiktoken cannot map yet. A test asserts they still raise KeyError, so a
# tiktoken release that maps them is noticed and they can move into CURRENT_MODELS.
KNOWN_UNMAPPED: tuple[str, ...] = ("gpt-6-astra", "gpt-6.1-sol", "gpt-6-luna", "gpt-6-sol")

# (model id, chat family), newest first.
CURRENT_MODELS: tuple[tuple[str, ChatFamily | None], ...] = (
    ("gpt-5.6-sol", ChatFamily.IM_SEP),
    ("gpt-5.6-terra", ChatFamily.IM_SEP),
    ("gpt-5.6-luna", ChatFamily.IM_SEP),
    ("gpt-5.6-cyber", ChatFamily.IM_SEP),
    ("gpt-5.5", ChatFamily.IM_SEP),
    ("gpt-5.5-pro", ChatFamily.IM_SEP),
    ("gpt-5.4", ChatFamily.IM_SEP),
    ("gpt-5.4-pro", ChatFamily.IM_SEP),
    ("gpt-5.4-mini", ChatFamily.IM_SEP),
    ("gpt-5.4-nano", ChatFamily.IM_SEP),
    ("gpt-5.2", ChatFamily.IM_SEP),
    ("gpt-5.2-pro", ChatFamily.IM_SEP),
    ("gpt-5", ChatFamily.IM_SEP),
    ("gpt-5-pro", ChatFamily.IM_SEP),
    ("gpt-5-mini", ChatFamily.IM_SEP),
    ("gpt-5-nano", ChatFamily.IM_SEP),
    ("o3", ChatFamily.IM_SEP),
    ("o3-pro", ChatFamily.IM_SEP),
    ("gpt-oss-120b", ChatFamily.HARMONY),
    ("gpt-oss-20b", ChatFamily.HARMONY),
    ("text-embedding-3-large", None),
    ("text-embedding-3-small", None),
    ("text-embedding-ada-002", None),
)

LEGACY_MODELS: tuple[tuple[str, ChatFamily | None], ...] = (
    ("gpt-5.1", ChatFamily.IM_SEP),
    ("gpt-4.5-preview", ChatFamily.IM_SEP),
    ("gpt-4.1", ChatFamily.IM_SEP),
    ("gpt-4.1-mini", ChatFamily.IM_SEP),
    ("gpt-4.1-nano", ChatFamily.IM_SEP),
    ("gpt-4o", ChatFamily.IM_SEP),
    ("gpt-4o-mini", ChatFamily.IM_SEP),
    ("chatgpt-4o-latest", ChatFamily.IM_SEP),
    ("o4-mini", ChatFamily.IM_SEP),
    ("o3-mini", ChatFamily.IM_SEP),
    ("o1", ChatFamily.IM_SEP),
    ("o1-pro", ChatFamily.IM_SEP),
    ("o1-mini", ChatFamily.IM_SEP),
    ("gpt-4-turbo", ChatFamily.IM_SEP),
    ("gpt-4", ChatFamily.IM_SEP),
    ("gpt-4-32k", ChatFamily.IM_SEP),
    ("gpt-3.5-turbo", ChatFamily.IM_SEP),
    ("davinci-002", None),
    ("babbage-002", None),
    # Completion, code, edit and search models exactly as in tiktoken MODEL_TO_ENCODING.
    ("text-davinci-003", None),
    ("text-davinci-002", None),
    ("text-davinci-001", None),
    ("text-curie-001", None),
    ("text-babbage-001", None),
    ("text-ada-001", None),
    ("davinci", None),
    ("curie", None),
    ("babbage", None),
    ("ada", None),
    ("code-davinci-002", None),
    ("code-davinci-001", None),
    ("code-cushman-002", None),
    ("code-cushman-001", None),
    ("davinci-codex", None),
    ("cushman-codex", None),
    ("text-davinci-edit-001", None),
    ("code-davinci-edit-001", None),
    ("text-similarity-davinci-001", None),
    ("text-similarity-curie-001", None),
    ("text-similarity-babbage-001", None),
    ("text-similarity-ada-001", None),
    ("text-search-davinci-doc-001", None),
    ("text-search-curie-doc-001", None),
    ("text-search-babbage-doc-001", None),
    ("text-search-ada-doc-001", None),
    ("code-search-babbage-code-001", None),
    ("code-search-ada-code-001", None),
    # "gpt2" is listed once, as an encoding.
)

DEFAULT_MODEL = "gpt-5.6-sol"
POPULAR: tuple[str, ...] = (
    DEFAULT_MODEL,
    "gpt-5",
    "gpt-4o",
    "o200k_base",
    "cl100k_base",
    "gpt-oss-120b",
)

# Display order for encodings; names tiktoken adds later are appended after these.
_ENCODING_ORDER: tuple[str, ...] = (
    "o200k_base",
    "o200k_harmony",
    "cl100k_base",
    "p50k_base",
    "p50k_edit",
    "r50k_base",
    "gpt2",
)


def tiktoken_encoding_names() -> list[str]:
    """Encodings registered in tiktoken, newest family first."""
    names = tiktoken.list_encoding_names()
    rank = {name: i for i, name in enumerate(_ENCODING_ORDER)}
    return sorted(names, key=lambda n: (rank.get(n, len(rank)), n))


def _model_entries(
    models: tuple[tuple[str, ChatFamily | None], ...], group: Group
) -> list[CatalogueEntry]:
    return [
        CatalogueEntry(
            id=model_id,
            kind="model",
            encoding=tiktoken.encoding_name_for_model(model_id),
            group=group,
            chat_family=family,
            deprecated=group is Group.LEGACY,
        )
        for model_id, family in models
    ]


def _encoding_entries() -> list[CatalogueEntry]:
    entries = [
        CatalogueEntry(id=name, kind="encoding", encoding=name, group=Group.ENCODINGS)
        for name in tiktoken_encoding_names()
    ]
    entries += [
        CatalogueEntry(
            id=variant,
            kind="encoding",
            encoding=variant,
            group=Group.ENCODINGS,
            encoding_source="derived",
        )
        for variant in CHAT_VARIANTS
    ]
    return entries


@cache
def entries() -> tuple[CatalogueEntry, ...]:
    """Every selectable entry, in display order (current, legacy, encodings)."""
    return (
        *_model_entries(CURRENT_MODELS, Group.CURRENT),
        *_model_entries(LEGACY_MODELS, Group.LEGACY),
        *_encoding_entries(),
    )


@cache
def _by_id() -> dict[str, CatalogueEntry]:
    return {e.id: e for e in entries()}


def lookup(name: str) -> CatalogueEntry:
    """Return the entry for a model id or encoding name; raise KeyError when unknown."""
    try:
        return _by_id()[name]
    except KeyError:
        raise KeyError(name) from None


def ids() -> list[str]:
    return [e.id for e in entries()]


def models_using(encoding: str) -> list[str]:
    """Model ids whose tokenizer is ``encoding`` (or its chat variant)."""
    base = CHAT_VARIANTS.get(encoding, encoding)
    return [e.id for e in entries() if e.kind == "model" and e.encoding == base]


def groups() -> list[tuple[Group, list[CatalogueEntry]]]:
    """Entries grouped for the selector, Popular first."""
    popular = [lookup(i) for i in POPULAR]
    grouped: list[tuple[Group, list[CatalogueEntry]]] = [(Group.POPULAR, popular)]
    for group in (Group.CURRENT, Group.LEGACY, Group.ENCODINGS):
        grouped.append((group, [e for e in entries() if e.group is group]))
    return grouped


def print_table() -> None:
    rows = [
        (e.id, e.kind, e.encoding, e.chat_family or "-", GROUP_LABELS[e.group]) for e in entries()
    ]
    header = ("id", "kind", "encoding", "chat", "group")
    widths = [max(len(str(r[i])) for r in (header, *rows)) for i in range(len(header))]
    for row in (header, *rows):
        print("  ".join(str(cell).ljust(w) for cell, w in zip(row, widths, strict=True)))
