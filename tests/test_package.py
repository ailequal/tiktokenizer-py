import tomllib
from pathlib import Path

import tiktokenizer_py


def test_version_comes_from_pyproject() -> None:
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with pyproject.open("rb") as f:
        expected = tomllib.load(f)["project"]["version"]
    assert tiktokenizer_py.__version__ == expected
