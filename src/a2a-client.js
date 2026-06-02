const http = require("http");
const https = require("https");
const fs = require("fs");
const os = require("os");
const path = require("path");

const API_BASE = process.env.AELLI_BASE_URL || process.env.AELLI_API_BASE || "http://localhost:3001/api";
const SESSION_ID = process.env.PTY_SESSION_ID || "";
const AUTH_TOKEN = process.env.AELLI_AUTH_TOKEN || "";

function isLocalhost(urlStr) {
  try {
    const h = new URL(urlStr).hostname;
    return h === "localhost" || h === "127.0.0.1" || h === "::1" || h === "[::1]";
  } catch { return false; }
}

// AELLI_LITELLM_BASE: route through LiteLLM A2A gateway
// AELLI_DEV_ADVISOR_URL: direct call to dev-advisor (local default)
const LITELLM_BASE = process.env.AELLI_LITELLM_BASE || "";
const DEV_ADVISOR_URL =
  process.env.AELLI_DEV_ADVISOR_URL || "http://localhost:3456/a2a/dev-advisor";
const ROUTER_URL = process.env.AELLI_ROUTER_URL
  || (LITELLM_BASE ? `${LITELLM_BASE}/a2a/aelli-router/message/send` : null);

// Warn when sending credentials over non-localhost plain HTTP
if (AUTH_TOKEN) {
  const urlsToCheck = [
    ["AELLI_API_BASE", API_BASE],
    ...(LITELLM_BASE ? [["AELLI_LITELLM_BASE", LITELLM_BASE]] : []),
    ["AELLI_DEV_ADVISOR_URL", DEV_ADVISOR_URL],
  ];
  for (const [name, url] of urlsToCheck) {
    if (!url.startsWith("https://") && !isLocalhost(url)) {
      console.warn(
        `[AELLI A2A] Warning: AELLI_AUTH_TOKEN is set but ${name} uses plain HTTP on a non-localhost address. Use HTTPS to protect your token.`
      );
    }
  }
}

const LOG_FILE = path.join(
  process.env.AELLI_CACHE_DIR || path.join(os.homedir(), ".cache", "aelli-cc"),
  "aelli-cc.log"
);

function appendLog(msg) {
  try {
    fs.appendFileSync(LOG_FILE, `[${new Date().toISOString()}] ${msg}\n`);
  } catch {}
}

function makeAuthHeaders() {
  if (!AUTH_TOKEN) return {};
  return LITELLM_BASE
    ? { "Authorization": `Bearer ${AUTH_TOKEN}` }
    : { "x-aelli-secret": AUTH_TOKEN };
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
    const url = new URL(API_BASE + urlPath);
    const isHttps = url.protocol === "https:";
    const lib = isHttps ? https : http;

    const options = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname + url.search,
      method,
      headers: { "Content-Type": "application/json", ...makeAuthHeaders() },
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
      console.warn(`[AELLI SSE] connection closed — reconnecting in ${reconnectMs / 1000}s`);
      setTimeout(() => _connectSSE(urlStr, headers, onEvent, reconnectMs), reconnectMs);
    });
  });

  req.setTimeout(60_000, () => req.destroy());
  req.on("error", (e) => {
    console.error("[AELLI SSE] error:", e.message, `— reconnecting in ${reconnectMs / 1000 + 2}s`);
    setTimeout(() => _connectSSE(urlStr, headers, onEvent, reconnectMs + 2000), reconnectMs + 2000);
  });
  req.end();
}

function subscribe(onTask) {
  if (typeof onTask !== "function") {
    throw new TypeError("[AELLI A2A] subscribe() requires an onTask callback function");
  }
  if (!SESSION_ID) {
    console.warn("[AELLI A2A] PTY_SESSION_ID not set — SSE subscription skipped");
    return;
  }
  _connectSSE(
    `${API_BASE}/a2a/tasks/subscribe?sessionId=${SESSION_ID}`,
    makeAuthHeaders(),
    (event, data) => {
      if (event === "task-new" && data) {
        try {
          const task = JSON.parse(data);
          Promise.resolve(onTask(task)).catch((e) =>
            console.error("[AELLI A2A] Task processing failed:", e.message)
          );
        } catch (e) {
          console.warn("[AELLI A2A] Parse error:", e.message);
        }
      }
    },
    3000,
    () => console.log(`[AELLI A2A] SSE connected (sessionId=${SESSION_ID})`)
  );
}

function subscribeToQueue(queueUrl, onTask) {
  if (typeof onTask !== "function") {
    throw new TypeError("[octowiz] subscribeToQueue() requires an onTask callback");
  }
  const secret = process.env.AELLI_AUTH_TOKEN || process.env.AELLI_INBOUND_SECRET || "";
  _connectSSE(
    queueUrl,
    { "x-aelli-secret": secret },
    (event, data) => {
      if (event === "task-new" && data) {
        try {
          const task = JSON.parse(data);
          Promise.resolve(onTask(task)).catch((e) =>
            console.error("[octowiz] Task processing failed:", e.message)
          );
        } catch (e) {
          console.warn("[octowiz] Parse error:", e.message);
        }
      }
    },
    3000,
    () => console.log(`[octowiz] Daemon subscribed to ${queueUrl}`)
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
  const url = LITELLM_BASE
    ? `${LITELLM_BASE}/a2a/aelli-dev-advisor/message/send`
    : DEV_ADVISOR_URL;

  const rpcBody = JSON.stringify({
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

  const init = {
    method: "POST",
    headers: { "Content-Type": "application/json", ...makeAuthHeaders() },
    body: rpcBody,
  };

  if (!sync) {
    fetch(url, init).catch((err) =>
      appendLog(`[post:${eventType}] fire-and-forget error: ${err?.message ?? err}`)
    );
    return null;
  }

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...init, signal: ctrl.signal });
    const rpc = await res.json();
    const text = rpc?.result?.artifacts?.[0]?.parts?.[0]?.text;
    return text ? JSON.parse(text) : null;
  } catch (err) {
    appendLog(`[post:${eventType}] fail-open: ${err?.message ?? err}`);
    return null;
  } finally {
    clearTimeout(timer);
  }
}

// Synchronous routing decision — returns { router, tier, model, workflow } or null (fail-open).
async function route(taskKind, data = {}, { timeoutMs = 2000 } = {}) {
  if (!ROUTER_URL) return null;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(ROUTER_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...makeAuthHeaders() },
      signal: ctrl.signal,
      body: JSON.stringify({
        jsonrpc: '2.0',
        method: 'message/send',
        params: { message: { parts: [{ kind: 'text', text: JSON.stringify({
          type: 'route', taskKind, ...data
        }) }] } },
      }),
    });
    // Router returns SSE — parse first data event
    const text = await res.text();
    const match = text.match(/^data: (.+)$/m);
    if (!match) return null;
    return JSON.parse(match[1]);
  } catch (err) {
    appendLog(`[route:${taskKind}] fail-open: ${err?.message ?? err}`);
    return null;
  } finally {
    clearTimeout(timer);
  }
}

module.exports = { subscribe, subscribeToQueue, post, route, parseSseEvents, updateTask, _connectSSE };
