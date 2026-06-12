const logger = require("./logger");
const { subscribeToQueue } = require("./a2a-client");
const { checkStartup, validateCwd } = require("./policy");
const { claimTask, postResult } = require("./task-queue-client");
const { normalizeA2AResponse } = require("./a2a-response");
const { sendEvent } = require("./a2a-transport");
const config = require("./config");

const ALLOWED_ADVISORY_TYPES = new Set(["file-conflict", "branch-drift", "spec-deviation"]);

const KNOWN_CAPABILITIES = new Set([
  "octowiz.dispatch",
  "octowiz.manage_agents",
  "octowiz.observe",
  "octowiz.load_memory",
  "octowiz.escalate_to_aelli",
  "octowiz.plan",
  "octowiz.review",
  "octowiz.write_diary",
  "octowiz.run_sandboxed",
  "octowiz.marketplace_info",
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
  // The inner event must include `capability` so Python dispatch.py can route
  // it, plus all payload fields (task, cwd, operation, sessionId, ...).
  // capability is placed last so a payload.capability field from an untrusted
  // queue task cannot override the validated outer capability (P2 security fix).
  return sendEvent(`${config.a2aServerUrl()}/a2a/octowiz`, {
    method: "octowiz/event",
    id: `daemon-${Date.now()}`,
    payload: { ...payload, capability },
    headers: config.a2aServerAuthHeaders(),
    timeoutMs: config.a2aTimeoutMs(),
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
    logger.log(`[octowiz - observe] advisory for session ${sessionId}: ${advisory.type} — ${advisory.message}`);
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
    logger.error(`[octowiz - forward] A2A server failed for ${capability}:`, err.message);
    await postResult(id, leaseToken, { status: "error", message: err.message });
  }
}

function start() {
  checkStartup();
  const queueUrl = config.queueUrl();
  subscribeToQueue(queueUrl, processTask);
  logger.log(`[octowiz - startup] subscribed to task queue at ${queueUrl}`);
}

module.exports = { start, processTask, _forwardToA2A };
