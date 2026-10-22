// The input (text or chat), the tokenize request, the token panes and the selected segment.

import { formatCount, formatPrice, formatUsd, visible } from "../lib/format.js";
import { postJson } from "../lib/http.js";
import { syncUrl } from "../lib/share.js";

const DEBOUNCE_MS = 50;

let rowSeq = 0;
export function newRow(role, content = "", name = "") {
  rowSeq += 1;
  return { key: rowSeq, role, content, name, withName: name !== "" };
}

export function inputPart(ctx) {
  return {
    text: "",
    mode: "text",
    messages: [newRow("system", "You are a helpful assistant"), newRow("user")],
    allowSpecial: true,
    showWhitespace: false,
    loading: false,
    error: "",
    count: 0,
    characters: 0,
    bytes: 0,
    encoding: "",
    isEstimate: false,
    note: "",
    shownSegments: 0,
    totalSegments: 0,

    // Selected segment details.
    selected: null,
    selectedText: "",
    selectedPieces: [],
    selectedError: "",

    // Re-tokenize whenever the input or the model changes.
    watchInput() {
      this.$watch("model", (value, old) => {
        syncUrl(value);
        const wasChat = ctx.models.get(old)?.is_chat ?? false;
        // Moving to a chat model opens the chat editor, unless there is text to compare.
        if (this.entry.is_chat && !wasChat && this.mode === "text" && !this.text) {
          this.mode = "chat";
        }
        if (!this.entry.is_chat && this.mode === "chat") this.mode = "text";
        this.schedule(0);
      });
      this.$watch("mode", (mode) => {
        if (mode === "decode" && !this.decodeInput.trim() && ctx.lastTokens.length) {
          this.decodeInput = ctx.lastTokens.join(", ");
        }
        this.schedule(0);
      });
      this.$watch("decodeInput", () => {
        this.notice = "";
        if (this.mode === "decode") this.schedule();
      });
      this.$watch("activeEncoding", () => {
        if (this.infoOpen) this.loadInfo();
      });
      this.$watch("messages", () => {
        this.notice = "";
        if (this.mode === "chat") this.schedule();
      });
      this.$watch("text", () => {
        this.notice = "";
        this.schedule();
      });
      this.$watch("allowSpecial", () => this.schedule(0));
      this.$watch("showWhitespace", (on) => ctx.panes.setWhitespace(on));
    },

    get entry() {
      return ctx.models.get(this.model);
    },

    // Plain text uses the encoding tiktoken reports; chat and decode use the chat variant.
    get activeEncoding() {
      return this.mode === "text" ? this.entry.base_encoding : this.entry.encoding;
    },

    // Arrow keys, Home and End move between the input tabs (the ARIA tabs pattern).
    tabKey(event) {
      const tabs = ["text", ...(this.entry.is_chat ? ["chat"] : []), "decode"];
      const i = tabs.indexOf(this.mode);
      const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[event.key];
      if (next === undefined) return;
      event.preventDefault();
      this.mode = tabs[(next + tabs.length) % tabs.length];
      this.$nextTick(() => document.getElementById(`tab-${this.mode}`).focus());
    },

    get charsPerToken() {
      return this.count ? (this.characters / this.count).toFixed(2) : "";
    },

    requestBody() {
      if (this.mode === "chat") {
        return {
          model: this.model,
          messages: this.messages.map((m) => ({
            role: m.role,
            content: m.content,
            name: m.withName ? m.name : "",
          })),
          allow_special: this.allowSpecial,
        };
      }
      return { model: this.model, text: this.text, allow_special: this.allowSpecial };
    },

    addMessage() {
      if (this.messages.length >= ctx.page.limits.max_messages) return;
      const last = this.messages.at(-1)?.role;
      const role = !last ? "system" : last === "user" ? "assistant" : "user";
      this.messages.push(newRow(role));
      this.$nextTick(() => {
        const boxes = this.$root.querySelectorAll(".chat-row textarea");
        boxes[boxes.length - 1]?.focus();
      });
    },

    removeMessage(index) {
      this.messages.splice(index, 1);
    },

    // Put an example into the text box, or into the last user message in chat mode.
    loadExample(id) {
      const example = ctx.page.examples.find((e) => e.id === id);
      if (!example) return;
      if (this.mode === "chat") {
        let row = [...this.messages].reverse().find((m) => m.role === "user");
        if (!row) {
          row = newRow("user");
          this.messages.push(row);
        }
        row.content = example.text;
      } else {
        this.mode = "text";
        this.text = example.text;
      }
    },

    schedule(delay = DEBOUNCE_MS) {
      clearTimeout(ctx.timer);
      ctx.timer = setTimeout(() => this.run(), delay);
    },

    async run() {
      if (this.mode === "decode") return this.runDecode();
      const body = this.requestBody();
      const seq = ++ctx.sequence;
      ctx.inflight?.abort();
      ctx.inflight = new AbortController();
      this.loading = true;
      try {
        const { data, error } = await postJson("/api/tokenize", body, ctx.inflight.signal);
        if (seq !== ctx.sequence) return;
        if (error) {
          this.error = error;
          this.clearResults();
          return;
        }
        this.error = "";
        this.apply(data);
        this.runExtras(body, seq);
      } catch (err) {
        if (err.name === "AbortError") return;
        this.error = "Could not reach the server. Check that it is running and try again.";
        this.clearResults();
      } finally {
        if (seq === ctx.sequence) this.loading = false;
      }
    },

    apply(data) {
      ctx.lastTokens = data.tokens;
      this.count = data.count;
      this.characters = data.characters;
      this.bytes = data.bytes;
      this.encoding = data.encoding;
      this.isEstimate = data.is_estimate;
      this.note = data.note ?? "";
      ctx.lastSegments = data.segments;
      this.totalSegments = data.segments.length;
      this.clearSelection();
      this.shownSegments = ctx.panes.render(data.segments);
    },

    // An error must not leave the previous result on screen as if it were current.
    clearResults() {
      this.apply({
        tokens: [],
        count: 0,
        characters: 0,
        bytes: 0,
        encoding: "",
        is_estimate: false,
        note: "",
        segments: [],
      });
      this.applyChunks([], 0);
      this.compareRows = [];
    },

    showAllSegments() {
      this.clearSelection();
      this.shownSegments = ctx.panes.render(ctx.lastSegments, Infinity);
    },

    async selectSegment(i) {
      if (this.selected === i) {
        this.clearSelection();
        return;
      }
      const segment = ctx.lastSegments[i];
      if (!segment) return;
      this.selected = i;
      ctx.panes.setSelected(i);
      this.selectedText = segment.text;
      this.selectedPieces = [];
      this.selectedError = "";
      const seq = ++ctx.detailSequence;
      try {
        const body = { model: this.model, tokens: segment.tokens.map((t) => t.id) };
        const { data, error } = await postJson("/api/decode", body);
        if (seq !== ctx.detailSequence) return;
        this.selectedError = error ?? "";
        this.selectedPieces = data?.pieces ?? [];
      } catch {
        if (seq === ctx.detailSequence) this.selectedError = "Could not reach the server.";
      }
    },

    clearSelection() {
      ctx.detailSequence += 1;
      this.selected = null;
      this.selectedPieces = [];
      this.selectedError = "";
      ctx.panes?.setSelected(null);
    },

    // Formatters for the template.
    visible(text) {
      return visible(text);
    },

    formatCount(n) {
      return formatCount(n);
    },

    formatUsd(value) {
      return formatUsd(value);
    },

    formatPrice(value) {
      return formatPrice(value);
    },
  };
}
