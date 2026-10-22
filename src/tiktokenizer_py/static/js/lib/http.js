// JSON requests to the tokenizer API.

// Parse a response body; non-JSON bodies (a proxy error page, say) give an error message.
export async function readJson(res) {
  const isJson = (res.headers.get("content-type") ?? "").includes("application/json");
  const data = isJson ? await res.json() : null;
  if (res.ok && data) return { data };
  if (data?.error?.message) return { error: data.error.message };
  // No JSON body: the app itself did not answer (stopped, restarting, or not routed).
  return {
    error: `The tokenizer server is not responding (${res.status} ${res.statusText}). Check that it is running and try again.`,
  };
}

export async function postJson(url, body, signal) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  return readJson(res);
}
