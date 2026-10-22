import pytest

from tiktokenizer_py import catalogue, chat, segments, tokenizers
from tiktokenizer_py.catalogue import ChatFamily
from tiktokenizer_py.chat import Message

MESSAGES = [
    Message(role="system", content="You are helpful."),
    Message(role="user", content="Hi", name="elia"),
]


def test_im_sep_golden() -> None:
    rendered = chat.render(MESSAGES, ChatFamily.IM_SEP)
    assert rendered.text == (
        "<|im_start|>system<|im_sep|>You are helpful.<|im_end|>"
        "<|im_start|>user:elia<|im_sep|>Hi<|im_end|>"
        "<|im_start|>assistant<|im_sep|>"
    )
    assert rendered.is_estimate


def test_harmony_golden() -> None:
    messages = [*MESSAGES, Message(role="assistant", content="Hello!")]
    rendered = chat.render(messages, ChatFamily.HARMONY)
    assert rendered.text == (
        "<|start|>system<|message|>You are helpful.<|end|>"
        "<|start|>user:elia<|message|>Hi<|end|>"
        "<|start|>assistant<|channel|>final<|message|>Hello!<|end|>"
        "<|start|>assistant"
    )
    assert not rendered.is_estimate


@pytest.mark.parametrize("family", list(ChatFamily))
def test_empty_conversation_primes_assistant(family: ChatFamily) -> None:
    text = chat.render([], family).text
    assert text.startswith(("<|im_start|>assistant", "<|start|>assistant"))


@pytest.mark.parametrize("family", list(ChatFamily))
def test_every_family_has_a_note(family: ChatFamily) -> None:
    assert chat.render(MESSAGES, family).note


@pytest.mark.parametrize(
    ("model", "start_id", "sep_id"),
    [("gpt-4", 100264, 100266), ("gpt-5", 200264, 200266), ("gpt-oss-120b", 200006, 200008)],
)
def test_framing_tokens_are_single_special_tokens(model: str, start_id: int, sep_id: int) -> None:
    entry = catalogue.lookup(model)
    assert entry.chat_family is not None
    rendered = chat.render(MESSAGES, entry.chat_family)
    tokens, segs = segments.tokenize(tokenizers.resolve(model, chat=True), rendered.text)
    assert tokens[0] == start_id
    assert sep_id in tokens
    assert segs[0].special


@pytest.mark.parametrize("model", ["gpt-3.5-turbo", "gpt-4o", "gpt-5", "gpt-oss-20b"])
def test_encode_parts_matches_full_encode_without_names(model: str) -> None:
    entry = catalogue.lookup(model)
    assert entry.chat_family is not None
    messages = [MESSAGES[0], Message(role="assistant", content="Sure 👩‍👦‍👦\n\n  ok")]
    rendered = chat.render(messages, entry.chat_family)
    enc = tokenizers.resolve(model, chat=True)
    assert segments.encode_parts(enc, rendered.parts) == enc.encode(
        rendered.text, allowed_special="all"
    )


# The example conversation and the prompt_tokens OpenAI's API returned for it, from the token
# counting guide: https://developers.openai.com/cookbook/examples/how_to_count_tokens_with_tiktoken
COOKBOOK_MESSAGES = [
    Message(
        role="system",
        content="You are a helpful, pattern-following assistant that translates corporate "
        "jargon into plain English.",
    ),
    Message(
        role="system", name="example_user", content="New synergies will help drive top-line growth."
    ),
    Message(
        role="system",
        name="example_assistant",
        content="Things working well together will increase revenue.",
    ),
    Message(
        role="system",
        name="example_user",
        content="Let's circle back when we have more bandwidth to touch base on opportunities "
        "for increased leverage.",
    ),
    Message(
        role="system",
        name="example_assistant",
        content="Let's talk later when we're less busy about how to do better.",
    ),
    Message(
        role="user",
        content="This late pivot means we don't have time to boil the ocean for the client "
        "deliverable.",
    ),
]


@pytest.mark.parametrize(
    ("model", "api_prompt_tokens"),
    [("gpt-3.5-turbo", 129), ("gpt-4", 129), ("gpt-4o", 124), ("gpt-4o-mini", 124)],
)
def test_chat_counts_match_openai_api(model: str, api_prompt_tokens: int) -> None:
    entry = catalogue.lookup(model)
    assert entry.chat_family is ChatFamily.IM_SEP
    rendered = chat.render(COOKBOOK_MESSAGES, entry.chat_family)
    tokens = segments.encode_parts(tokenizers.resolve(model, chat=True), rendered.parts)
    assert len(tokens) == api_prompt_tokens


def test_name_is_its_tokens_plus_one() -> None:
    enc = tokenizers.resolve("gpt-4o", chat=True)
    plain = chat.render([Message(role="user", content="Hi")], ChatFamily.IM_SEP)
    named = chat.render(
        [Message(role="user", content="Hi", name="example_user")], ChatFamily.IM_SEP
    )
    extra = len(segments.encode_parts(enc, named.parts)) - len(
        segments.encode_parts(enc, plain.parts)
    )
    assert extra == len(enc.encode("example_user")) + 1


def test_harmony_name_follows_reference_renderer() -> None:
    rendered = chat.render([Message(role="user", content="Hi", name="ada")], ChatFamily.HARMONY)
    assert [p.text for p in rendered.parts][:3] == ["<|start|>", "user", ":ada"]


def test_encode_parts_plain_content_keeps_framing() -> None:
    enc = tokenizers.resolve("gpt-5", chat=True)
    messages = [Message(role="user", content="<|endoftext|>")]
    rendered = chat.render(messages, ChatFamily.IM_SEP)
    tokens = segments.encode_parts(enc, rendered.parts, allow_special=False)
    assert tokens[0] == 200264
    assert 199999 not in tokens
    assert enc.decode(tokens) == rendered.text


def test_parts_merge_text_runs() -> None:
    rendered = chat.render([Message(role="assistant", content="hi")], ChatFamily.HARMONY)
    texts = [p.text for p in rendered.parts]
    assert texts[:6] == ["<|start|>", "assistant", "<|channel|>", "final", "<|message|>", "hi"]
