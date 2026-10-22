import pytest

from tiktokenizer_py import segments, tokenizers
from tiktokenizer_py.examples import EXAMPLES, INTRO_EXAMPLE_ID, Example
from tiktokenizer_py.glossary import GLOSSARY


def test_examples_have_unique_ids_and_intro_first() -> None:
    assert len(EXAMPLES) == 11
    assert len({e.id for e in EXAMPLES}) == len(EXAMPLES)
    assert EXAMPLES[0].id == INTRO_EXAMPLE_ID


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e.id)
def test_example_is_not_empty(example: Example) -> None:
    assert example.title.strip()
    assert example.text.strip()


@pytest.mark.parametrize("name", tokenizers.all_encoding_names())
@pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e.id)
def test_examples_round_trip(name: str, example: Example) -> None:
    enc = tokenizers.get_encoding(name)
    tokens, segs = segments.tokenize(enc, example.text)
    assert "".join(s.text for s in segs) == enc.decode(tokens)
    assert [t.id for s in segs for t in s.tokens] == tokens


def test_glossary_entries_are_complete() -> None:
    ids = [g.id for g in GLOSSARY]
    assert len(ids) == len(set(ids))
    for entry in GLOSSARY:
        assert entry.id == entry.id.lower()
        assert " " not in entry.id
        assert entry.title.strip()
        assert entry.text.strip()


def test_glossary_covers_required_concepts() -> None:
    required = {
        "token",
        "encoding",
        "special-token",
        "framing",
        "estimate",
        "segment",
        "token-id",
        "grapheme",
        "bpe",
        "billing",
        "chunk",
        "merge",
        "chars-per-token",
        "compare",
        "partial-character",
    }
    assert required <= {g.id for g in GLOSSARY}
