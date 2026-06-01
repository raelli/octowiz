const http = require("http");
const https = require("https");
const { subscribeToQueue } = require("./a2a-client");
const { checkStartup, validateCwd } = require("./policy");
const { claimTask, postResult } = require("./task-queue-client");

const QUEUE_URL = `${(process.env.AELLI_BASE_URL || "http://localhost:3456").replace(/\/$/, "")}/a2a/task-queue`;

// The daemon now forwards all capability work to the Python A2A server.
// Build the base URL from OCTOWIZ_A2A_URL, or fall back to localhost on
// OCTOWIZ_A2A_PORT (default 8765).
function _a2aBaseUrl() {
  if (process.env.OCTOWIZ_A2A_URL) {
    return process.env.OCTOWIZ_A2A_URL.replace(/\/$/, "");
  }
  const port = process.env.OCTOWIZ_A2A_PORT || "8765";
  return `http://localhost:${port}`;
}

// The Python A2A server authenticates via x-octowiz-secret.
const OCTOWIZ_SECRET = process.env.OCTOWIZ_INBOUND_SECRET || "";

// OCTOWIZ_DISPATCH_TIMEOUT is in *seconds* (matching Python's dispatch.py).
// The daemon's HTTP timeout must exceed the Python ceiling so we never abort
// a POST before Python finishes.  Add a 30 s buffer.
const _dispatchTimeoutSec = parseInt(process.env.OCTOWIZ_DISPATCH_TIMEOUT || "300", 10);
const A2A_TIMEOUT_MS = _dispatchTimeoutSec * 1000 + 30_000;

const KNOWN_CAPABILITIES = new Set([
  "octowiz.dispatch",
  "octowiz.advise",
  "octowiz.manage_agents",
]);

/**
 * Forward a capability task to the Python A2A server via JSON-RPC 2.0 and
 * return the artifact object (whatever the Python handler returned).
 *
 * Throws on network errors or non-200 HTTP responses so processTask can catch
 * and postResult with an error.
 */
function _forwardToA2A(capability, payload) {
  return new Promise((resolve, reject) => {
    const baseUrl = _a2aBaseUrl();
    const url = new URL(baseUrl + "/a2a/octowiz");
    const isHttps = url.protocol === "https:";
    const lib = isHttps ? https : http;

    // The inner event text must include `capability` so Python dispatch.py can
    // route it, plus all payload fields (task, cwd, operation, sessionId, ...).
    const innerEvent = { capability, ...payload };

    const rpcBody = JSON.stringify({
      jsonrpc: "2.0",
      method: "octowiz/event",
      id: `daemon-${Date.now()}`,
      params: {
        message: {
          parts: [{ kind: "text", text: JSON.stringify(innerEvent) }],
        },
      },
    });

    const options = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(rpcBody),
        "x-octowiz-secret": OCTOWIZ_SECRET,
      },
    };

    const req = lib.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        if (res.statusCode !== 200) {
          return reject(new Error(`A2A server returned HTTP ${res.statusCode}: ${data.slice(0, 200)}`));
        }
        try {
          const rpc = JSON.parse(data);
          // Extract artifact from JSON-RPC 2.0 response.
          // make_response() shape: result.artifacts[0].parts[0].text
          const text = rpc?.result?.artifacts?.[0]?.parts?.[0]?.text;
          const artifact = text ? JSON.parse(text) : {};
          resolve(artifact);
        } catch (err) {
          reject(new Error(`Failed to parse A2A response: ${err.message}`));
        }
      });
    });

    req.setTimeout(A2A_TIMEOUT_MS, () => {
      req.destroy(new Error(`A2A forward timed out after ${A2A_TIMEOUT_MS}ms`));
    });
    req.on("error", reject);
    req.write(rpcBody);
    req.end();
  });
}

async function processTask(task) {
  const { id, capability, payload = {} } = task;

  const claim = await claimTask(id);
  if (!claim.ok) {
    // 409 = another instance claimed it; silently skip
    return;
  }
  const { leaseToken } = claim;

  if (!KNOWN_CAPABILITIES.has(capability)) {
    await postResult(id, leaseToken, { status: "error", message: `unknown capability: ${capability}` });
    return;
  }

  // CWD validation is a security boundary that stays in the daemon even though
  // Python also validates cwd. This ensures bad paths are rejected before they
  // ever leave the trusted JS process.
  if (payload.cwd) {
    try { payload.cwd = validateCwd(payload.cwd); }
    catch (err) {
      await postResult(id, leaseToken, { status: "error", message: err.message });
      return;
    }
  }

  try {
    const artifact = await _forwardToA2A(capability, payload);
    const normalized = artifact || { status: "completed" };
    // Normalize: Python capabilities use "error" for failures; queue needs
    // "completed" vs "error".
    const queueStatus = normalized.status === "error" ? "error" : "completed";
    await postResult(id, leaseToken, { ...normalized, status: queueStatus });
  } catch (err) {
    console.error(`[octowiz] forward to A2A server failed for ${capability}:`, err.message);
    await postResult(id, leaseToken, { status: "error", message: err.message });
  }
}

function start() {
  checkStartup();
  subscribeToQueue(QUEUE_URL, processTask);
  console.log(`[octowiz] Subscribed to task queue at ${QUEUE_URL}`);
}

module.exports = { start, processTask, _forwardToA2A };
