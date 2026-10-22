// "Copy link", "Copy ids" and opening a shared link.

import { SHARE_PREFIX, copyText, modelFromUrl, packState, sharedFragment, syncUrl, unpackState } from "../lib/share.js";
import { newRow } from "./input.js";
import { PRICE_FIELDS } from "./cost.js";

// Links longer than this may be cut by chat apps, mail clients and some servers.
const LONG_LINK = 8000;

export function sharingPart(ctx) {
  return {
    status: "",
    shareLink: "",
    notice: "",

    // Open the page with the state of a shared link, or with the intro example.
    async restoreFromLink() {
      const shared = sharedFragment();
      syncUrl(this.model);
      if (shared) {
        await this.restoreShared(shared);
      } else {
        // First visit: plain text with an example that shows the interesting cases.
        this.text = ctx.introText;
      }
      // A shared link opened in a tab that already shows the page only changes the
      // fragment, which does not reload the page.
      window.addEventListener("hashchange", async () => {
        const packed = sharedFragment();
        if (!packed) return;
        this.model = modelFromUrl(ctx.models, this.model);
        syncUrl(this.model);
        this.notice = "";
        await this.restoreShared(packed);
        this.schedule(0);
      });
    },

    flash(message) {
      this.status = message;
      clearTimeout(ctx.statusTimer);
      ctx.statusTimer = setTimeout(() => {
        this.status = "";
      }, 2500);
    },

    sharedState() {
      const state = { v: 1, mode: this.mode, special: this.allowSpecial };
      // Calculator settings and the custom prices in use, so the estimate reproduces exactly.
      const custom = {};
      for (const row of ["short", "long"]) {
        for (const field of PRICE_FIELDS) {
          if (this.isCustom(row, field)) custom[`${this.priceMode}.${row}.${field}`] = this.price(row, field);
        }
      }
      state.calc = {
        input: this.inputOverride,
        output: this.output,
        cachedPct: this.cachedPct,
        perDay: this.perDay,
        writesPerDay: this.writesPerDay,
        cacheTtl: this.cacheTtl,
        reserve: this.reserve,
        compactPct: this.compactPct,
        priceMode: this.priceMode,
        prices: custom,
      };
      if (this.mode === "chat") {
        state.messages = this.messages.map((m) => ({
          role: m.role,
          content: m.content,
          name: m.withName ? m.name : "",
        }));
      } else if (this.mode === "decode") {
        state.decode = this.decodeInput;
      } else {
        state.text = this.text;
      }
      return state;
    },

    async copyLink() {
      this.shareLink = "";
      const url = new URL(window.location.href);
      url.searchParams.set("model", this.model);
      url.hash = SHARE_PREFIX.slice(1) + (await packState(this.sharedState()));
      const link = url.toString();
      try {
        await copyText(link);
        this.flash("Link copied");
      } catch {
        // Show the link so it can be copied by hand.
        this.shareLink = link;
      }
      this.notice =
        link.length > LONG_LINK
          ? `This link is ${this.formatCount(link.length)} characters long. Some apps and servers cut links that long, so it may not open; for long inputs, share the text itself.`
          : "";
    },

    async copyIds() {
      try {
        await copyText(JSON.stringify(ctx.lastTokens));
        this.flash(`${this.formatCount(ctx.lastTokens.length)} ids copied`);
      } catch {
        this.flash("Copying failed. Select the ids and copy them by hand.");
      }
    },

    async restoreShared(packed) {
      try {
        const state = await unpackState(packed);
        if (typeof state !== "object" || state === null) throw new Error("bad state");
        this.allowSpecial = state.special !== false;
        this.applySharedCalc(state.calc);
        if (state.mode === "chat" && Array.isArray(state.messages) && this.entry.is_chat) {
          this.messages = state.messages
            .filter((m) => ctx.page.roles.includes(m?.role))
            .slice(0, ctx.page.limits.max_messages)
            .map((m) => newRow(m.role, String(m.content ?? ""), String(m.name ?? "")));
          this.mode = "chat";
        } else if (state.mode === "decode" && typeof state.decode === "string") {
          this.decodeInput = state.decode;
          this.mode = "decode";
        } else if (typeof state.text === "string") {
          this.text = state.text;
          this.mode = "text";
        } else {
          throw new Error("bad state");
        }
      } catch {
        this.mode = "text";
        this.text = ctx.introText;
        // Set after the watchers have seen the new text, which clear the notice.
        this.$nextTick(() => {
          this.notice = "This shared link could not be read, so the page opened with an example.";
        });
      }
    },
  };
}
