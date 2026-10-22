import pytest
import tiktoken

from tiktokenizer_py import catalogue, tokenizers


@pytest.mark.parametrize(
    ("name", "text_encoding", "chat_encoding"),
    [
        ("gpt-4", "cl100k_base", "cl100k_base_chat"),
        ("gpt-3.5-turbo", "cl100k_base", "cl100k_base_chat"),
        ("gpt-5.6-sol", "o200k_base", "o200k_base_chat"),
        ("gpt-oss-20b", "o200k_harmony", "o200k_harmony"),
        ("text-embedding-3-small", "cl100k_base", "cl100k_base"),
        ("davinci", "r50k_base", "r50k_base"),
        ("o200k_base", "o200k_base", "o200k_base"),
        ("cl100k_base_chat", "cl100k_base_chat", "cl100k_base_chat"),
        ("gpt2", "gpt2", "gpt2"),
    ],
)
def test_resolve(name: str, text_encoding: str, chat_encoding: str) -> None:
    assert tokenizers.resolve(name).name == text_encoding
    assert tokenizers.resolve(name, chat=True).name == chat_encoding


def test_text_encoding_is_what_tiktoken_uses() -> None:
    for entry in catalogue.entries():
        if entry.kind == "model":
            assert tokenizers.resolve(entry.id).name == tiktoken.encoding_name_for_model(entry.id)


def test_resolve_unknown_raises() -> None:
    with pytest.raises(KeyError):
        tokenizers.resolve("gpt-6-astra")


@pytest.mark.parametrize(
    ("base", "ids"),
    [("cl100k_base", (100264, 100265, 100266)), ("o200k_base", (200264, 200265, 200266))],
)
def test_chat_variant_special_tokens(base: str, ids: tuple[int, int, int]) -> None:
    enc = tokenizers.chat_variant(base)
    text = "<|im_start|>user<|im_sep|>hi<|im_end|>"
    tokens = enc.encode(text, allowed_special="all")
    assert tokens[0] == ids[0]
    assert ids[2] in tokens
    assert tokens[-1] == ids[1]
    assert enc.decode(tokens) == text


def test_chat_variant_keeps_base_tokens() -> None:
    base = tiktoken.get_encoding("o200k_base")
    variant = tokenizers.chat_variant("o200k_base")
    text = "Hello world, ciao mondo! <|endoftext|>"
    assert variant.encode(text, allowed_special="all") == base.encode(text, allowed_special="all")


def test_chat_variant_is_cached() -> None:
    assert tokenizers.chat_variant("cl100k_base") is tokenizers.chat_variant("cl100k_base")


def test_chat_variant_unknown_base() -> None:
    with pytest.raises(KeyError):
        tokenizers.chat_variant("r50k_base")


def test_every_chatml_model_has_a_variant() -> None:
    for entry in catalogue.entries():
        name = tokenizers.encoding_name_for(entry)
        assert name in tokenizers.all_encoding_names()


def test_warm_up_loads_everything() -> None:
    tokenizers.warm_up()
    for name in tokenizers.all_encoding_names():
        assert tokenizers.get_encoding(name).name == name
