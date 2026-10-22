// Shareable links: the input, compressed and base64url-encoded in the URL fragment, and the
// address bar's ?model= parameter.

export const SHARE_PREFIX = "#s=";

function toBase64Url(bytes) {
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}

function fromBase64Url(text) {
  const b64 = text.replaceAll("-", "+").replaceAll("_", "/");
  const binary = atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4));
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

export async function packState(state) {
  const raw = new TextEncoder().encode(JSON.stringify(state));
  const stream = new Blob([raw]).stream().pipeThrough(new CompressionStream("deflate-raw"));
  return toBase64Url(new Uint8Array(await new Response(stream).arrayBuffer()));
}

export async function unpackState(packed) {
  const stream = new Blob([fromBase64Url(packed)]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return JSON.parse(await new Response(stream).text());
}

// The shared-state fragment of the current address, or "" when there is none.
export function sharedFragment() {
  return window.location.hash.startsWith(SHARE_PREFIX) ? window.location.hash.slice(SHARE_PREFIX.length) : "";
}

export function modelFromUrl(models, fallback) {
  const wanted = new URLSearchParams(window.location.search).get("model");
  return wanted && models.has(wanted) ? wanted : fallback;
}

// Keep ?model= in the address bar; the shared-state fragment is dropped once it is read.
export function syncUrl(model) {
  const url = new URL(window.location.href);
  url.searchParams.set("model", model);
  url.hash = "";
  window.history.replaceState(null, "", url);
}

// The async Clipboard API needs a secure context; plain-HTTP local hosts fall back to a hidden
// textarea and the copy command.
export async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.append(area);
  area.select();
  const ok = document.execCommand("copy");
  area.remove();
  if (!ok) throw new Error("copy failed");
}
