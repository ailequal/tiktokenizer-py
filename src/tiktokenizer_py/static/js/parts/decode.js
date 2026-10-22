// Decode mode: token ids back to text.

import { postJson } from "../lib/http.js";

const MAX_DECODE_ROWS = 2000;

// Parse "1, 2 3\n[4]" into numbers; returns { ids } or { error }.
function parseIds(input) {
  const parts = input.split(/[\s,;\[\]]+/).filter(Boolean);
  const bad = parts.find((p) => !/^\d+$/.test(p));
  if (bad !== undefined) {
    return { error: `"${bad}" is not a token id. Enter whole numbers separated by commas or spaces.` };
  }
  return { ids: parts.map(Number) };
}

export function decodePart(ctx) {
  return {
    decodeInput: "",
    decodeText: "",
    decodePieces: [],
    decodeTotal: 0,

    async runDecode() {
      const seq = ++ctx.sequence;
      ctx.inflight?.abort();
      const parsed = parseIds(this.decodeInput);
      if (parsed.error || parsed.ids.length === 0) {
        this.loading = false;
        this.error = parsed.error ?? "";
        this.clearDecode();
        return;
      }
      ctx.inflight = new AbortController();
      this.loading = true;
      try {
        const body = { model: this.model, tokens: parsed.ids };
        const { data, error } = await postJson("/api/decode", body, ctx.inflight.signal);
        if (seq !== ctx.sequence) return;
        if (error) {
          this.error = error;
          this.clearDecode();
          return;
        }
        this.error = "";
        this.decodeText = data.text;
        this.decodeTotal = data.pieces.length;
        this.decodePieces = data.pieces.slice(0, MAX_DECODE_ROWS);
      } catch (err) {
        if (err.name === "AbortError") return;
        this.error = "Could not reach the server. Check that it is running and try again.";
        this.clearDecode();
      } finally {
        if (seq === ctx.sequence) this.loading = false;
      }
    },

    clearDecode() {
      this.decodeText = "";
      this.decodePieces = [];
      this.decodeTotal = 0;
    },
  };
}
