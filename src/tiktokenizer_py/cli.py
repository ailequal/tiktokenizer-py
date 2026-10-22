"""Command line tokenizer: ``tiktokenizer-py gpt-5 "hello world"``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from tiktokenizer_py import catalogue, segments, tokenizers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tiktokenizer-py", description="Tokenize text with an OpenAI tokenizer."
    )
    parser.add_argument("model", help="model id or encoding name, e.g. gpt-5 or o200k_base")
    parser.add_argument("text", help='text to tokenize, or "-" to read standard input')
    parser.add_argument(
        "--plain",
        action="store_true",
        help="treat special tokens such as <|endoftext|> as plain text",
    )
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    text: str = sys.stdin.read() if args.text == "-" else args.text
    try:
        enc = tokenizers.resolve(args.model)
    except KeyError:
        print(f"error: unknown model or encoding {args.model!r}", file=sys.stderr)
        print("valid names: " + ", ".join(catalogue.ids()), file=sys.stderr)
        return 2

    tokens, segs = segments.tokenize(enc, text, allow_special=not args.plain)
    if args.json:
        payload = {
            "model": args.model,
            "encoding": enc.name,
            "count": len(tokens),
            "tokens": tokens,
            "segments": [s.text for s in segs],
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"model:    {args.model}")
        print(f"encoding: {enc.name}")
        print(f"count:    {len(tokens)}")
        print(f"tokens:   {tokens}")
        print("segments: " + " | ".join(repr(s.text) for s in segs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
