const { subscribeToQueue } = require("./a2a-client");
const { checkStartup, validateCwd } = require("./policy");
const { claimTask, postResult } = require("./task-queue-client");
const { handleDispatch } = require("./capabilities/dispatch");
const { handleAdvise } = require("./capabilities/advise");
const { handleManageAgents } = require("./capabilities/manage-agents");

const QUEUE_URL = `${(process.env.AELLI_BASE_URL || "http://localhost:3456").replace(/\/$/, "")}/a2a/task-queue`;

const HANDLERS = {
  "octowiz.dispatch": handleDispatch,
  "octowiz.advise": handleAdvise,
  "octowiz.manage_agents": handleManageAgents,
};

async function processTask(task) {
  const { id, capability, payload = {}, principal = "" } = task;

  const claim = await claimTask(id);
  if (!claim.ok) {
    // 409 = another instance claimed it; silently skip
    return;
  }
  const { leaseToken } = claim;

  const handler = HANDLERS[capability];
  if (!handler) {
    await postResult(id, leaseToken, { status: "error", message: `unknown capability: ${capability}` });
    return;
  }

  if (payload.cwd) {
    try { payload.cwd = validateCwd(payload.cwd); }
    catch (err) {
      await postResult(id, leaseToken, { status: "error", message: err.message });
      return;
    }
  }

  const enrichedPayload = { ...payload, _principal: principal };

  try {
    let result;
    if (capability === "octowiz.dispatch") {
      result = await handleDispatch(enrichedPayload, { principal });
    } else {
      result = await handler(enrichedPayload);
    }
    const normalized = result || { status: "completed" };
    // Normalize: capabilities use "ok" or omit status for success; queue needs "completed" vs "error"
    const queueStatus = normalized.status === "error" ? "error" : "completed";
    await postResult(id, leaseToken, { ...normalized, status: queueStatus });
  } catch (err) {
    console.error(`[octowiz] capability ${capability} threw:`, err.message);
    await postResult(id, leaseToken, { status: "error", message: err.message });
  }
}

function start() {
  checkStartup();
  subscribeToQueue(QUEUE_URL, processTask);
  console.log(`[octowiz] Subscribed to task queue at ${QUEUE_URL}`);
}

module.exports = { start, processTask };
