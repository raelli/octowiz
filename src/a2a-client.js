const http = require("http");
const https = require("https");
const fs = require("fs");
const logger = require("./logger");
const config = require("./config");

const MAX_RECONNECT_MS = 30_000;

// Surface misconfiguration once at load time (config owns the rules).
for (const warning of config.configWarnings()) {
  logger.warn(warning);
}

function appendLog(msg) {
  try {
    fs.appendFileSync(config.logFile(), `[${new Date().toISOString()}] ${msg}\n`);
  } catch {}
}

// Build a standard JSON-RPC POST init object (shared by post() and route()).
// subscribeToQueue() intentionally uses queueAuthHeaders() and does not go
// through this helper — it connects to octowiz's own inbound queue, not AELLI.
function _jsonInit(body) {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json", ...config.aelliAuthHeaders() },
    body: typeof body === "string" ? body : JSON.stringify(body),
  };
}

// Timeout-guarded fetch. Returns [Response, null] on success or [null, Error] on
// abort / network failure. Caller reads the body; we do not consume it here.
async function _abortFetch(url, init, timeoutMs) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...init, signal: ctrl.signal });
    return [res, null];
  } catch (err) {
    return [null, err];
  } finally {
    clearTimeout(timer);
  }
}

// Pure SSE framing parser. Takes the accumulated buffer string, returns
// complete events and the leftover partial chunk.
function parseSseEvents(buffer) {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const blocks = normalized.split("\n\n");
  const remainder = blocks.pop(); // last entry is always the incomplete tail
  const events = [];
  for (const block of blocks) {
    const lines = block.trim().split("\n");
    let event = "message";
    const dataParts = [];
    for (const line of lines) {
      if (line.startsWith("event: ")) event = line.slice(7);
      if (line.startsWith("data: ")) dataParts.push(line.slice(6));
    }
    events.push({ event, data: dataParts.join("\n") });
  }
  return { events, remainder };
}

function request(method, urlPath, body = null) {
  return new Promise((resolve, reject) => {
    const url = new URL(config.apiBase() + urlPath);
    const isHttps = url.protocol === "https:";
    const lib = isHttps ? https : http;

    const options = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname + url.search,
      method,
      headers: { "Content-Type": "application/json", ...config.aelliAuthHeaders() },
    };

    const req = lib.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try { resolve(JSON.parse(data)); } catch { resolve(data); }
      });
    });

    req.setTimeout(30_000, () => req.destroy());
    req.on("error", reject);
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

async function updateTask(taskId, state, artifact = null) {
  const body = { state };
  if (artifact) body.artifact = artifact;
  return request("POST", `/a2a/tasks/${taskId}/update`, body);
}

function _connectSSE(urlStr, headers, onEvent, reconnectMs = 3000, onConnected = null) {
  const url = new URL(urlStr);
  const isHttps = url.protocol === "https:";
  const lib = isHttps ? https : http;

  const options = {
    hostname: url.hostname,
    port: url.port || (isHttps ? 443 : 80),
    path: url.pathname + url.search,
    method: "GET",
    headers: { Accept: "text/event-stream", ...headers },
  };

  const req = lib.request(options, (res) => {
    if (onConnected) onConnected();
    let buffer = "";
    res.on("data", (chunk) => {
      buffer += chunk.toString();
      const { events, remainder } = parseSseEvents(buffer);
      buffer = remainder;
      for (const { event, data } of events) {
        onEvent(event, data);
      }
    });
    res.on("end", () => {
      logger.warn(`[AELLI SSE] connection closed — reconnecting in ${reconnectMs / 1000}s`);
      setTimeout(() => _connectSSE(urlStr, headers, onEvent, reconnectMs), reconnectMs);
    });
  });

  req.setTimeout(60_000, () => req.destroy());
  req.on("error", (e) => {
    const nextMs = Math.min(reconnectMs * 2, MAX_RECONNECT_MS);
    logger.error("[AELLI SSE] error:", e.message, `— reconnecting in ${nextMs / 1000}s`);
    setTimeout(() => _connectSSE(urlStr, headers, onEvent, nextMs, onConnected), nextMs);
  });
  req.end();
}

function subscribeToQueue(queueUrl, onTask) {
  if (typeof onTask !== "function") {
    throw new TypeError("[octowiz] subscribeToQueue() requires an onTask callback");
  }
  _connectSSE(
    queueUrl,
    config.queueAuthHeaders(),
    (event, data) => {
      if (event === "task-new" && data) {
        try {
          const task = JSON.parse(data);
          Promise.resolve(onTask(task)).catch((e) =>
            logger.error("[octowiz] Task processing failed:", e.message)
          );
        } catch (e) {
          logger.warn("[octowiz] Parse error:", e.message);
        }
      }
    },
    3000,
    () => logger.log(`[octowiz] Daemon subscribed to ${queueUrl}`)
  );
}

// Post an event to the dev-advisor.
//
// fire-and-forget (sync=false, default): returns null immediately; the fetch
// runs in the background and all errors are silently dropped.
//
// advice (sync=true): waits up to timeoutMs for a response artifact.
// On timeout or any network error: logs locally and returns null (fail-open —
// the caller proceeds without advice rather than blocking).
async function post(eventType, data, { sync = false, timeoutMs = 2000 } = {}) {
  const url = config.devAdvisorUrl();

  const init = _jsonInit({
    jsonrpc: "2.0",
    method: "message/send",
    params: {
      message: {
        role: "user",
        messageId: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        parts: [{ kind: "text", text: JSON.stringify({ type: eventType, ...data }) }],
      },
    },
  });

  if (!sync) {
    fetch(url, init).catch((err) =>
      appendLog(`[post:${eventType}] fire-and-forget error: ${err?.message ?? err}`)
    );
    return null;
  }

  const [res, err] = await _abortFetch(url, init, timeoutMs);
  if (!res) {
    appendLog(`[post:${eventType}] fail-open: ${err?.message ?? err}`);
    return null;
  }
  try {
    const rpc = await res.json();
    const text = rpc?.result?.artifacts?.[0]?.parts?.[0]?.text;
    return text ? JSON.parse(text) : null;
  } catch (err) {
    appendLog(`[post:${eventType}] fail-open: ${err?.message ?? err}`);
    return null;
  }
}

// Synchronous routing decision — returns { router, tier, model, workflow } or null (fail-open).
//
// The router endpoint emits an SSE stream terminated by `data: [DONE]`.
// We use parseSseEvents() for correct multi-line / CRLF handling, skip preamble
// events whose data can't be parsed as JSON, skip the sentinel `[DONE]` line,
// and return the first successfully parsed object (the routing decision).
async function route(taskKind, data = {}, { timeoutMs = 2000 } = {}) {
  const routerUrl = config.routerUrl();
  if (!routerUrl) return null;
  const init = _jsonInit({
    jsonrpc: "2.0",
    method: "message/send",
    params: { message: { parts: [{ kind: "text", text: JSON.stringify({
      type: "route", taskKind, ...data,
    }) }] } },
  });
  const [res, err] = await _abortFetch(routerUrl, init, timeoutMs);
  if (!res) {
    appendLog(`[route:${taskKind}] fail-open: ${err?.message ?? err}`);
    return null;
  }
  try {
    const text = await res.text();
    if (!text) return null;
    // Ensure the buffer is terminated with a blank line so parseSseEvents emits
    // the last event (router often sends a single event without a trailing \n\n).
    const buf = text.endsWith("\n\n") ? text : text + "\n\n";
    const { events } = parseSseEvents(buf);
    for (const { data: raw } of events) {
      if (!raw || raw === "[DONE]") continue;
      try { return JSON.parse(raw); } catch { /* skip non-JSON / preamble lines */ }
    }
    return null;
  } catch (err) {
    appendLog(`[route:${taskKind}] fail-open: ${err?.message ?? err}`);
    return null;
  }
}

module.exports = { subscribeToQueue, post, route, parseSseEvents, updateTask };
