// The "How the tokenizer works" and "Compare encodings" panels.

import { utf8Length } from "../lib/format.js";
import { postJson } from "../lib/http.js";
import { renderMerges } from "../views/how-it-works.js";

// Merge replays grow with the square of the chunk length; longer chunks show only their ids.
const MERGE_REPLAY_LIMIT = 120;

export function howItWorksPart(ctx) {
  return {
    explainOpen: true,
    chunkCount: 0,
    totalChunks: 0,
    explainError: "",
    chunkIndex: null,
    chunkText: "",
    chunkSpecial: false,
    chunkTokens: [],
    mergeCount: 0,
    mergeTooLong: false,
    mergeError: "",

    compareOpen: true,
    compareRows: [],
    compareError: "",

    // The two panels follow the same input as the token panes.
    async runExtras(body, seq) {
      ctx.extrasInflight?.abort();
      ctx.extrasInflight = new AbortController();
      const signal = ctx.extrasInflight.signal;
      const jobs = [];
      if (this.explainOpen) {
        jobs.push(
          postJson("/api/explain", body, signal).then(({ data, error }) => {
            if (seq !== ctx.sequence) return;
            this.explainError = error ?? "";
            this.applyChunks(data?.chunks ?? [], data?.total_chunks ?? 0);
          }),
        );
      }
      if (this.compareOpen && this.mode === "text") {
        const compareBody = { text: body.text, allow_special: body.allow_special };
        jobs.push(
          postJson("/api/compare", compareBody, signal).then(({ data, error }) => {
            if (seq !== ctx.sequence) return;
            this.compareError = error ?? "";
            this.compareRows = data?.rows ?? [];
          }),
        );
      }
      try {
        await Promise.all(jobs);
      } catch (err) {
        if (err.name !== "AbortError" && seq === ctx.sequence) {
          this.explainError = "Could not reach the server.";
        }
      }
    },

    toggleExplain(open) {
      this.explainOpen = open;
      if (open) this.schedule(0);
    },

    toggleCompare(open) {
      this.compareOpen = open;
      if (open) this.schedule(0);
    },

    applyChunks(chunks, total) {
      const previous = this.chunkIndex === null ? null : ctx.lastChunks[this.chunkIndex];
      ctx.lastChunks = chunks;
      this.chunkCount = chunks.length;
      this.totalChunks = total;
      ctx.chunkList.render(chunks);
      if (chunks.length === 0) {
        this.chunkIndex = null;
        this.chunkText = "";
        this.chunkTokens = [];
        this.mergeCount = 0;
        document.getElementById("merges-body").replaceChildren();
        return;
      }
      // Keep the chunk the reader picked if it is still there, otherwise show the longest
      // ordinary chunk that can be replayed: it has the most merges to watch.
      let index = -1;
      if (previous) {
        index = chunks.findIndex((c) => c.text === previous.text && c.special === previous.special);
      }
      if (index < 0) index = this.pickChunk(chunks);
      this.selectChunk(index, { keep: true });
    },

    // Prefer the longest plain word: its merges read as text. Emoji and other multi-byte
    // chunks replay as raw bytes, which is a harder first example.
    pickChunk(chunks) {
      const score = (c) => {
        const length = utf8Length(c.text);
        if (c.special || length > MERGE_REPLAY_LIMIT) return -1;
        return /^ ?[A-Za-z]+$/.test(c.text) ? 1000 + length : length;
      };
      let best = 0;
      chunks.forEach((c, i) => {
        if (score(c) > score(chunks[best])) best = i;
      });
      return best;
    },

    async selectChunk(i, { keep = false } = {}) {
      const chunk = ctx.lastChunks[i];
      if (!chunk) return;
      // Another encoding can split the same text differently, so compare the tokens too.
      const same =
        this.chunkIndex === i &&
        this.chunkText === chunk.text &&
        this.chunkSpecial === chunk.special &&
        this.chunkTokens.join() === chunk.tokens.join();
      this.chunkIndex = i;
      ctx.chunkList.setSelected(i);
      if (keep && same && !this.mergeError) return;
      this.chunkText = chunk.text;
      this.chunkSpecial = chunk.special;
      this.chunkTokens = chunk.tokens;
      this.mergeError = "";
      const container = document.getElementById("merges-body");
      this.mergeTooLong = !chunk.special && utf8Length(chunk.text) > MERGE_REPLAY_LIMIT;
      if (chunk.special || this.mergeTooLong) {
        this.mergeCount = 0;
        container.replaceChildren();
        return;
      }
      const seq = ++ctx.mergeSequence;
      try {
        const { data, error } = await postJson("/api/merges", { model: this.model, chunk: chunk.text });
        if (seq !== ctx.mergeSequence) return;
        if (error) {
          this.mergeError = error;
          container.replaceChildren();
          return;
        }
        this.mergeCount = data.steps.length - 1;
        renderMerges(container, data.steps, data.tokens);
      } catch {
        if (seq === ctx.mergeSequence) this.mergeError = "Could not reach the server.";
      }
    },

    get compareMax() {
      return Math.max(1, ...this.compareRows.map((r) => r.count));
    },

    modelsLabel(names) {
      if (names.length === 0) return "Not used by a listed model";
      const shown = names.slice(0, 3).join(", ");
      return names.length > 3 ? `${shown} and ${names.length - 3} more` : shown;
    },
  };
}
