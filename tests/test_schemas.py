import pytest
from pydantic import ValidationError

from tiktokenizer_py.schemas import MAX_MESSAGES, DecodeRequest, TokenizeRequest


def test_text_request() -> None:
    req = TokenizeRequest.model_validate({"model": "gpt-5", "text": "hi"})
    assert req.allow_special is True
    assert req.input_chars() == 2


def test_messages_request() -> None:
    req = TokenizeRequest.model_validate(
        {"model": "gpt-5", "messages": [{"role": "user", "content": "hey", "name": "bo"}]}
    )
    assert req.messages is not None
    assert req.input_chars() == 5


@pytest.mark.parametrize(
    "body",
    [
        {"model": "gpt-5"},
        {"model": "gpt-5", "text": "a", "messages": []},
        {"model": "", "text": "a"},
        {"model": "gpt-5", "text": "a", "unknown": 1},
        {"model": "gpt-5", "messages": [{"role": "robot", "content": "a"}]},
        {"model": "gpt-5", "messages": [{"role": "user"}] * (MAX_MESSAGES + 1)},
    ],
)
def test_invalid_tokenize_requests(body: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        TokenizeRequest.model_validate(body)


def test_decode_rejects_negative_ids() -> None:
    with pytest.raises(ValidationError):
        DecodeRequest.model_validate({"model": "gpt-5", "tokens": [1, -2]})
