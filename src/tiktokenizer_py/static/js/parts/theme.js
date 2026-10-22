// The theme button: follow the system setting, or pin light or dark.

import { loadStored, saveStored } from "../lib/storage.js";

const STORE_THEME = "tiktokenizer-py:theme";
const ORDER = ["auto", "light", "dark"];

export function themePart() {
  const stored = loadStored(STORE_THEME, "auto");

  return {
    theme: ORDER.includes(stored) ? stored : "auto",

    get themeLabel() {
      return this.theme.charAt(0).toUpperCase() + this.theme.slice(1);
    },

    cycleTheme() {
      this.theme = ORDER[(ORDER.indexOf(this.theme) + 1) % ORDER.length];
      // "auto" removes the attribute, so the stylesheet follows prefers-color-scheme again.
      if (this.theme === "auto") delete document.documentElement.dataset.theme;
      else document.documentElement.dataset.theme = this.theme;
      saveStored(STORE_THEME, this.theme);
    },
  };
}
