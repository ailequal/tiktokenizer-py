"""Download every tiktoken BPE file into TIKTOKEN_CACHE_DIR and build the chat variants.

Run at image build time so the container never needs network access at runtime.
"""

import os
import sys

from tiktokenizer_py import tokenizers


def main() -> int:
    cache_dir = os.environ.get("TIKTOKEN_CACHE_DIR")
    if not cache_dir:
        print("TIKTOKEN_CACHE_DIR is not set; refusing to warm a temporary cache", file=sys.stderr)
        return 1
    print(f"warming tiktoken cache in {cache_dir}")
    for name in tokenizers.all_encoding_names():
        enc = tokenizers.get_encoding(name)
        print(f"  {name:<18} n_vocab={enc.n_vocab}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
