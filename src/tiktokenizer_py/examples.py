"""Ready-made prompts for the examples dropdown; the tests reuse them as fixtures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Example:
    id: str
    title: str
    text: str


# Shown when the page opens: it touches every behaviour worth noticing in one short paragraph.
INTRO_EXAMPLE_ID = "intro"

EXAMPLES: tuple[Example, ...] = (
    Example(
        id=INTRO_EXAMPLE_ID,
        title="How tokens work",
        text=(
            'Tokenizers cut text into pieces called tokens. Common words like "the" are a single '
            'token, rare words like "unbelievably" are built from smaller pieces, numbers such '
            "as 1234567 are split into groups of three digits by newer tokenizers, and an emoji "
            "like 👩‍👦‍👦 needs several tokens."
        ),
    ),
    Example(
        id="english",
        title="English paragraph",
        text=(
            "Tokenizers split text into small pieces called tokens. Common words are usually a "
            "single token, while rare words are split into several pieces. The model never sees "
            "letters, only the numbers that stand for these pieces."
        ),
    ),
    Example(
        id="italian",
        title="Italian with accents",
        text=(
            "Perché la città è così bella? Più ci penso, più mi sembra che l'università, il caffè "
            "e la libertà di passeggiare lì siano già una ragione più che sufficiente. Però può "
            "darsi che io sia di parte."
        ),
    ),
    Example(
        id="python",
        title="Python code",
        text=(
            "def fibonacci(n: int) -> list[int]:\n"
            '    """Return the first n Fibonacci numbers."""\n'
            "    seq = [0, 1]\n"
            "    while len(seq) < n:\n"
            "        seq.append(seq[-1] + seq[-2])\n"
            "    return seq[:n]\n"
        ),
    ),
    Example(
        id="json",
        title="JSON blob",
        text=(
            '{\n  "id": 4021,\n  "name": "Ada Lovelace",\n  "tags": ["math", "computing"],\n'
            '  "active": true,\n  "score": 98.75\n}\n'
        ),
    ),
    Example(id="emoji", title="Emoji and flags", text="👩‍👦‍👦 👩‍👧‍👦 🇨🇿 🇮🇹 🧑🏾‍💻 👍🏽 ❤️‍🔥"),
    Example(
        id="cjk", title="Chinese text", text="是美國一個人工智能研究實驗室 由非營利組織OpenAI Inc"
    ),
    Example(id="tamil", title="Tamil combining marks", text="நடிகர் சூர்யா"),
    Example(
        id="numbers",
        title="Numbers and dates",
        text="Order 1234567 shipped on 2026-10-21 at 14:05. Total: 1,299.99 EUR (+22% VAT).",
    ),
    Example(
        id="special",
        title="Special tokens typed as text",
        text="<|im_start|>test<|im_end|> and <|endoftext|>",
    ),
    Example(
        id="whitespace",
        title="Whitespace torture",
        text="Trailing spaces   \n\n\n\tTabbed line\r\nWindows line end\r\n    four spaces\n",
    ),
)
