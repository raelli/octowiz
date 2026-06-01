const { execFileSync } = require("child_process");

const ANSI_RE = /\x1b\[[0-9;]*[a-zA-Z]/g;
const SESSION_RE = /backgrounded\s*[·•]\s*(\S+)/;
const SESSION_ID_RE = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;

function defaultRunner(args, cwd) {
  try {
    const out = execFileSync(args[0], args.slice(1), {
      stdio: ["ignore", "pipe", "pipe"],
      timeout: 30_000,
      encoding: "utf8",
      cwd: cwd || undefined,
    });
    return [0, out.trim(), ""];
  } catch (err) {
    return [err.status || 1, (err.stdout || "").trim(), (err.stderr || "").trim()];
  }
}

function parseSession(item) {
  return {
    sessionId: item.sessionId || item.id || "",
    cwd: item.cwd || item.repoRoot || "",
    startedAt: item.startedAt || item.createdAt || null,
    status: item.status || "",
    needsInput: Boolean(item.needsInput),
  };
}

class ClaudeCliAdapter {
  constructor(runner) {
    this._runner = runner || defaultRunner;
  }

  startSession(task, cwd, name) {
    if (!task || task.startsWith("-")) throw new Error(`Invalid task: ${task}`);
    const args = ["claude", "--bg"];
    if (name) args.push("--name", String(name));
    args.push("--", task);
    const [rc, stdout, stderr] = this._runner(args, cwd);
    if (rc !== 0) return { ok: false, error: stderr || `claude --bg exited ${rc}` };
    const clean = stdout.replace(ANSI_RE, "");
    const m = SESSION_RE.exec(clean);
    if (!m) return { ok: false, error: `could not parse session ID from output: ${clean.slice(0, 100)}` };
    return { ok: true, sessionId: m[1] };
  }

  listSessions(cwd) {
    const args = ["claude", "agents", "--json"];
    if (cwd) args.push("--cwd", cwd);
    const [rc, stdout] = this._runner(args, null);
    if (rc !== 0) return [];
    try {
      const items = JSON.parse(stdout || "[]");
      return Array.isArray(items) ? items.map(parseSession) : [];
    } catch {
      return [];
    }
  }

  control(op, sessionId) {
    if (!SESSION_ID_RE.test(sessionId)) throw new Error(`Invalid sessionId: ${sessionId}`);
    const [rc, stdout, stderr] = this._runner(["claude", op, "--", sessionId], null);
    if (rc !== 0) throw new Error(stderr || `claude ${op} exited ${rc}`);
    return stdout;
  }
}

module.exports = { ClaudeCliAdapter };
