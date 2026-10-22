// Browser storage can be missing or blocked (private windows); the page works without it.

export const STORE_PRICES = "tiktokenizer-py:prices:v1";
export const STORE_CALC = "tiktokenizer-py:calc:v1";

export function loadStored(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

export function saveStored(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Not saved; the values still apply to this page.
  }
}
