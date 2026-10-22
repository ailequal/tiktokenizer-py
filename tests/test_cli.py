import io
import json

import pytest

from tiktokenizer_py import cli


def test_cli_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["o200k_base", "hello world"]) == 0
    out = capsys.readouterr().out
    assert "encoding: o200k_base" in out
    assert "count:    2" in out


def test_cli_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["cl100k_base", "<|endoftext|>", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tokens"] == [100257]


def test_cli_plain(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["cl100k_base", "<|endoftext|>", "--json", "--plain"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] > 1


def test_cli_stdin(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("ciao"))
    assert cli.main(["gpt-5", "-", "--json"]) == 0
    assert "".join(json.loads(capsys.readouterr().out)["segments"]) == "ciao"


def test_cli_unknown_model(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["gpt-6-astra", "hi"]) == 2
    assert "unknown model" in capsys.readouterr().err
