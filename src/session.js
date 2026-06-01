const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { captureContext, getContext } = require("./git-context");

const CACHE_DIR =
  process.env.AELLI_CACHE_DIR || path.join(os.homedir(), ".cache", "aelli-cc");

function pidFile(sessionId) {
  return path.join(CACHE_DIR, `aelli-cc.${sessionId}.pid`);
}

// Start a session: capture git context, spawn the background A2A subscriber,
// and persist the PID. Returns the captured session context object.
function start(sessionId, cwd) {
  fs.mkdirSync(CACHE_DIR, { recursive: true });

  // Kill any leftover subscriber from a previous run of this session
  const pf = pidFile(sessionId);
  if (fs.existsSync(pf)) {
    try {
      const old = parseInt(fs.readFileSync(pf, "utf8").trim(), 10);
      if (!isNaN(old)) process.kill(old, "SIGTERM");
    } catch {}
    try { fs.unlinkSync(pf); } catch {}
  }

  const ctx = captureContext(sessionId, cwd);

  const indexJs = path.join(__dirname, "..", "index.js");
  const child = spawn(process.execPath, [indexJs], {
    env: { ...process.env, PTY_SESSION_ID: sessionId },
    detached: true,
    stdio: "ignore",
  });
  child.unref();

  fs.writeFileSync(pf, String(child.pid));

  return ctx;
}

// Return the full session context (cached stable fields + live git state).
function get(sessionId) {
  return getContext(sessionId);
}

// Stop a session: kill the subscriber process and delete the cache.
function stop(sessionId) {
  const pf = pidFile(sessionId);
  if (fs.existsSync(pf)) {
    try {
      const pid = parseInt(fs.readFileSync(pf, "utf8").trim(), 10);
      if (!isNaN(pid)) process.kill(pid, "SIGTERM");
    } catch {}
    try { fs.unlinkSync(pf); } catch {}
  }

  const cacheFile = path.join(CACHE_DIR, `git-context-${sessionId}.json`);
  try { fs.unlinkSync(cacheFile); } catch {}
}

module.exports = { start, get, stop };
