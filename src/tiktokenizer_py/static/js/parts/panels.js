// The encoding details panel and the glossary drawer.

import { readJson } from "../lib/http.js";

export function panelsPart(ctx) {
  const infoCache = new Map();

  return {
    infoOpen: false,
    info: null,
    infoError: "",

    glossaryOpen: false,
    glossaryFlash: "",
    glossaryOpener: null,

    toggleInfo(open) {
      this.infoOpen = open;
      if (open) this.loadInfo();
    },

    async loadInfo() {
      const name = this.activeEncoding;
      this.infoError = "";
      if (infoCache.has(name)) {
        this.info = infoCache.get(name);
        return;
      }
      this.info = null;
      let message;
      try {
        const { data, error } = await readJson(await fetch(`/api/encodings/${encodeURIComponent(name)}`));
        if (data) infoCache.set(name, data);
        message = error;
      } catch {
        message = "Could not reach the server.";
      }
      if (this.activeEncoding !== name) return;
      this.info = infoCache.get(name) ?? null;
      this.infoError = message ? `Could not load details for ${name}. ${message}` : "";
    },

    get specialTokenList() {
      return Object.entries(this.info?.special_tokens ?? {});
    },

    openGlossary(id = "") {
      this.glossaryOpener = document.activeElement;
      this.glossaryOpen = true;
      this.glossaryFlash = id;
      // Wait for x-show to display the drawer: focus and scrolling do nothing while hidden.
      this.$nextTick(() =>
        requestAnimationFrame(() => {
          // Focus first without scrolling, then bring the requested entry into view.
          this.$refs.glossaryClose.focus({ preventScroll: true });
          const target = id && document.getElementById(`g-${id}`);
          if (target) {
            target.scrollIntoView({ block: "start" });
          } else {
            this.$refs.glossaryBody.scrollTop = 0;
          }
        }),
      );
    },

    closeGlossary() {
      if (!this.glossaryOpen) return;
      this.glossaryOpen = false;
      this.glossaryFlash = "";
      // The page stops being inert on the next tick; focus cannot land on it before.
      const opener = this.glossaryOpener;
      this.$nextTick(() => opener?.focus?.());
    },
  };
}
