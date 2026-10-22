import pytest
import tiktoken

from tiktokenizer_py import catalogue
from tiktokenizer_py.catalogue import ChatFamily, Group


@pytest.mark.parametrize("model_id", [e.id for e in catalogue.entries() if e.kind == "model"])
def test_every_model_resolves_through_tiktoken(model_id: str) -> None:
    entry = catalogue.lookup(model_id)
    assert tiktoken.encoding_name_for_model(model_id) == entry.encoding


@pytest.mark.parametrize("model_id", catalogue.KNOWN_UNMAPPED)
def test_known_unmapped_models_still_raise(model_id: str) -> None:
    # When this fails, tiktoken maps the model: add it to CURRENT_MODELS.
    with pytest.raises(KeyError):
        tiktoken.encoding_name_for_model(model_id)
    assert model_id not in catalogue.ids()


def test_every_encoding_is_known() -> None:
    known = set(tiktoken.list_encoding_names()) | set(catalogue.CHAT_VARIANTS)
    for entry in catalogue.entries():
        assert entry.encoding in known


def test_encodings_are_listed_dynamically() -> None:
    listed = [e.id for e in catalogue.entries() if e.group is Group.ENCODINGS]
    assert set(tiktoken.list_encoding_names()) <= set(listed)
    assert listed[0] == "o200k_base"
    assert "o200k_base_chat" in listed
    assert "cl100k_base_chat" in listed


def test_ids_are_unique() -> None:
    ids = catalogue.ids()
    assert len(ids) == len(set(ids))


def test_default_and_popular_exist() -> None:
    assert catalogue.lookup(catalogue.DEFAULT_MODEL).group is Group.CURRENT
    for model_id in catalogue.POPULAR:
        catalogue.lookup(model_id)


def test_groups_order() -> None:
    groups = [g for g, _ in catalogue.groups()]
    assert groups == [Group.POPULAR, Group.CURRENT, Group.LEGACY, Group.ENCODINGS]


def test_lookup_unknown_raises() -> None:
    with pytest.raises(KeyError):
        catalogue.lookup("gpt-unknown")


@pytest.mark.parametrize(
    ("model_id", "family", "encoding"),
    [
        ("gpt-3.5-turbo", ChatFamily.IM_SEP, "cl100k_base"),
        ("gpt-4", ChatFamily.IM_SEP, "cl100k_base"),
        ("gpt-4o", ChatFamily.IM_SEP, "o200k_base"),
        ("gpt-5.6-sol", ChatFamily.IM_SEP, "o200k_base"),
        ("gpt-oss-120b", ChatFamily.HARMONY, "o200k_harmony"),
        ("text-embedding-3-large", None, "cl100k_base"),
        ("text-davinci-edit-001", None, "p50k_edit"),
    ],
)
def test_chat_family_and_encoding(model_id: str, family: ChatFamily | None, encoding: str) -> None:
    entry = catalogue.lookup(model_id)
    assert entry.chat_family == family
    assert entry.encoding == encoding


def test_legacy_models_are_deprecated() -> None:
    for entry in catalogue.entries():
        assert entry.deprecated == (entry.group is Group.LEGACY)


def test_models_using() -> None:
    assert catalogue.models_using("o200k_harmony") == ["gpt-oss-120b", "gpt-oss-20b"]
    assert "gpt-4" in catalogue.models_using("cl100k_base_chat")


def test_print_table(capsys: pytest.CaptureFixture[str]) -> None:
    catalogue.print_table()
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("id")
    assert "gpt-5.6-sol" in out
