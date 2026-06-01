const { ClaudeCliAdapter } = require("./cli-adapter");
const owners = require("../session-owners");

const DEFAULT_POLL_INTERVAL = parseInt(process.env.OCTOWIZ_DISPATCH_POLL_INTERVAL || "5000", 10);
const DEFAULT_TIMEOUT = parseInt(process.env.OCTOWIZ_DISPATCH_TIMEOUT || "300000", 10);
const TERMINAL_STATES = new Set(["stopped", "idle"]);

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function handleDispatch(event, { adapter, principal = "", pollInterval, timeout } = {}) {
  const { task, cwd } = event;
  if (!task) return { status: "error", message: "task is required" };
  if (!cwd) return { status: "error", message: "cwd is required" };
  if (task.startsWith("-")) return { status: "error", message: "task must not start with '-'" };

  if (!adapter) adapter = new ClaudeCliAdapter();
  const _poll = pollInterval ?? DEFAULT_POLL_INTERVAL;
  const _timeout = timeout ?? DEFAULT_TIMEOUT;

  const started = adapter.startSession(task, cwd);
  if (!started.ok) return { status: "error", message: `failed to start session: ${started.error}` };

  const { sessionId } = started;
  owners.register(sessionId, principal);

  const deadline = Date.now() + _timeout;
  while (Date.now() < deadline) {
    await sleep(_poll);
    const sessions = adapter.listSessions();
    const session = sessions.find((s) => s.sessionId === sessionId || s.sessionId.startsWith(sessionId));
    if (!session) continue;

    if (session.needsInput) {
      let output = "";
      try {
        output = adapter.control("logs", sessionId);
      } catch {}
      return { status: "needs-input", sessionId, output };
    }
    if (TERMINAL_STATES.has(session.status)) {
      let output = "";
      try {
        output = adapter.control("logs", sessionId);
      } catch {}
      return { status: "completed", sessionId, output };
    }
    if (session.status === "error") {
      let output = "";
      try {
        output = adapter.control("logs", sessionId);
      } catch {}
      return { status: "error", sessionId, output };
    }
  }
  return { status: "error", sessionId, message: `timeout after ${_timeout}ms waiting for session to complete` };
}

module.exports = { handleDispatch };
