const { ClaudeCliAdapter } = require("./cli-adapter");
const { validateCwd } = require("../policy");
const owners = require("../session-owners");

const CONTROL_OPS = new Set(["logs", "stop", "rm", "respawn"]);
const SESSION_ID_RE = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;

async function handleManageAgents(event, adapter) {
  if (!adapter) adapter = new ClaudeCliAdapter();
  const { operation } = event;

  if (operation === "list") return handleList(event, adapter);
  if (CONTROL_OPS.has(operation)) return handleControl(operation, event, adapter);
  return { status: "error", message: `unknown operation: ${operation}` };
}

function handleList(event, adapter) {
  const { cwd } = event;
  if (cwd) {
    try {
      validateCwd(cwd);
    } catch (e) {
      return { status: "error", message: e.message };
    }
  }
  let sessions;
  try {
    sessions = adapter.listSessions(cwd);
  } catch {
    sessions = [];
  }
  if (!Array.isArray(sessions)) sessions = [];
  return { status: "ok", sessions };
}

function handleControl(op, event, adapter) {
  const { sessionId = "", _principal = "" } = event;
  if (!SESSION_ID_RE.test(sessionId)) {
    return { status: "error", message: `invalid sessionId: ${sessionId}` };
  }
  if (!owners.check(sessionId, _principal)) {
    return { status: "error", message: `session "${sessionId}" is not owned by this caller` };
  }
  let output;
  try {
    output = adapter.control(op, sessionId);
  } catch (e) {
    return { status: "error", message: e.message };
  }
  if (op === "rm") owners.deregister(sessionId);
  return { status: "ok", output };
}

module.exports = { handleManageAgents };
