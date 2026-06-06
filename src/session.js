const fs = require("fs");
const os = require("os");
const path = require("path");
const { captureContext, getContext } = require("./git-context");

const CACHE_DIR =
  process.env.AELLI_CACHE_DIR || path.join(os.homedir(), ".cache", "aelli-cc");

function pidFile(sessionId) {
  return path.join(CACHE_DIR, `aelli-cc.${sessionId}.pid`);
}

// Start a session: capture git context and return the context object.
// The daemon is managed by launchd (de.integrahub.octowiz-daemon); no
// per-session process is spawned here.
function start(sessionId, cwd) {
  fs.mkdirSync(CACHE_DIR, { recursive: true });
  return captureContext(sessionId, cwd);
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
