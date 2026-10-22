import tiktoken
from fastapi.testclient import TestClient

from tiktokenizer_py import tokenizers


def test_healthz(client: TestClient) -> None:
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_tokenize_text(client: TestClient) -> None:
    text = "hello world <|endoftext|> 👩‍👦‍👦"
    res = client.post("/api/tokenize", json={"model": "o200k_base", "text": text})
    assert res.status_code == 200
    data = res.json()
    enc = tiktoken.get_encoding("o200k_base")
    assert data["count"] == len(enc.encode(text, allowed_special="all"))
    assert data["tokens"] == enc.encode(text, allowed_special="all")
    assert data["encoding"] == "o200k_base"
    assert data["is_estimate"] is False
    assert data["rendered_text"] is None
    assert "".join(s["text"] for s in data["segments"]) == text
    assert any(s["special"] for s in data["segments"])


def test_tokenize_text_with_chat_model_uses_tiktoken_encoding(client: TestClient) -> None:
    # Plain text must match tiktoken exactly: <|im_start|> is not a special token of o200k_base.
    res = client.post("/api/tokenize", json={"model": "gpt-5", "text": "<|im_start|>"})
    data = res.json()
    enc = tiktoken.encoding_for_model("gpt-5")
    assert data["encoding"] == "o200k_base"
    assert data["tokens"] == enc.encode("<|im_start|>", allowed_special="all")
    assert len(data["tokens"]) > 1


def test_every_model_text_matches_tiktoken(client: TestClient) -> None:
    from tiktokenizer_py import catalogue

    text = "Hi <|endoftext|> <|im_start|> 👩‍👦‍👦"
    for entry in catalogue.entries():
        if entry.kind != "model":
            continue
        enc = tiktoken.encoding_for_model(entry.id)
        data = client.post("/api/tokenize", json={"model": entry.id, "text": text}).json()
        assert data["tokens"] == enc.encode(text, allowed_special="all"), entry.id


def test_tokenize_plain_special(client: TestClient) -> None:
    res = client.post(
        "/api/tokenize",
        json={"model": "cl100k_base", "text": "<|endoftext|>", "allow_special": False},
    )
    data = res.json()
    assert data["count"] == len(
        tiktoken.get_encoding("cl100k_base").encode_ordinary("<|endoftext|>")
    )
    assert not any(s["special"] for s in data["segments"])


def test_tokenize_chat(client: TestClient) -> None:
    body = {
        "model": "gpt-5.6-sol",
        "messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
        ],
    }
    res = client.post("/api/tokenize", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["rendered_text"] == (
        "<|im_start|>system<|im_sep|>You are helpful.<|im_end|>"
        "<|im_start|>user<|im_sep|>Hi<|im_end|><|im_start|>assistant<|im_sep|>"
    )
    assert data["is_estimate"] is True
    assert data["note"]
    enc = tokenizers.resolve("gpt-5.6-sol", chat=True)
    assert data["encoding"] == "o200k_base_chat"
    assert data["tokens"] == enc.encode(data["rendered_text"], allowed_special="all")


def test_tokenize_chat_harmony_is_not_estimate(client: TestClient) -> None:
    body = {"model": "gpt-oss-120b", "messages": [{"role": "user", "content": "Hi"}]}
    data = client.post("/api/tokenize", json=body).json()
    assert data["encoding"] == "o200k_harmony"
    assert data["is_estimate"] is False
    assert data["tokens"][0] == 200006


def test_tokenize_chat_on_non_chat_model(client: TestClient) -> None:
    body = {"model": "text-embedding-3-small", "messages": [{"role": "user", "content": "Hi"}]}
    assert client.post("/api/tokenize", json=body).status_code == 422


def test_unknown_model(client: TestClient) -> None:
    res = client.post("/api/tokenize", json={"model": "gpt-6-astra", "text": "hi"})
    assert res.status_code == 422


def test_oversized_text(client: TestClient) -> None:
    res = client.post("/api/tokenize", json={"model": "gpt-5", "text": "a" * 1_001})
    assert res.status_code == 413


def test_oversized_chat(client: TestClient) -> None:
    messages = [{"role": "user", "content": "a" * 600}] * 2
    res = client.post("/api/tokenize", json={"model": "gpt-5", "messages": messages})
    assert res.status_code == 413


def test_decode(client: TestClient) -> None:
    enc = tiktoken.get_encoding("o200k_base")
    tokens = enc.encode("ciao 👩‍👦‍👦<|endoftext|>", allowed_special="all")
    res = client.post("/api/decode", json={"model": "o200k_base", "tokens": tokens})
    assert res.status_code == 200
    data = res.json()
    assert data["text"] == "ciao 👩‍👦‍👦<|endoftext|>"
    assert [p["id"] for p in data["pieces"]] == tokens
    assert data["pieces"][-1]["special"] is True
    assert data["pieces"][0]["bytes"] == enc.decode_single_token_bytes(tokens[0]).hex(" ")
    assert any("�" in p["text"] for p in data["pieces"])


def test_decode_chat_framing_ids(client: TestClient) -> None:
    res = client.post("/api/decode", json={"model": "gpt-4", "tokens": [100264, 882, 100266]})
    assert res.json()["text"] == "<|im_start|>user<|im_sep|>"


def test_decode_rejects_ids_beyond_32_bits(client: TestClient) -> None:
    res = client.post("/api/decode", json={"model": "gpt-5", "tokens": [2**40]})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


def test_decode_invalid_ids(client: TestClient) -> None:
    res = client.post("/api/decode", json={"model": "gpt2", "tokens": [1, 999_999]})
    assert res.status_code == 422
    assert "999999" in res.text


def test_models(client: TestClient) -> None:
    data = client.get("/api/models").json()
    assert data["default"] == "gpt-5.6-sol"
    assert [g["id"] for g in data["groups"]] == ["popular", "current", "legacy", "encodings"]
    by_id = {m["id"]: m for m in data["models"]}
    assert by_id["gpt-4"]["encoding"] == "cl100k_base_chat"
    assert by_id["gpt-4"]["base_encoding"] == "cl100k_base"
    assert by_id["gpt-oss-20b"]["chat_family"] == "harmony"
    assert by_id["o200k_base"]["is_chat"] is False


def test_encodings(client: TestClient) -> None:
    data = client.get("/api/encodings").json()
    names = [e["name"] for e in data]
    assert set(tiktoken.list_encoding_names()) <= set(names)
    assert {"cl100k_base_chat", "o200k_base_chat"} <= set(names)


def test_encoding_info_harmony_collapses_reserved(client: TestClient) -> None:
    data = client.get("/api/encodings/o200k_harmony").json()
    assert data["n_vocab"] == 201088
    assert data["special_tokens"]["<|start|>"] == 200006
    assert not any(k.startswith("<|reserved_") for k in data["special_tokens"])
    assert data["reserved_tokens"]["last"] == 201087
    assert data["models"] == ["gpt-oss-120b", "gpt-oss-20b"]
    assert data["pat_str"]


def test_encoding_info_chat_variant(client: TestClient) -> None:
    data = client.get("/api/encodings/cl100k_base_chat").json()
    assert data["source"] == "derived"
    assert data["base"] == "cl100k_base"
    assert data["special_tokens"]["<|im_start|>"] == 100264
    assert data["eot_token"] == 100257
    assert data["reserved_tokens"] is None


def test_encoding_info_unknown(client: TestClient) -> None:
    assert client.get("/api/encodings/nope").status_code == 404


def test_error_shape_unknown_model(client: TestClient) -> None:
    res = client.post("/api/tokenize", json={"model": "gpt-6-astra", "text": "hi"})
    assert res.status_code == 422
    error = res.json()["error"]
    assert error["code"] == "unknown_model"
    assert "gpt-6-astra" in error["message"]
    assert "gpt-5.6-sol" in error["details"]["valid"]


def test_error_shape_validation(client: TestClient) -> None:
    res = client.post("/api/tokenize", json={"model": "gpt-5"})
    assert res.status_code == 422
    error = res.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"].startswith("Provide exactly one")
    assert isinstance(error["details"], list)


def test_error_shape_invalid_json(client: TestClient) -> None:
    res = client.post(
        "/api/tokenize", content=b"not json", headers={"content-type": "application/json"}
    )
    assert res.status_code == 422
    error = res.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"] == "The request body is not valid JSON"


def test_error_shape_too_large(client: TestClient) -> None:
    res = client.post("/api/tokenize", json={"model": "gpt-5", "text": "a" * 1_001})
    assert res.json()["error"] == {
        "code": "input_too_large",
        "message": "Input is 1,001 characters, longer than the limit of 1,000.",
        "details": {"limit": 1000, "length": 1001},
    }


def test_body_limit_with_content_length(client: TestClient) -> None:
    res = client.post("/api/tokenize", json={"model": "gpt-5", "text": "a" * 20_000})
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "body_too_large"


def test_body_limit_chunked(client: TestClient) -> None:
    def chunks() -> object:
        yield b'{"model": "gpt-5", "text": "'
        for _ in range(20):
            yield b"a" * 1_000
        yield b'"}'

    res = client.post(
        "/api/tokenize", content=chunks(), headers={"content-type": "application/json"}
    )
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "body_too_large"


def test_not_found_shape(client: TestClient) -> None:
    res = client.get("/api/nothing")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_openapi_documents_errors(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    responses = spec["paths"]["/api/tokenize"]["post"]["responses"]
    assert {"200", "413", "422"} <= set(responses)


def test_lone_surrogates_are_replaced(client: TestClient) -> None:
    body = '{"model": "gpt-5", "messages": [{"role": "user", "content": "a\\ud800b"}]}'
    res = client.post("/api/tokenize", content=body, headers={"content-type": "application/json"})
    assert res.status_code == 200
    assert "a�b" in res.json()["rendered_text"]
