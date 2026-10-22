"""Render chat messages into the text a chat model actually tokenizes.

OpenAI documents the Harmony format used by gpt-oss; names follow its reference renderer
(``openai/harmony``), which writes the role and then ``:name``. The ChatML framing for API models
(``<|im_start|>``, ``<|im_sep|>``, ``<|im_end|>``) is not published. It is chosen so the counts
equal OpenAI's token counting guide: 3 tokens per message, the role, the content, the name plus
one token, and 3 tokens priming the reply. The guide checks those counts against the API for
gpt-3.5-turbo, gpt-4 and gpt-4o; for newer models they remain estimates.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, NamedTuple

from tiktokenizer_py.catalogue import ChatFamily

Role = Literal["system", "developer", "user", "assistant"]
ROLES: tuple[Role, ...] = ("system", "developer", "user", "assistant")


@dataclass(frozen=True, slots=True)
class Message:
    role: Role
    content: str
    name: str = ""


class ChatPart(NamedTuple):
    """A run of rendered text; ``special`` marks a single framing special token."""

    text: str
    special: bool


@dataclass(frozen=True, slots=True)
class RenderedChat:
    parts: tuple[ChatPart, ...]
    is_estimate: bool
    note: str

    @property
    def text(self) -> str:
        return "".join(p.text for p in self.parts)


NOTES: dict[ChatFamily, str] = {
    ChatFamily.IM_SEP: (
        "OpenAI does not publish the chat framing for this model. The <|im_start|>role<|im_sep|>"
        "content<|im_end|> framing used here gives the same counts as OpenAI's token counting "
        "guide, which matches the API for gpt-3.5-turbo, gpt-4 and gpt-4o. Treat it as an "
        "estimate for other models."
    ),
    ChatFamily.HARMONY: (
        "Uses the Harmony format OpenAI documents for gpt-oss. "
        "Assistant turns go on the final channel; system and developer text is used as written."
    ),
}


class _Parts:
    """Collects framing tokens and text, merging neighbouring text runs."""

    def __init__(self) -> None:
        self.items: list[ChatPart] = []

    def special(self, token: str) -> None:
        self.items.append(ChatPart(token, special=True))

    def text(self, text: str, *, separate: bool = False) -> None:
        """Add text; ``separate`` keeps it a part of its own, tokenized on its own."""
        if not text:
            return
        if not separate and self.items and not self.items[-1].special:
            self.items[-1] = ChatPart(self.items[-1].text + text, special=False)
        else:
            self.items.append(ChatPart(text, special=False))


def _header(out: _Parts, m: Message, *, name_with_colon: bool) -> None:
    out.text(m.role)
    if not m.name:
        return
    if name_with_colon:
        # Harmony reference renderer: the role, then ":name" as one more piece of text.
        out.text(f":{m.name}", separate=True)
    else:
        # ChatML: OpenAI counts a name as its own tokens plus one.
        out.text(":", separate=True)
        out.text(m.name, separate=True)


def _render_chatml(messages: Sequence[Message]) -> _Parts:
    out = _Parts()
    for m in messages:
        out.special("<|im_start|>")
        _header(out, m, name_with_colon=False)
        out.special("<|im_sep|>")
        out.text(m.content)
        out.special("<|im_end|>")
    out.special("<|im_start|>")
    out.text("assistant")
    out.special("<|im_sep|>")
    return out


def _render_harmony(messages: Sequence[Message]) -> _Parts:
    out = _Parts()
    for m in messages:
        out.special("<|start|>")
        _header(out, m, name_with_colon=True)
        if m.role == "assistant":
            out.special("<|channel|>")
            out.text("final")
        out.special("<|message|>")
        out.text(m.content)
        out.special("<|end|>")
    out.special("<|start|>")
    out.text("assistant")
    return out


def render(messages: Sequence[Message], family: ChatFamily) -> RenderedChat:
    """Render ``messages`` plus the header that primes the next assistant reply."""
    match family:
        case ChatFamily.IM_SEP:
            parts = _render_chatml(messages)
        case ChatFamily.HARMONY:
            parts = _render_harmony(messages)
    return RenderedChat(
        parts=tuple(parts.items),
        is_estimate=family is not ChatFamily.HARMONY,
        note=NOTES[family],
    )
