const http = require("http");
const https = require("https");
const logger = require("./logger");
const { subscribeToQueue } = require("./a2a-client");
const { checkStartup, validateCwd } = require("./policy");
const { claimTask, postResult } = require("./task-queue-client");
const { normalizeA2AResponse } = require("./a2a-response");

const ALLOWED_ADVISORY_TYPES = new Set(["file-conflict", "branch-drift", "spec-deviation"]);

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
  "octowiz.manage_agents",
  "octowiz.observe",
  "router.validation-request",
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
    // capability is placed last so a payload.capability field from an untrusted
    // queue task cannot override the validated outer capability (P2 security fix).
    const innerEvent = { ...payload, capability };

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

  // octowiz.observe is handled locally — no A2A forwarding needed.
  // Log the advisory and echo it back as the artifact.
  if (capability === "octowiz.observe") {
    const { sessionId, advisory = {} } = payload;
    if (!ALLOWED_ADVISORY_TYPES.has(advisory.type)) {
      await postResult(id, leaseToken, { status: "error", failureKind: "unknown-advisory-type", type: advisory.type });
      return;
    }
    logger.log(`[octowiz] advisory for session ${sessionId}: ${advisory.type} — ${advisory.message}`);
    await postResult(id, leaseToken, { status: "completed", advisory });
    return;
  }

  // router.validation-request is handled locally: validate the draft and post
  // the result back so AELLI's onTaskComplete callback resolves the gate.
  // AELLI_VALIDATOR_PRINCIPAL must match the OCTOWIZ_INBOUND_SECRET value that
  // this daemon uses when authenticating to AELLI's task queue.
  if (capability === "router.validation-request") {
    const { validateJavaScriptSyntax } = require("./validation");
    const { workflowTaskId, draft = "" } = payload;
    // Validate payload shape before JS syntax check so callers get an explicit
    // error rather than an empty-draft failure for a missing field.
    if (typeof workflowTaskId !== "string" || typeof draft !== "string") {
      await postResult(id, leaseToken, { status: "completed", workflowTaskId, passed: false, failureKind: "invalid-payload" });
      return;
    }
    const validation = validateJavaScriptSyntax(draft);
    await postResult(id, leaseToken, {
      status: "completed",
      workflowTaskId,
      passed: validation.passed,
      ...(validation.failureKind ? { failureKind: validation.failureKind } : {}),
      ...(validation.output      ? { output: validation.output }           : {}),
    });
    return;
  }

  try {
    const artifact = await _forwardToA2A(capability, payload);
    // normalizeA2AResponse handles null/undefined (returns {}) and adds camelCase
    // aliases for any recognized snake_case fields (session_id → sessionId, etc.).
    const normalized = normalizeA2AResponse(artifact);
    // Normalize: Python capabilities use "error" for failures; queue needs
    // "completed" vs "error".
    const queueStatus = normalized.status === "error" ? "error" : "completed";
    await postResult(id, leaseToken, { ...normalized, status: queueStatus });
  } catch (err) {
    logger.error(`[octowiz] forward to A2A server failed for ${capability}:`, err.message);
    await postResult(id, leaseToken, { status: "error", message: err.message });
  }
}

function start() {
  checkStartup();
  subscribeToQueue(QUEUE_URL, processTask);
  logger.log(`[octowiz] Subscribed to task queue at ${QUEUE_URL}`);
}

module.exports = { start, processTask, _forwardToA2A };
