"""Plain-language glossary shown in the "What am I looking at?" panel.

Written for readers who are not AI specialists. Every badge and column title in the page links
to one of these entries by id.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    id: str
    title: str
    text: str


GLOSSARY: tuple[GlossaryEntry, ...] = (
    GlossaryEntry(
        id="token",
        title="Token",
        text=(
            "A token is the unit of text a language model reads and writes. It is often a "
            "whole short word, part of a longer word, a space plus a word, or a single symbol. "
            "As a rough rule, one token is about four characters of English text."
        ),
    ),
    GlossaryEntry(
        id="token-count",
        title="Token count",
        text=(
            "The number of tokens the text turns into. Models have a maximum number of tokens they "
            "can handle at once (the context window), and API usage is billed per token."
        ),
    ),
    GlossaryEntry(
        id="token-id",
        title="Token id",
        text=(
            "Each token has a number, its id, in the tokenizer's vocabulary. The model only ever "
            "sees these numbers. Hover a number to see which piece of text it stands for."
        ),
    ),
    GlossaryEntry(
        id="segment",
        title="Segment",
        text=(
            "Each coloured block in the text view is a segment. Usually a segment is one token. "
            "When a single character needs several tokens (many emoji, some accented or non-Latin "
            "letters), those tokens are shown together as one segment so no character is cut in "
            "half."
        ),
    ),
    GlossaryEntry(
        id="grapheme",
        title="Grapheme",
        text=(
            "What a reader sees as one character. A family emoji or a flag looks like one symbol "
            "but is stored as several code points joined together; that whole group is one "
            "grapheme. Segments always end on a grapheme boundary."
        ),
    ),
    GlossaryEntry(
        id="encoding",
        title="Encoding (tokenizer)",
        text=(
            "The rule set that turns text into token ids, for example o200k_base. It contains a "
            "vocabulary of known pieces and a pattern that splits text before the pieces are "
            "matched. Different model generations use different encodings, so the same text can "
            "have a different token count on each."
        ),
    ),
    GlossaryEntry(
        id="vocabulary",
        title="Vocabulary size",
        text=(
            "How many different tokens an encoding knows. Bigger vocabularies usually need fewer "
            "tokens for the same text, especially for languages other than English."
        ),
    ),
    GlossaryEntry(
        id="bpe",
        title="BPE (byte pair encoding)",
        text=(
            "The method behind these tokenizers. Text is first turned into bytes, then the most "
            "common neighbouring pairs are merged again and again, following a ranked list learned "
            "from lots of text. Frequent words end up as one token; rare ones stay in pieces."
        ),
    ),
    GlossaryEntry(
        id="split-regex",
        title="Split pattern",
        text=(
            "Before merging, the text is cut into chunks by a regular expression: words, numbers, "
            "punctuation and whitespace. Newer encodings (o200k_base, cl100k_base) take at most "
            "three digits at a time. Tokens never cross these chunk borders."
        ),
    ),
    GlossaryEntry(
        id="chunk",
        title="Chunk",
        text=(
            "The first stage of tokenizing. The split pattern cuts the text into chunks: a word "
            "with the space before it, a number (up to three digits in newer encodings), a run of "
            "punctuation or whitespace. "
            "Merging happens inside each chunk, so a token never crosses a chunk border. This is "
            "why most tokens start with a space."
        ),
    ),
    GlossaryEntry(
        id="merge",
        title="Merge",
        text=(
            "The second stage. Each chunk starts as single bytes. The tokenizer joins the pair of "
            "neighbours that comes first in its learned merge list, then the next, until no known "
            "pair is left. The pieces that remain are the tokens, and each piece's position in "
            "the list (its rank) is its token id. Click a chunk in How it works to watch it."
        ),
    ),
    GlossaryEntry(
        id="chars-per-token",
        title="Characters per token",
        text=(
            "The number of characters divided by the number of tokens. Higher means the "
            "tokenizer packs more text into each token, so the same text costs fewer tokens. "
            "English is often around four; many other languages, code and emoji are lower."
        ),
    ),
    GlossaryEntry(
        id="compare",
        title="Comparing encodings",
        text=(
            "The same text tokenized by every encoding OpenAI has used. Newer encodings have "
            "bigger vocabularies, so they usually need fewer tokens, especially for languages "
            "other than English and for code."
        ),
    ),
    GlossaryEntry(
        id="partial-character",
        title="Partial character",
        text=(
            "Some characters take several bytes, for example accented letters, Chinese "
            "characters and emoji. A token can hold only some of those bytes. On its own it "
            "cannot be shown as text (you see the replacement mark), but together with its "
            "neighbours it forms the full character."
        ),
    ),
    GlossaryEntry(
        id="special-token",
        title="Special token",
        text=(
            "A reserved token such as <|endoftext|> or <|im_start|> that marks structure instead "
            "of text: the end of a document, the start of a message, and so on. It is always a "
            "single id, even though its written form has many characters."
        ),
    ),
    GlossaryEntry(
        id="special-as-text",
        title="Treat special tokens as text",
        text=(
            "By default, typing <|endoftext|> produces the special token. With this option on, it "
            "is tokenized as ordinary characters instead. This is how the OpenAI API treats text "
            "you send it: users cannot inject special tokens through message content."
        ),
    ),
    GlossaryEntry(
        id="framing",
        title="Chat framing",
        text=(
            "Chat models do not read a list of messages directly. Each message is wrapped in "
            "special tokens that mark who is speaking, then everything is joined into one text. "
            "The chat editor shows that rendered text and counts its tokens."
        ),
    ),
    GlossaryEntry(
        id="estimate",
        title="Estimate",
        text=(
            "OpenAI publishes the tokenizer for each model but not, for most API models, the exact "
            "chat framing. This tool uses the best known framing, so chat counts marked estimate "
            "can differ by a few tokens from what the API reports. Plain text counts are exact."
        ),
    ),
    GlossaryEntry(
        id="name",
        title="Message name",
        text=(
            "An optional author name for a message, for example to tell two users apart. It is "
            "added to the message header after the role, as role:name. OpenAI counts a name as "
            "its own tokens plus one, and this page counts it the same way."
        ),
    ),
    GlossaryEntry(
        id="context-window",
        title="Context window",
        text=(
            "The most tokens a model can work with in one request: your input plus its answer, "
            "including hidden reasoning. OpenAI lists a context window, often a maximum input, "
            "and a maximum output per model. The meter compares your input with the usable "
            "input: the maximum input, or the context window minus the room kept for the reply."
        ),
    ),
    GlossaryEntry(
        id="compaction",
        title="Compacting a conversation",
        text=(
            "When a long conversation gets close to the context window, older messages are "
            "replaced with a short summary so the model keeps working. OpenAI's API can do this "
            "for you once a token threshold you choose is passed. The meter turns amber at the "
            "share you set (80% by default) as a reminder to compact before the window is full."
        ),
    ),
    GlossaryEntry(
        id="cost-estimate",
        title="Cost estimate",
        text=(
            "A rough figure: input tokens times the input price, plus cached input tokens times "
            "the cached price, plus expected output tokens times the output price, all per "
            "million tokens. Prices come from OpenAI's pricing page on the date shown and can "
            "change; you can edit them. Hidden reasoning is billed as output, so include it in "
            "the expected output. Newer models also charge for writing input to the cache; for "
            "them, each cache write you expect per day is added at the write price."
        ),
    ),
    GlossaryEntry(
        id="price-modes",
        title="Price modes",
        text=(
            "OpenAI sells the same model at different speeds. Standard is the default. Batch "
            "runs jobs within 24 hours at about half price. Flex answers more slowly for less. "
            "Fast answers sooner for more. Only the modes a model offers are listed. Requests "
            "with more than 272K input tokens use higher long-request prices on some models."
        ),
    ),
    GlossaryEntry(
        id="billing",
        title="Why the bill can differ",
        text=(
            "The API adds tokens you do not see: chat framing, tool and function definitions, "
            "images, hidden reasoning tokens on reasoning models, and cached-input discounts. Use "
            "this page to understand and compare text sizes, and the usage numbers in the API "
            "response for exact billing."
        ),
    ),
    GlossaryEntry(
        id="whitespace",
        title="Show whitespace",
        text=(
            "Makes invisible characters visible: a dot for a space, an arrow for a tab, and \\n "
            "for a line break. Spaces matter because most tokens include the space before a word."
        ),
    ),
    GlossaryEntry(
        id="decode",
        title="Decode",
        text=(
            "The reverse of tokenizing: paste a list of token ids to see the text they stand for "
            "and the raw bytes behind each one. Some tokens hold only part of a character; their "
            "bytes are shown even when they cannot be printed alone."
        ),
    ),
)
