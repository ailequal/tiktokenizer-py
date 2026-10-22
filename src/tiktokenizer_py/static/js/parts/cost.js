// Context window meter, reference prices and the cost estimate.

import { clampNumber } from "../lib/format.js";
import { STORE_CALC, STORE_PRICES, loadStored, saveStored } from "../lib/storage.js";

export const PRICE_MODES = ["standard", "batch", "flex", "fast", "ultrafast"];
export const PRICE_FIELDS = ["input", "cached_input", "output", "cache_write_30m", "cache_write_12h"];
const FIELD_LABELS = {
  input: "Input",
  cached_input: "Cached input",
  output: "Output",
  cache_write_30m: "30 min write",
  cache_write_12h: "12 h write",
};
// Cache lifetimes and the price field each one is billed at.
export const CACHE_TTLS = { "30m": "cache_write_30m", "12h": "cache_write_12h" };
const CALC_DEFAULTS = { output: 1000, cachedPct: 0, perDay: 1, writesPerDay: 1, reserve: 25000, compactPct: 80 };
const DAYS_PER_MONTH = 30;

export function costPart(ctx) {
  // Prices: the snapshot in use, prices saved in this browser, and prices from a shared link
  // (those apply to the current view only and are never saved).
  ctx.priceData = ctx.page.prices;
  ctx.savedPrices = loadStored(STORE_PRICES, {});
  ctx.linkPrices = {};
  const storedCalc = loadStored(STORE_CALC, {});

  return {
    output: clampNumber(storedCalc.output, 0, 1e9, CALC_DEFAULTS.output),
    cachedPct: clampNumber(storedCalc.cachedPct, 0, 100, CALC_DEFAULTS.cachedPct),
    perDay: clampNumber(storedCalc.perDay, 0, 1e9, CALC_DEFAULTS.perDay),
    reserve: clampNumber(storedCalc.reserve, 0, 1e9, CALC_DEFAULTS.reserve),
    compactPct: clampNumber(storedCalc.compactPct, 1, 100, CALC_DEFAULTS.compactPct),
    priceMode: PRICE_MODES.includes(storedCalc.priceMode) ? storedCalc.priceMode : "standard",
    cacheTtl: storedCalc.cacheTtl in CACHE_TTLS ? storedCalc.cacheTtl : "30m",
    writesPerDay: clampNumber(storedCalc.writesPerDay, 0, 1e9, CALC_DEFAULTS.writesPerDay),
    // Input tokens typed in the calculator; null follows the page's token count.
    inputOverride: null,
    meterSettings: false,
    suppressSave: false,
    pricesVersion: 0,
    refreshing: false,
    refreshMessage: "",
    refreshError: false,
    refreshProblems: [],

    // Save the calculator settings and keep the price mode valid for the model.
    watchCost() {
      // A remembered mode the opening model does not offer falls back to Standard.
      if (!this.priceModes.includes(this.priceMode)) this.priceMode = "standard";
      for (const key of ["output", "cachedPct", "perDay", "writesPerDay", "cacheTtl", "reserve", "compactPct", "priceMode"]) {
        this.$watch(key, () => this.saveCalc());
      }
      this.$watch("model", () => {
        if (!this.priceModes.includes(this.priceMode)) this.priceMode = "standard";
      });
    },

    // --- context meter -----------------------------------------------------------------

    get modelPricing() {
      void this.pricesVersion;
      return this.entry.kind === "model" ? (ctx.priceData.models[this.model] ?? null) : null;
    },

    get limits() {
      return this.modelPricing?.limits ?? null;
    },

    // Room kept for the reply and reasoning: never more than the model can output, and never
    // more than half the context window, so small windows (gpt-4: 8,192 for input and
    // output together) still leave room for input.
    get effectiveReserve() {
      const lim = this.limits;
      if (!lim?.max_output) return 0;
      const reserve = clampNumber(this.reserve, 0, 1e9, CALC_DEFAULTS.reserve);
      const caps = [lim.max_output, lim.context_window ? Math.floor(lim.context_window / 2) : null];
      return Math.min(reserve, ...caps.filter((v) => v !== null));
    },

    // Usable input: the maximum input, or the context window minus the reserve.
    get usableInput() {
      const lim = this.limits;
      if (!lim) return 0;
      const fromWindow = lim.context_window ? lim.context_window - this.effectiveReserve : null;
      const candidates = [lim.max_input, fromWindow].filter((v) => v !== null && v > 0);
      return candidates.length ? Math.min(...candidates) : 0;
    },

    get meterPct() {
      return this.usableInput ? (this.count / this.usableInput) * 100 : 0;
    },

    // The warning threshold as typed, kept within 1 to 100 so the marker stays on the bar.
    get compactAt() {
      return clampNumber(this.compactPct, 1, 100, CALC_DEFAULTS.compactPct);
    },

    get meterLevel() {
      if (this.meterPct > 100) return "over";
      if (this.meterPct >= this.compactAt) return "warn";
      return "ok";
    },

    get meterText() {
      const pct = this.meterPct < 0.1 && this.count > 0 ? "<0.1" : this.meterPct.toFixed(1);
      return `${this.formatCount(this.count)} of ${this.formatCount(this.usableInput)} usable input tokens (${pct}%)`;
    },

    get meterDetail() {
      const lim = this.limits;
      if (!lim) return "";
      const parts = [];
      if (lim.context_window) parts.push(`${this.formatCount(lim.context_window)} tokens`);
      if (lim.max_input) parts.push(`maximum input ${this.formatCount(lim.max_input)}`);
      if (lim.max_output) parts.push(`maximum output ${this.formatCount(lim.max_output)}`);
      if (this.effectiveReserve) parts.push(`${this.formatCount(this.effectiveReserve)} kept for the reply`);
      return parts.join(", ");
    },

    get meterMessage() {
      if (this.meterLevel === "over") {
        return "Too long: this leaves less room than you keep for the reply, or is above the model's maximum input. Shorten it or compact the conversation.";
      }
      if (this.meterLevel === "warn") {
        return "Getting full: consider compacting the conversation (summarizing older messages) before adding more.";
      }
      return "";
    },

    get noLimitsMessage() {
      if (this.entry.kind !== "model") return "Pick a model to see its context window and cost.";
      return "OpenAI publishes no context window for this model.";
    },

    // --- prices -------------------------------------------------------------------------

    get pricesLabel() {
      void this.pricesVersion;
      const when = new Date(ctx.priceData.fetched_at);
      const date = when.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" });
      const origin = ctx.priceData.origin === "fetched" ? "fetched with this page" : "shipped with the app";
      return `Prices from OpenAI as of ${date} UTC (${origin})`;
    },

    get pricingPage() {
      void this.pricesVersion;
      return ctx.priceData.sources?.page ?? "https://developers.openai.com/api/docs/pricing";
    },

    get priceModes() {
      const prices = this.modelPricing?.prices ?? {};
      const modes = PRICE_MODES.filter((m) => prices[m]);
      return modes.length ? modes : ["standard"];
    },

    modeLabel(mode) {
      return mode.charAt(0).toUpperCase() + mode.slice(1);
    },

    get priceNote() {
      return this.modelPricing?.price_note ?? "";
    },

    get hasLongPrices() {
      return Boolean(this.modelPricing?.prices?.[this.priceMode]?.long);
    },

    // Newer models (gpt-5.6 and later) also charge for writing input to the cache.
    get hasWritePrices() {
      return Object.values(CACHE_TTLS).some((field) => this.referencePrice("short", field) !== null);
    },

    get priceFields() {
      return this.hasWritePrices ? PRICE_FIELDS : PRICE_FIELDS.slice(0, 3);
    },

    fieldLabel(field) {
      return FIELD_LABELS[field];
    },

    get longThreshold() {
      void this.pricesVersion;
      return ctx.priceData.long_context_threshold;
    },

    referencePrice(row, field) {
      const mode = this.modelPricing?.prices?.[this.priceMode];
      if (!mode) return null;
      const source = row === "long" ? mode.long : mode;
      return source?.[field] ?? null;
    },

    customPrice(row, field) {
      const key = `${this.priceMode}.${row}.${field}`;
      const fromLink = ctx.linkPrices[this.model]?.[key];
      if (fromLink !== undefined) return fromLink;
      return ctx.savedPrices[this.model]?.[key];
    },

    // The price used: a custom one if set, otherwise the reference price.
    price(row, field) {
      void this.pricesVersion;
      const custom = this.customPrice(row, field);
      return custom !== undefined ? custom : this.referencePrice(row, field);
    },

    isCustom(row, field) {
      void this.pricesVersion;
      const custom = this.customPrice(row, field);
      return custom !== undefined && custom !== this.referencePrice(row, field);
    },

    get anyCustom() {
      void this.pricesVersion;
      return ["short", "long"].some((row) => PRICE_FIELDS.some((f) => this.isCustom(row, f)));
    },

    setPrice(row, field, raw) {
      const key = `${this.priceMode}.${row}.${field}`;
      const value = raw === "" ? undefined : clampNumber(raw, 0, 1e6, undefined);
      if (ctx.linkPrices[this.model]) delete ctx.linkPrices[this.model][key];
      const forModel = { ...(ctx.savedPrices[this.model] ?? {}) };
      if (value === undefined || value === this.referencePrice(row, field)) {
        delete forModel[key];
      } else {
        forModel[key] = value;
      }
      ctx.savedPrices = { ...ctx.savedPrices, [this.model]: forModel };
      saveStored(STORE_PRICES, ctx.savedPrices);
      this.pricesVersion += 1;
    },

    resetPrices() {
      const prefix = `${this.priceMode}.`;
      const keep = (obj) => Object.fromEntries(Object.entries(obj ?? {}).filter(([k]) => !k.startsWith(prefix)));
      ctx.savedPrices = { ...ctx.savedPrices, [this.model]: keep(ctx.savedPrices[this.model]) };
      ctx.linkPrices = { ...ctx.linkPrices, [this.model]: keep(ctx.linkPrices[this.model]) };
      saveStored(STORE_PRICES, ctx.savedPrices);
      this.pricesVersion += 1;
    },

    saveCalc() {
      if (this.suppressSave) return;
      saveStored(STORE_CALC, {
        output: this.output,
        cachedPct: this.cachedPct,
        perDay: this.perDay,
        writesPerDay: this.writesPerDay,
        cacheTtl: this.cacheTtl,
        reserve: this.reserve,
        compactPct: this.compactPct,
        priceMode: this.priceMode,
      });
    },

    // Settings from a link apply to this view; they are saved only once the reader edits them.
    applySharedCalc(calc) {
      if (typeof calc !== "object" || calc === null) return;
      this.suppressSave = true;
      this.inputOverride = calc.input === null || calc.input === undefined ? null : clampNumber(calc.input, 0, 1e9, null);
      this.output = clampNumber(calc.output, 0, 1e9, this.output);
      this.cachedPct = clampNumber(calc.cachedPct, 0, 100, this.cachedPct);
      this.perDay = clampNumber(calc.perDay, 0, 1e9, this.perDay);
      this.writesPerDay = clampNumber(calc.writesPerDay, 0, 1e9, this.writesPerDay);
      if (calc.cacheTtl in CACHE_TTLS) this.cacheTtl = calc.cacheTtl;
      this.reserve = clampNumber(calc.reserve, 0, 1e9, this.reserve);
      this.compactPct = clampNumber(calc.compactPct, 1, 100, this.compactPct);
      if (PRICE_MODES.includes(calc.priceMode)) this.priceMode = calc.priceMode;
      const prices = {};
      for (const [key, value] of Object.entries(calc.prices ?? {})) {
        const [mode, row, field] = key.split(".");
        if (PRICE_MODES.includes(mode) && ["short", "long"].includes(row) && PRICE_FIELDS.includes(field)) {
          prices[key] = clampNumber(value, 0, 1e6, 0);
        }
      }
      ctx.linkPrices = { ...ctx.linkPrices, [this.model]: prices };
      this.pricesVersion += 1;
      this.$nextTick(() => {
        this.suppressSave = false;
      });
    },

    // --- cost --------------------------------------------------------------------------

    get inputTokens() {
      return this.inputOverride === null ? this.count : this.inputOverride;
    },

    setInputTokens(raw) {
      this.inputOverride = raw === "" ? null : clampNumber(raw, 0, 1e9, null);
      if (this.inputOverride !== null) this.inputOverride = Math.round(this.inputOverride);
    },

    get usesLongPrices() {
      return this.hasLongPrices && this.inputTokens > this.longThreshold;
    },

    get cost() {
      void this.pricesVersion;
      const row = this.usesLongPrices ? "long" : "short";
      const pIn = this.price(row, "input");
      if (pIn === null || pIn === undefined) return null;
      const pCached = this.price(row, "cached_input");
      const pOut = this.price(row, "output");
      const input = this.inputTokens;
      const output = clampNumber(this.output, 0, 1e9, CALC_DEFAULTS.output);
      const share = pCached === null || pCached === undefined ? 0 : clampNumber(this.cachedPct, 0, 100, 0);
      const cached = Math.round((input * share) / 100);
      const lines = [
        { label: "Input", tokens: input - cached, price: pIn },
        ...(cached > 0 ? [{ label: "Cached input", tokens: cached, price: pCached }] : []),
        { label: "Output", tokens: output, price: pOut ?? 0 },
      ].map((l) => ({ ...l, cost: (l.tokens * l.price) / 1e6 }));
      const perRequest = lines.reduce((sum, l) => sum + l.cost, 0);
      const requests = clampNumber(this.perDay, 0, 1e9, 1);
      // A cache write stores the cached part of the input; it replaces one cached read and is
      // billed at the write price of the chosen lifetime instead.
      const pWrite = this.hasWritePrices ? this.price(row, CACHE_TTLS[this.cacheTtl]) : null;
      const writes = Math.min(clampNumber(this.writesPerDay, 0, 1e9, CALC_DEFAULTS.writesPerDay), requests);
      const writeLine =
        cached > 0 && writes > 0 && pWrite !== null && pWrite !== undefined
          ? { writes, tokens: cached, price: pWrite, readPrice: pCached, cost: (writes * cached * (pWrite - pCached)) / 1e6 }
          : null;
      const perDay = perRequest * requests + (writeLine?.cost ?? 0);
      return {
        lines,
        writeLine,
        perRequest,
        perDay,
        perMonth: perDay * DAYS_PER_MONTH,
        noCachedPrice: pCached === null || pCached === undefined,
        noOutputPrice: pOut === null || pOut === undefined,
      };
    },

    async refreshPrices() {
      this.refreshing = true;
      this.refreshMessage = "";
      this.refreshProblems = [];
      try {
        const res = await fetch("/api/prices/refresh", { method: "POST" });
        const isJson = (res.headers.get("content-type") ?? "").includes("application/json");
        const body = isJson ? await res.json() : null;
        if (!res.ok || !body) {
          this.refreshError = true;
          this.refreshMessage =
            body?.error?.message ?? `The tokenizer server is not responding (${res.status} ${res.statusText}).`;
          this.refreshProblems = body?.error?.details?.problems ?? [];
          return;
        }
        ctx.priceData = body.prices;
        this.pricesVersion += 1;
        if (!this.priceModes.includes(this.priceMode)) this.priceMode = "standard";
        this.refreshError = false;
        const changed = body.changes.length;
        this.refreshMessage =
          (changed === 0 ? "Prices are up to date: nothing changed." : `Prices updated: ${changed} ${changed === 1 ? "change" : "changes"}.`) +
          (body.saved ? "" : " They could not be saved, so they last until the server restarts.");
      } catch {
        this.refreshError = true;
        this.refreshMessage = "Could not reach the server. Check that it is running and try again.";
      } finally {
        this.refreshing = false;
      }
    },
  };
}
