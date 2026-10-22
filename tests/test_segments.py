import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tiktokenizer_py import segments, tokenizers
from tiktokenizer_py.segments import Segment

ENCODINGS = tokenizers.all_encoding_names()

FIXTURES = [
    "Hello world",
    "New lines\n\n\n\n\n       Spaces",
    "👩‍👦‍👦 👩‍👧‍👦 👩‍👧‍👧 👩‍👩‍👦 👩‍👩‍👧 🇨🇿 Emojis: 🧑🏾‍💻️🧑🏿‍🎓️🧑🏿‍🏭️🧑🏿‍💻️",
    "是美國一個人工智能研究實驗室 由非營利組織OpenAI Inc",
    "<|im_start|>test<|im_end|>",
    "நடிகர் சூர்யா",
    " Ġ除",
    "Windows\r\nline\r\nendings\tand tabs",
    "",
]


def check_invariants(name: str, text: str, allow_special: bool = True) -> list[Segment]:
    enc = tokenizers.get_encoding(name)
    tokens, segs = segments.tokenize(enc, text, allow_special=allow_special)
    assert "".join(s.text for s in segs) == enc.decode(tokens)
    assert [t.id for s in segs for t in s.tokens] == tokens
    assert [t.idx for s in segs for t in s.tokens] == list(range(len(tokens)))
    return segs


@pytest.mark.parametrize("name", ENCODINGS)
@pytest.mark.parametrize("text", FIXTURES)
def test_segment_invariants(name: str, text: str) -> None:
    check_invariants(name, text)
    check_invariants(name, text, allow_special=False)


@pytest.mark.parametrize("name", ["cl100k_base", "o200k_base", "o200k_base_chat"])
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "👩‍👦‍👦 👩‍👧‍👦 👩‍👧‍👧 👩‍👩‍👦 👩‍👩‍👧 🇨🇿",
            ["👩‍👦‍👦", " 👩‍👧‍👦", " 👩‍👧‍👧", " 👩‍👩‍👦", " 👩‍👩‍👧", " 🇨🇿"],
        ),
        ("由非營利組織", ["由", "非", "營", "利", "組", "織"]),
    ],
)
def test_grapheme_segments(name: str, text: str, expected: list[str]) -> None:
    enc = tokenizers.get_encoding(name)
    _, segs = segments.tokenize(enc, text)
    texts = [s.text for s in segs]
    if name == "cl100k_base":
        assert texts == expected
    # Whatever the tokenizer, no segment may cut a grapheme in half.
    joined = "".join(texts)
    assert joined == text
    for seg in segs:
        assert "�" not in seg.text


def test_special_tokens_are_flagged() -> None:
    enc = tokenizers.get_encoding("o200k_base_chat")
    _, segs = segments.tokenize(enc, "<|im_start|>test<|im_end|>")
    assert [(s.text, s.special) for s in segs] == [
        ("<|im_start|>", True),
        ("test", False),
        ("<|im_end|>", True),
    ]
    assert segs[0].tokens[0].id == 200264


def test_special_tokens_as_plain_text() -> None:
    enc = tokenizers.get_encoding("cl100k_base")
    special, _ = segments.tokenize(enc, "<|endoftext|>")
    plain, segs = segments.tokenize(enc, "<|endoftext|>", allow_special=False)
    assert special == [100257]
    assert len(plain) > 1
    assert not any(s.special for s in segs)


def test_lone_surrogate_keeps_every_token() -> None:
    enc = tokenizers.get_encoding("cl100k_base")
    tokens, segs = segments.tokenize(enc, "a\ud800b")
    assert [t.id for s in segs for t in s.tokens] == tokens
    assert "".join(s.text for s in segs) == "a�b"


@settings(max_examples=200, deadline=None)
@given(text=st.text(), name=st.sampled_from(ENCODINGS))
def test_segment_invariants_property(text: str, name: str) -> None:
    check_invariants(name, text)
