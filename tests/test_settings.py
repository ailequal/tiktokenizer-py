import pytest

from tiktokenizer_py.settings import Settings


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_DATA_DIR", raising=False)
    monkeypatch.setenv("APP_MAX_TEXT_CHARS", "10")
    monkeypatch.setenv("APP_MAX_BODY_BYTES", "2000")
    assert Settings.from_env() == Settings(max_text_chars=10, max_body_bytes=2000)


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_DATA_DIR", raising=False)
    monkeypatch.delenv("APP_MAX_TEXT_CHARS", raising=False)
    monkeypatch.delenv("APP_MAX_BODY_BYTES", raising=False)
    assert Settings.from_env() == Settings(max_text_chars=200_000, max_body_bytes=1_000_000)
