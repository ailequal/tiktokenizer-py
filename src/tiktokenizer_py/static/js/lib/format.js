// Number and text formatting shared by the page.

// A number from a form field, or the fallback when it is empty or not a number.
export function clampNumber(value, min, max, fallback) {
  const n = typeof value === "number" ? value : Number.parseFloat(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, n));
}

export function formatCount(n) {
  return n.toLocaleString("en-US");
}

export function formatUsd(raw) {
  // Sums of float products carry noise (1.2 + 0.015 is 1.2149999...); drop it before rounding.
  const value = Number(raw.toPrecision(12));
  if (value === 0) return "$0";
  if (value >= 1) {
    return "$" + value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return "$" + value.toLocaleString("en-US", { maximumSignificantDigits: 3 });
}

export function formatPrice(value) {
  return value === null || value === undefined ? "none" : "$" + value.toLocaleString("en-US", { maximumFractionDigits: 4 });
}

// Make invisible characters visible. Order matters: "\r\n" is fixed up last.
export function encodeWhitespace(str) {
  return str
    .replaceAll(" ", "\u22c5")
    .replaceAll("\t", "\u2192")
    .replaceAll("\f", "\\f\f")
    .replaceAll("\b", "\\b\b")
    .replaceAll("\v", "\\v\v")
    .replaceAll("\r", "\\r\r")
    .replaceAll("\n", "\\n\n")
    .replaceAll("\\r\r\\n\n", "\\r\\n\r\n");
}

// One-line form for table cells and chips: whitespace as symbols, and characters that draw
// nothing (joiners, variation selectors, control codes) as their code point.
const INVISIBLE = /[\s\p{Cf}\p{Cc}\u{FE00}-\u{FE0F}\u{E0100}-\u{E01EF}]/gu;
export function visible(text) {
  return text.replace(INVISIBLE, (ch) => {
    switch (ch) {
      case " ":
        return "\u22c5";
      case "\t":
        return "\u2192";
      case "\n":
        return "\\n";
      case "\r":
        return "\\r";
      default:
        return `[U+${ch.codePointAt(0).toString(16).toUpperCase().padStart(4, "0")}]`;
    }
  });
}

export function utf8Length(text) {
  return new TextEncoder().encode(text).length;
}
