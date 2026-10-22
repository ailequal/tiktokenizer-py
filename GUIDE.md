# tiktokenizer-py guide

This guide explains what tiktokenizer-py does and how to use every part of it, in the order you meet them on the
page. For installation, see the [README](README.md#quick-start).

## Tokens in one minute

Language models do not read letters. A tokenizer first cuts the text into pieces called tokens and gives each piece
a number, its token id. The model only ever sees those numbers.

The number of tokens matters for two reasons. Every model can handle only a limited number at once (its context
window), and the OpenAI API bills per token. A common English word is usually one token; rare words, numbers,
other languages and emoji often take several.

Each OpenAI model family uses an encoding: a vocabulary of known pieces plus the rules for cutting text. Newer
encodings such as `o200k_base` have bigger vocabularies and usually need fewer tokens than older ones such as
`cl100k_base` or `gpt2`.

## Starting the app

Run `just setup` once, then `just up`, and open <http://localhost:8000>. The page opens with a short example text
that shows the most interesting cases: common words, a rare word, a long number and an emoji.

## The page at a glance

- **Header:** the model selector on the right and the "What am I looking at?" button, which opens the glossary.
- **Left column:** the input (Text, Chat or Decode), the example menu, and two panels: "How the tokenizer works"
  and "Compare encodings".
- **Right column:** the token count, the context window meter, the text split into tokens, the token ids, the cost
  estimate and the encoding details.

Every result updates as you type. Labels with a dotted underline open the matching glossary entry.

## Choosing a model

Click the model selector to open a searchable list with four groups:

- **Popular:** the most used choices.
- **OpenAI models:** current models, newest first.
- **Legacy OpenAI models:** older and deprecated models that tiktoken still knows.
- **OpenAI encodings:** the encodings themselves, for when you care about the tokenizer rather than a model.

Type to filter the list, use the arrow keys to move and Enter to choose, or click an entry. Escape closes the
list. The small text next to each model is the encoding it uses.

The chosen model is kept in the address bar (`?model=gpt-5`), so a bookmark or a copied address opens the same
model. A model is only listed once tiktoken knows which encoding it uses; the encoding always comes from tiktoken.

## Counting text

The **Text** tab is the default. Type or paste into the box and the right column shows:

- **The token count**, with an `exact` badge. Plain-text counts are exactly what tiktoken returns for the model.
- **Characters, bytes and characters per token.** English prose is usually around four characters per token; code,
  emoji and many other languages are lower. Bytes are counted in UTF-8, where accented letters, most non-Latin
  scripts and emoji take more than one byte.

### Text split into tokens

The text is shown again as coloured blocks called segments. A segment is usually one token. When one character
needs several tokens, as many emoji do, those tokens are shown together as one segment so no character is cut in
half. A dashed border marks a special token.

- **Hover a segment** to highlight its ids and to show its spaces and line breaks.
- **Click a segment** to list its tokens with their ids, their bytes in hexadecimal and their text. A token that
  holds only part of a character is marked "part of a character". Click the segment again, or Close, to hide the
  list.
- **Show whitespace** draws every space as `⋅`, every tab as `→` and every line break as `\n`.
- **With the keyboard,** Tab into the segments, move between them with the arrow keys, Home and End, and press
  Enter or Space to open the token list. The Text, Chat and Decode tabs also switch with the arrow keys.

Very long inputs show the first 5,000 segments to keep the page responsive; the count still covers everything, and
"Show all" renders the rest.

### Token ids

The token ids are listed in order. Hovering an id highlights its segment, and clicking it selects the segment.
"Copy ids" copies all ids as a JSON array, ready to paste into Decode or into code.

### Special tokens

Sequences such as `<|endoftext|>` are special tokens: markers that stand for structure rather than text. By default,
typing one produces the special token, a single id. Tick **Treat special tokens as text** to tokenize them as
ordinary characters instead. That is how the OpenAI API treats the text you send it.

### Examples

The **Load an example** menu fills the input with ready-made texts: English, Italian with accents, Python code,
JSON, emoji and flags, Chinese, Tamil, numbers and dates, special tokens and whitespace edge cases. In the Chat tab,
the example goes into the last user message.

## How the tokenizer works

This panel shows the two stages of tokenizing, applied to your text.

1. **Split the text into chunks.** A pattern cuts the text into words (each with the space before it), numbers,
   punctuation and whitespace. In the newer encodings a number chunk holds at most three digits. A token never
   crosses a chunk border. Each chunk shows how many tokens it becomes; the list shows the first 2,000 chunks.
2. **Merge bytes into tokens.** Click a chunk to replay its merges. The chunk starts as single bytes. At each step
   the neighbouring pair that comes first in the encoding's merge list is joined, highlighted in the replay, until
   no known pair is left. Chunks longer than 120 bytes are too long to replay and show only their tokens; a special
   token skips merging.
3. **Look up the ids.** Every remaining piece is in the vocabulary, and its rank in the merge list is its token id.
   The last row of the replay shows each piece with its id.

The panel picks the longest plain word to start with, because it has the most merges to watch. Collapse the panel
when you do not need it; it then stops updating.

## Comparing encodings

The **Compare encodings** panel tokenizes the same text with every OpenAI encoding, newest family first. Each row
shows the token count as a bar, the characters per token and the models that use the encoding. Click an encoding
name to switch to it.

Newer encodings usually need fewer tokens, especially for languages other than English and for code. The panel is
available in the Text tab.

## Counting a conversation

Chat models do not read a list of messages directly. Each message is wrapped in special tokens that mark who is
speaking, and everything is joined into one text before tokenizing. This wrapping is the chat framing.

The **Chat** tab appears for chat models. Moving from an encoding or a non-chat model to a chat model while the text
box is empty opens it directly.

- **Messages:** each row has a role (system, developer, user or assistant) and the content. "Add message" adds a row
  with the role that usually comes next; "Remove" deletes a row. A conversation can have up to 100 messages.
- **Names:** "Add name" gives a message an optional author name of up to 64 characters, for example to tell two
  users apart. The name is added after the role, as `role:name`.
- **The result:** the right column shows the framed text split into tokens, so you can see every framing token.

There are two framings:

- **OpenAI API models** use `<|im_start|>role<|im_sep|>content<|im_end|>` for each message, followed by
  `<|im_start|>assistant<|im_sep|>`, which primes the reply. OpenAI does not publish the framing for these models,
  so the count carries an `estimate` badge. It matches the API-verified numbers in OpenAI's
  [token counting guide](https://developers.openai.com/cookbook/examples/how_to_count_tokens_with_tiktoken).
- **gpt-oss models** use the Harmony format that OpenAI documents. The page renders it exactly as OpenAI's reference
  renderer does, so the count is `exact`. System and developer messages are used as written; assistant messages go
  on the final channel.

## Decoding token ids

The **Decode** tab turns token ids back into text. Paste ids separated by commas, spaces, semicolons or new lines;
square brackets are fine too, so a JSON array works. When you switch to Decode with an empty box, it is filled with
the ids of the current text.

The page shows the decoded text and a table with each token's id, bytes and text, marking special tokens and
tokens that hold only part of a character. Ids are decoded with the model's chat encoding, so the framing tokens
of a chat decode too. Unknown ids or anything that is not a whole number produce an error message.

## Encoding details

The **About the encoding** panel, at the bottom of the right column, describes the encoding in use: vocabulary
size, end-of-text token, every special token with its id, the split pattern and the models that use it. The
reserved tokens of `o200k_harmony` are summarized in one line instead of listed one by one.

In the Text tab the panel shows the model's plain encoding; in Chat and Decode it shows the chat variant, which adds
the framing tokens.

## The context window meter

The bar under the token count shows how much of the model's input room the current text uses. It appears for
models whose limits OpenAI publishes.

- **Usable input** is the model's maximum input, or its context window minus the room kept for the reply, whichever
  is smaller.
- **Room for the reply** defaults to 25,000 tokens, capped at the model's maximum output and at half its context
  window, so models with small windows still leave room for input. Hidden reasoning also counts as reply.
- **Warnings:** the bar turns amber at the compaction threshold (80% by default) and red when the text no longer
  fits. Compacting means replacing older messages with a short summary so a long conversation keeps working.

Click **Adjust** to change the room kept for the reply and the warning threshold. The text under the bar lists the
model's context window, maximum input and maximum output.

## The cost estimate

The **Cost estimate** panel gives a rough cost in US dollars, based on OpenAI's reference prices per million
tokens. It appears for models; encodings have no price.

- **Price mode:** Standard is the default. Batch runs jobs within 24 hours at half price. Flex answers more slowly
  for less. Fast answers sooner for more. Only the modes the model offers are listed.
- **Long requests:** some models charge more when a request has more than 272,000 input tokens. For those models
  the price table has a second row, and the estimate uses it for the whole request once the input passes that size.
- **Prices:** every price in the table can be edited. A changed price shows its reference value below it; "Reset to
  reference prices" restores them. Custom prices are remembered in your browser, per model and price mode.
- **Inputs:** input tokens per request follow the page's token count until you type a number, and a link switches
  back. You also set the expected output tokens (default 1,000), the cached share of the input (default 0%) and the
  requests per day (default 1).
- **Cache writes:** newer models (gpt-5.6 and later) also charge for writing input to the cache, at a higher price
  for a 12-hour lifetime than for a 30-minute one. For those models the table shows both write prices, and you pick
  the lifetime and how many cache writes happen per day (default 1). Each write stores the cached part of the input
  at the write price instead of reading it at the cached price, so it adds to the daily cost.
- **Totals:** the cost per request, per day and per month (30 days), with the calculation behind each line. Per
  request shows a request that reads the cache; cache writes are added per day.

Output includes hidden reasoning, which OpenAI bills as output, so include it in the expected output.

### Where the prices come from

The prices and context limits come only from OpenAI's official documentation: the pricing page and one page per
model. A snapshot ships with the app and works offline; the line above the table shows its date.

**Fetch latest prices** downloads the pages again on the server, checks that their layout still matches what the
parser expects, and only then replaces the prices and lists how many changed. If anything does not match, the
current prices stay and the page lists the problems. After a successful fetch the button waits 10 minutes before it
works again, after a failed one 30 seconds. Fetched prices are saved in `APP_DATA_DIR` and survive restarts.

A few models need hand-kept corrections, for example aliases that OpenAI prices under a dated name (`gpt-4` as
`gpt-4-0613`) and models OpenAI no longer prices. Those models show a short note instead of, or next to, the
prices.

## Sharing and copying

- **Copy link** copies an address that reopens the page with the same model, tab, input, special-token setting,
  meter settings and cost settings, including custom prices. The input travels in the part of the address after
  `#`, compressed, which browsers never send to a server. Settings from a link apply to that view only and are saved
  in the browser only once you change them.
- **Copy ids** copies the token ids as a JSON array.

When the browser blocks copying, the link appears in a field so you can copy it by hand. Links longer than 8,000
characters come with a warning, because some apps and servers cut them; for long inputs, share the text itself. A
damaged link opens the page with the example text and says so.

## The glossary

"What am I looking at?" opens a panel with plain-language explanations of every term on the page: tokens,
encodings, segments, chunks, merges, special tokens, chat framing, the context window, price modes and more. Every
underlined label and every badge opens it at the matching entry. Escape, Close or a click outside closes it.

## What the browser remembers

The page saves three things in your browser's local storage: custom prices, the meter and cost settings (room for
the reply, warning threshold, output tokens, cached share, requests per day, cache lifetime and writes, price mode),
and the theme you picked. Nothing else is stored.
What you type is sent only to your own tiktokenizer-py server. In a private window the page works the same but
forgets these settings.

The **Theme** button in the header switches between Auto (follow the system setting), Light and Dark. The page also
works at phone width.

## The command line tool

The package installs a `tiktokenizer-py` command, also available as `just tokenize`:

```sh
just tokenize gpt-5 "hello world"            # model, encoding, count, ids and segments
just tokenize gpt-5 "hello world" --json     # the same as JSON
just tokenize gpt-5 "<|endoftext|>" --plain  # treat special tokens as text
echo "hello" | uv run tiktokenizer-py gpt-5 -   # read the text from standard input
```

An unknown model prints the list of valid names and exits with status 2.

## The JSON API

The page talks to the server through a JSON API that you can call yourself. Interactive documentation with every
schema is at `/docs`; it is served by the app itself, so it works offline too.

| Endpoint                    | Body or parameters                             | Returns                                      |
| --------------------------- | ---------------------------------------------- | -------------------------------------------- |
| `POST /api/tokenize`        | `model`, `text` or `messages`, `allow_special` | Count, ids, segments, characters and bytes   |
| `POST /api/explain`         | Same as tokenize                               | Split pattern, chunks and the tokens of each |
| `POST /api/merges`          | `model`, `chunk` (up to 1,000 characters)      | Every merge step and the final tokens        |
| `POST /api/compare`         | `text`, `allow_special`                        | Count and characters per token per encoding  |
| `POST /api/decode`          | `model`, `tokens` (up to 200,000 ids)          | Text and each token's bytes                  |
| `GET /api/models`           |                                                | Catalogue groups and every model's encoding  |
| `GET /api/encodings`        |                                                | Every encoding with its vocabulary size      |
| `GET /api/encodings/{name}` | Encoding name in the path                      | Special tokens, split pattern and models     |
| `GET /api/prices`           |                                                | Prices, context limits, date and origin      |
| `POST /api/prices/refresh`  |                                                | New prices and the list of changes           |
| `GET /healthz`              |                                                | `{"status": "ok"}`                           |

Notes on the requests:

- **`text` or `messages`:** send exactly one. A message has `role` (`system`, `developer`, `user` or `assistant`),
  `content` and an optional `name`. Messages work only for chat models.
- **`allow_special`** defaults to `true`, so `<|endoftext|>` in the text becomes a special token. Set it to `false`
  to tokenize such sequences as plain text.
- **Limits:** 200,000 characters of input (text or all messages together), 100 messages and a 1 MB request body by
  default. `APP_MAX_TEXT_CHARS` and `APP_MAX_BODY_BYTES` change the first and the last.

Every error has the same shape, with a stable `code`:

```json
{
  "error": {
    "code": "unknown_model",
    "message": "Unknown model or encoding 'nope'. ...",
    "details": { "valid": ["..."] }
  }
}
```

| Code                    | Status | When                                                   |
| ----------------------- | ------ | ------------------------------------------------------ |
| `validation_error`      | 422    | The body is not valid JSON or a field is wrong         |
| `unknown_model`         | 422    | The model or encoding is not in the catalogue          |
| `not_a_chat_model`      | 422    | `messages` was sent for a model without chat framing   |
| `invalid_token`         | 422    | A token id does not exist in the encoding              |
| `unknown_encoding`      | 404    | The encoding name in the path does not exist           |
| `input_too_large`       | 413    | The input is longer than `APP_MAX_TEXT_CHARS`          |
| `body_too_large`        | 413    | The request body is larger than `APP_MAX_BODY_BYTES`   |
| `refresh_too_soon`      | 429    | Prices were fetched or tried too recently              |
| `prices_layout_changed` | 502    | OpenAI's pages no longer match what the parser expects |
| `prices_fetch_failed`   | 502    | OpenAI's pages could not be downloaded                 |

A `refresh_too_soon` error also sends a `Retry-After` header with the seconds to wait. Other HTTP errors use the
status name as the code, for example `not_found`, `method_not_allowed` or `internal_server_error` for an unexpected
failure.

## Running in Docker

`just up` builds the production image and starts it with Docker Compose. The port is published on `127.0.0.1`
only: tiktokenizer-py is meant for local use, with no login and no request limits, so do not expose it to the
internet.

- **Offline:** the tokenizer files are downloaded during the build and baked into the image. The running app needs
  network access only for "Fetch latest prices".
- **Locked down:** the container runs as a non-root user on a read-only file system, with every Linux capability
  dropped. The only writable place is `/app/data`, a named volume that keeps fetched prices.
- **Health check:** Docker calls `/healthz` every 30 seconds; `just up` waits until the app is healthy.
- **Platforms:** images are built for the host, `linux/arm64` on Apple silicon and `linux/amd64` on Intel and AMD.
  `just docker-build-multi` builds and runs both.

`just up-dev` starts a development container instead, with `src/` mounted and auto-reload, on the same address.
`just up` and `just up-dev` stop each other's container before starting. `just docker-smoke` checks the production
image without network, on a read-only root and as a non-root user.

## Keeping prices current

Maintainers refresh the bundled snapshot with `just prices-update`. It fetches OpenAI's pricing page and every model
page, runs the same layout check as the button, and writes the snapshot only when everything matches. It then lists
what changed; review it with `git diff` and commit it.

Corrections that OpenAI's pages cannot provide live in `src/tiktokenizer_py/data/price_overrides.json`: aliases
priced under a dated name, models without an OpenAI price with the reason shown on the page, context limits from
other official pages, and retired models.
