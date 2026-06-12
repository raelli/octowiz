// A2A TRANSPORT — the single owner of how the Bridge speaks JSON-RPC 2.0
// to A2A endpoints (the Python A2A server, AELLI, the LiteLLM gateway).
//
// Owns: the request envelope, artifact extraction, HTTP POST with timeout,
// and the error vocabulary. Callers say what they want sent where; nothing
// outside this module builds an envelope or walks an RPC response.

const http = require("http");
const https = require("https");

// JSON-RPC 2.0 envelope around a single text part. `text` may be null for an
// intentionally empty parts array (used by diagnostics probes). id, role, and
// messageId are included only when given — the Python parser and AELLI both
// accept the minimal shape, and existing endpoints see exactly the bytes the
// pre-transport call sites sent.
function buildEnvelope(method, text, { id, role, messageId } = {}) {
  return {
    jsonrpc: "2.0",
    method,
    ...(id !== undefined ? { id } : {}),
    params: {
      message: {
        ...(role !== undefined ? { role } : {}),
        ...(messageId !== undefined ? { messageId } : {}),
        parts: text === null || text === undefined ? [] : [{ kind: "text", text }],
      },
    },
  };
}

// Pull the artifact out of a JSON-RPC response: result.artifacts[0].parts[0].text,
// parsed as JSON. Returns `fallback` when no artifact text is present. Throws on
// malformed artifact JSON — the caller decides whether that is fatal or fail-open.
function extractArtifact(rpc, fallback = {}) {
  const text = rpc?.result?.artifacts?.[0]?.parts?.[0]?.text;
  return text ? JSON.parse(text) : fallback;
}

// JSON-over-HTTP primitive. Resolves { status, body } where body is parsed
// JSON when possible, raw text otherwise. Rejects on network failure and on
// timeout (with an explicit message). Never rejects on HTTP status — status
// policy belongs to the caller.
function httpJson(method, urlStr, body = null, { headers = {}, timeoutMs = 30_000 } = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    const isHttps = url.protocol === "https:";
    const lib = isHttps ? https : http;
    const payload = body === null ? null : JSON.stringify(body);

    const options = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname + url.search,
      method,
      headers: {
        "Content-Type": "application/json",
        ...(payload !== null ? { "Content-Length": Buffer.byteLength(payload) } : {}),
        ...headers,
      },
    };

    const req = lib.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        let parsed;
        try {
          parsed = JSON.parse(data);
        } catch {
          parsed = data;
        }
        resolve({ status: res.statusCode, body: parsed });
      });
    });

    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error(`request timed out after ${timeoutMs}ms`));
    });
    req.on("error", reject);
    if (payload !== null) req.write(payload);
    req.end();
  });
}

// Send one A2A event and return its artifact.
//
// Serializes `payload` as the envelope's text part, POSTs it, and extracts
// the artifact (`fallback` — default {} — when the response carries none).
// Throws on network error, non-200 status, or malformed artifact JSON; the
// caller owns the recovery policy.
async function sendEvent(
  urlStr,
  { method, payload, id, role, messageId, headers = {}, timeoutMs = 30_000, fallback = {} }
) {
  const envelope = buildEnvelope(method, JSON.stringify(payload), { id, role, messageId });
  const { status, body } = await httpJson("POST", urlStr, envelope, { headers, timeoutMs });
  if (status !== 200) {
    const excerpt = typeof body === "string" ? body : JSON.stringify(body);
    throw new Error(`A2A server returned HTTP ${status}: ${String(excerpt).slice(0, 200)}`);
  }
  try {
    return extractArtifact(body, fallback);
  } catch (err) {
    throw new Error(`Failed to parse A2A response: ${err.message}`);
  }
}

module.exports = { buildEnvelope, extractArtifact, httpJson, sendEvent };
