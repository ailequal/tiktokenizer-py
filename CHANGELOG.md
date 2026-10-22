# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-22

### Added

- Web page that tokenizes text live with tiktoken and shows the token count, coloured segments and token ids.
- Searchable model selector with Popular, current, legacy and encoding groups, kept in the `?model=` query string.
- Keyboard navigation for the input tabs and the token segments.
- Characters, bytes and characters per token next to the token count.
- Token details for a clicked segment, with each token's bytes and tokens that hold part of a character.
- Whitespace view, a switch that treats special tokens as text, and eleven example prompts.
- "How the tokenizer works" panel with the chunks of the split pattern and a step-by-step merge replay.
- "Compare encodings" panel with token counts and characters per token for every encoding.
- Chat editor with roles and optional names, using the `<|im_start|>` framing for API models (marked as an
  estimate) and Harmony for gpt-oss.
- Decode mode that turns token ids back into text with the bytes of each token.
- Encoding panel with vocabulary size, special tokens, split pattern and the models that use the encoding.
- Context window meter with adjustable room for the reply and a compaction warning.
- Cost estimate from OpenAI's reference prices, with price modes, long-request prices, cache-write prices for newer
  models, editable prices and per request, per day and per month totals.
- Price and context limit snapshot from OpenAI's official pages, refreshed with "Fetch latest prices" or
  `just prices-update`; both keep the current prices when OpenAI's page layout changes.
- "Copy link" to share the model, input and settings, with a warning for very long links, and "Copy ids" to copy the
  token ids.
- Plain-language glossary linked from badges, headings and controls.
- Light and dark themes that follow the system setting or a theme button, and a phone-width layout.
- JSON API: `POST /api/tokenize`, `/api/explain`, `/api/merges`, `/api/compare` and `/api/decode`;
  `GET /api/models`, `/api/encodings`, `/api/encodings/{name}` and `/api/prices`; `POST /api/prices/refresh`;
  and `GET /healthz`.
- Interactive API documentation at `/docs`, served from a vendored copy of Swagger UI so it works offline.
- One JSON error shape and limits of 200,000 characters, 100 messages and 1 MB bodies, configurable with
  `APP_MAX_TEXT_CHARS` and `APP_MAX_BODY_BYTES`.
- `tiktokenizer-py` command line tool and `just tokenize` recipe.
- Production Docker image that runs offline as a non-root user on a read-only root filesystem, for `linux/amd64`
  and `linux/arm64`.
- Compose services for production and development on `localhost` and, with the SparkFabrik HTTP proxy, on
  `tiktokenizer-py.spark.loc`.
- `justfile` recipes for setup, development, quality checks, Docker and price updates.
- README and `GUIDE.md`.

[Unreleased]: https://github.com/ailequal/tiktokenizer-py/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/ailequal/tiktokenizer-py/releases/tag/v1.0.0
