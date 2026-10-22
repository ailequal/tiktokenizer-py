import pytest
import tiktoken
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from tiktokenizer_py import catalogue, chat, explain, segments, tokenizers
from tiktokenizer_py.examples import EXAMPLES
from tiktokenizer_py.main import create_app
from tiktokenizer_py.settings import Settings

ENCODINGS = tokenizers.all_encoding_names()


def flat(chunks: list[explain.Chunk]) -> list[int]:
    return [t for c in chunks for t in c.tokens]


@pytest.mark.parametrize("name", ENCODINGS)
@pytest.mark.parametrize("allow", [True, False])
def test_chunks_reproduce_tiktoken_on_examples(name: str, allow: bool) -> None:
    enc = tokenizers.get_encoding(name)
    for example in EXAMPLES:
        chunks = explain.split_chunks(enc, [(example.text, False)], allow_special=allow)
        assert flat(chunks) == segments.encode(enc, example.text, allow_special=allow)
        assert "".join(c.text for c in chunks) == example.text


@settings(max_examples=200, deadline=None)
@given(text=st.text(), name=st.sampled_from(ENCODINGS), allow=st.booleans())
def test_chunks_reproduce_tiktoken_property(text: str, name: str, allow: bool) -> None:
    enc = tokenizers.get_encoding(name)
    chunks = explain.split_chunks(enc, [(text, False)], allow_special=allow)
    assert flat(chunks) == segments.encode(enc, text, allow_special=allow)


@pytest.mark.parametrize("model", ["gpt-3.5-turbo", "gpt-5", "gpt-oss-20b"])
@pytest.mark.parametrize("allow", [True, False])
def test_chunks_reproduce_chat_tokens(model: str, allow: bool) -> None:
    entry = catalogue.lookup(model)
    assert entry.chat_family is not None
    messages = [chat.Message(role="user", content="Hi <|endoftext|> 👩‍👦‍👦", name="ada")]
    rendered = chat.render(messages, entry.chat_family)
    enc = tokenizers.resolve(model, chat=True)
    chunks = explain.split_chunks(enc, rendered.parts, allow_special=allow)
    assert flat(chunks) == segments.encode_parts(enc, rendered.parts, allow_special=allow)


def test_split_pattern_chunks() -> None:
    enc = tiktoken.get_encoding("o200k_base")
    chunks = explain.split_chunks(
        enc, [("Tokenizers split 12345 words", False)], allow_special=True
    )
    assert [c.text for c in chunks] == ["Tokenizers", " split", " ", "123", "45", " words"]


def test_special_tokens_are_their_own_chunk() -> None:
    enc = tiktoken.get_encoding("cl100k_base")
    chunks = explain.split_chunks(enc, [("a<|endoftext|>b", False)], allow_special=True)
    assert [(c.text, c.special, c.tokens) for c in chunks][1] == ("<|endoftext|>", True, [100257])
    plain = explain.split_chunks(enc, [("a<|endoftext|>b", False)], allow_special=False)
    assert not any(c.special for c in plain)


def test_merge_steps_unbelievably() -> None:
    ranks = tiktoken.get_encoding("o200k_base")._mergeable_ranks
    steps = explain.merge_steps(ranks, b" unbelievably")
    assert len(steps[0].pieces) == 13
    assert steps[0].merged is None
    assert steps[-1].pieces == [b" unbelievably"]
    assert all(s.merged is not None for s in steps[1:])
    # Each step merges exactly one pair.
    assert [len(s.pieces) for s in steps] == list(range(13, 0, -1))


def test_merge_steps_stop_when_no_pair_is_known() -> None:
    steps = explain.merge_steps({b"a": 0, b"b": 1}, b"ab")
    assert len(steps) == 1


# --- API --------------------------------------------------------------------------------


def test_api_explain_text(client: TestClient) -> None:
    res = client.post("/api/explain", json={"model": "gpt-5", "text": "Hi there <|im_start|>"})
    assert res.status_code == 200
    data = res.json()
    assert data["encoding"] == "o200k_base"
    assert data["pattern"] == tiktoken.get_encoding("o200k_base")._pat_str
    enc = tiktoken.encoding_for_model("gpt-5")
    assert [t for c in data["chunks"] for t in c["tokens"]] == enc.encode(
        "Hi there <|im_start|>", allowed_special="all"
    )
    assert data["total_chunks"] == len(data["chunks"])


def test_api_explain_chat(client: TestClient) -> None:
    body = {"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]}
    data = client.post("/api/explain", json=body).json()
    tokens = client.post("/api/tokenize", json=body).json()["tokens"]
    assert data["encoding"] == "cl100k_base_chat"
    assert [t for c in data["chunks"] for t in c["tokens"]] == tokens
    assert data["chunks"][0] == {"text": "<|im_start|>", "special": True, "tokens": [100264]}


def test_api_explain_truncates_chunk_list(client: TestClient) -> None:
    data = client.post("/api/explain", json={"model": "gpt2", "text": "a" + " a" * 449}).json()
    assert data["total_chunks"] == 450
    assert len(data["chunks"]) == 450
    with TestClient(create_app(Settings(max_text_chars=10_000))) as roomy:
        big = roomy.post("/api/explain", json={"model": "gpt2", "text": "a." * 1500}).json()
    assert big["total_chunks"] == 3000
    assert len(big["chunks"]) == explain.MAX_CHUNKS


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({"model": "gpt-6-astra", "text": "x"}, 422, "unknown_model"),
        ({"model": "gpt-5", "text": "a" * 1_001}, 413, "input_too_large"),
        ({"model": "o200k_base", "messages": [{"role": "user"}]}, 422, "not_a_chat_model"),
    ],
)
def test_api_explain_errors(
    client: TestClient, body: dict[str, object], status: int, code: str
) -> None:
    res = client.post("/api/explain", json=body)
    assert res.status_code == status
    assert res.json()["error"]["code"] == code


def test_api_merges(client: TestClient) -> None:
    res = client.post("/api/merges", json={"model": "gpt-5", "chunk": " unbelievably"})
    assert res.status_code == 200
    data = res.json()
    assert data["tokens"] == tiktoken.encoding_for_model("gpt-5").encode(" unbelievably")
    assert len(data["steps"]) == 13
    assert data["steps"][0]["pieces"][0] == {"bytes": "20", "text": " "}
    assert data["steps"][-1]["pieces"] == [
        {"bytes": b" unbelievably".hex(" "), "text": " unbelievably"}
    ]


def test_api_merges_partial_bytes(client: TestClient) -> None:
    data = client.post("/api/merges", json={"model": "cl100k_base", "chunk": "👩"}).json()
    assert [p["text"] for p in data["steps"][0]["pieces"]] == ["�"] * 4
    enc = tiktoken.get_encoding("cl100k_base")
    assert data["tokens"] == enc.encode("👩")


@pytest.mark.parametrize("chunk", ["", "x" * 1_001])
def test_api_merges_rejects_bad_chunks(client: TestClient, chunk: str) -> None:
    res = client.post("/api/merges", json={"model": "gpt-5", "chunk": chunk})
    assert res.status_code == 422


def test_api_compare(client: TestClient) -> None:
    text = "是美國一個人工智能研究實驗室 <|endoftext|>"
    res = client.post("/api/compare", json={"text": text})
    assert res.status_code == 200
    data = res.json()
    assert data["characters"] == len(text)
    assert [r["encoding"] for r in data["rows"]] == catalogue.tiktoken_encoding_names()
    for row in data["rows"]:
        enc = tiktoken.get_encoding(row["encoding"])
        assert row["count"] == len(enc.encode(text, allowed_special="all"))
        assert row["characters_per_token"] == round(len(text) / row["count"], 2)
    plain = client.post("/api/compare", json={"text": text, "allow_special": False}).json()
    assert plain["rows"][0]["count"] > data["rows"][0]["count"]
    by_name = {r["encoding"]: r for r in data["rows"]}
    assert "gpt-5" in by_name["o200k_base"]["models"]


def test_api_compare_empty_and_too_long(client: TestClient) -> None:
    empty = client.post("/api/compare", json={"text": ""}).json()
    assert all(r["count"] == 0 and r["characters_per_token"] is None for r in empty["rows"])
    assert client.post("/api/compare", json={"text": "a" * 1_001}).status_code == 413


def test_tokenize_reports_characters_and_bytes(client: TestClient) -> None:
    data = client.post("/api/tokenize", json={"model": "gpt-5", "text": "è👩"}).json()
    assert data["characters"] == 2
    assert data["bytes"] == 6
    chat_data = client.post(
        "/api/tokenize", json={"model": "gpt-5", "messages": [{"role": "user", "content": "è"}]}
    ).json()
    assert chat_data["characters"] == len(chat_data["rendered_text"])


def test_decode_marks_partial_characters(client: TestClient) -> None:
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode("a👩")
    pieces = client.post("/api/decode", json={"model": "cl100k_base", "tokens": tokens}).json()[
        "pieces"
    ]
    assert pieces[0]["partial"] is False
    assert any(p["partial"] for p in pieces[1:])
