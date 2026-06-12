#!/usr/bin/env node
"use strict";
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const net = require("net");
const logger = require("../../src/logger");
const config = require("../../src/config");

function appendLog(msg) {
  try {
    fs.mkdirSync(config.cacheDir(), { recursive: true });
    fs.appendFileSync(config.logFile(), `[${new Date().toISOString()}] ${msg}\n`);
  } catch {}
}

function isPortOpen(port) {
  return new Promise((resolve) => {
    const s = net.createConnection({ port, host: "127.0.0.1" });
    s.on("connect", () => { s.destroy(); resolve(true); });
    s.on("error", () => resolve(false));
  });
}

function _readPluginVersion(pluginRoot) {
  try {
    const raw = fs.readFileSync(path.join(pluginRoot, ".claude-plugin", "plugin.json"), "utf8");
    const version = JSON.parse(raw).version;
    return typeof version === "string" && version ? version : null;
  } catch {
    return null;
  }
}

async function _getJson(url, timeoutMs) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: ctrl.signal });
    let body = null;
    try { body = await res.json(); } catch {}
    return { status: res.status, body };
  } catch {
    return { status: null, body: null };
  } finally {
    clearTimeout(timer);
  }
}

// Classify whatever is listening on the A2A port (#116).
//
// The agent-card route has been public in every octowiz version, so it is the
// identity anchor: no card, no kill — a foreign service whose /health happens
// to return 200 must never be restarted. /health (public since 0.9.16) then
// settles fresh vs stale; an auth-gated /health behind a valid card is a
// pre-/health octowiz server, which is stale by definition.
async function _classifyA2AServer(port, expectedVersion, { timeoutMs = 2000 } = {}) {
  const base = `http://127.0.0.1:${port}`;
  const card = await _getJson(`${base}/a2a/octowiz/.well-known/agent.json`, timeoutMs);
  if (card.status === null) return "unknown";
  if (card.status !== 200) return "foreign";
  const health = await _getJson(`${base}/health`, timeoutMs);
  if (health.status === 200 && health.body && health.body.version === expectedVersion) {
    return "fresh";
  }
  return "stale";
}

// Default kill: verify the pid still belongs to our uvicorn ON THIS PORT
// before SIGTERM — pid files can outlive their process (crash, manual
// restart), and a recycled pid must never be hit. Requiring the configured
// port in the command line ties the recorded pid back to the listener that
// was actually probed.
function _killA2AServer(pid, port) {
  const { execFileSync } = require("child_process");
  let cmd = "";
  try {
    cmd = execFileSync("ps", ["-p", String(pid), "-o", "command="], { encoding: "utf8" });
  } catch {}
  if (!cmd.includes("uvicorn") || !cmd.includes(String(port))) {
    throw new Error(`pid ${pid} is not the uvicorn on port ${port} — refusing to kill`);
  }
  process.kill(pid, "SIGTERM");
}

// Concurrency note: two sessions starting at once can both classify the same
// server stale and race the restart. The loser's spawn fails to bind the busy
// port and exits; the winner serves. Degraded pid-file state self-heals on the
// next version skew, so no lock is taken here.
async function ensureA2AServer({
  killFn = _killA2AServer,
  spawnFn = spawn,
  waitMs = 250,
  waitTries = 20,
} = {}) {
  const port = config.a2aPort();
  const pluginRoot = process.env.CLAUDE_PLUGIN_ROOT || path.join(__dirname, "../..");

  if (await isPortOpen(port)) {
    const expectedVersion = _readPluginVersion(pluginRoot);
    if (!expectedVersion) return; // nothing to compare against — leave the server alone

    const state = await _classifyA2AServer(port, expectedVersion);
    if (state === "foreign") {
      appendLog(`[start] port ${port} serves a non-octowiz service — leaving it alone`);
      return;
    }
    if (state !== "stale") return; // fresh, or unreachable mid-probe

    // Stale octowiz server: only ever kill the pid we recorded at spawn time.
    let pid = NaN;
    try {
      pid = parseInt(fs.readFileSync(path.join(config.cacheDir(), "a2a-agent.pid"), "utf8").trim(), 10);
    } catch {}
    if (!Number.isInteger(pid) || pid <= 0) {
      appendLog(`[start] A2A server on port ${port} is stale but no pid file — not killing an unknown process`);
      return;
    }

    appendLog(`[start] A2A server version skew on port ${port} (want ${expectedVersion}) — restarting pid ${pid}`);
    try {
      killFn(pid, port);
    } catch (e) {
      appendLog(`[start] not restarting A2A server: ${e?.message ?? e}`);
      return;
    }

    let freed = false;
    for (let i = 0; i < waitTries; i++) {
      await new Promise((r) => setTimeout(r, waitMs));
      if (!(await isPortOpen(port))) { freed = true; break; }
    }
    if (!freed) {
      appendLog(`[start] port ${port} still busy after kill — skipping respawn`);
      return;
    }
  }

  const agentDir = path.join(pluginRoot, "apps", "a2a-agent");
  if (!fs.existsSync(path.join(agentDir, "main.py"))) {
    appendLog("[start] a2a-agent not found — skipping Python server startup");
    return;
  }

  const child = spawnFn("python3", ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: agentDir,
    env: { ...process.env },
    detached: true,
    stdio: "ignore",
  });
  child.unref();
  fs.mkdirSync(config.cacheDir(), { recursive: true });
  fs.writeFileSync(path.join(config.cacheDir(), "a2a-agent.pid"), String(child.pid));
  appendLog(`[start] Python A2A server started on port ${port} (pid ${child.pid})`);
}

async function ensureDaemonVersion({ sleepMs = 3000 } = {}) {
  const pluginRoot = process.env.CLAUDE_PLUGIN_ROOT;
  if (!pluginRoot) return;

  const plistPath = path.join(os.homedir(), "Library", "LaunchAgents", "de.integrahub.octowiz-daemon.plist");
  const newIndexJs = path.join(pluginRoot, "index.js");

  // Read what index.js the plist currently points at (= what version launchd will run).
  // This is the correct target: we're comparing/updating the Node daemon plist, not any
  // HTTP endpoint from the Python A2A server.
  let currentIndexJs;
  try {
    const { execFileSync } = require("child_process");
    currentIndexJs = execFileSync(
      "/usr/libexec/PlistBuddy",
      ["-c", "Print :ProgramArguments:1", plistPath],
      { encoding: "utf8" }
    ).trim();
  } catch {
    return; // plist absent, PlistBuddy missing, or key not found — skip
  }

  if (currentIndexJs === newIndexJs) return;

  appendLog(`[start] daemon path mismatch: plist=${currentIndexJs} plugin=${newIndexJs} — restarting daemon`);
  logger.log(`[octowiz - start] daemon path mismatch (${currentIndexJs} → ${newIndexJs}), restarting`);

  try {
    const { execFileSync } = require("child_process");
    execFileSync("launchctl", ["unload", plistPath], { stdio: "ignore" });
    execFileSync("/usr/libexec/PlistBuddy", ["-c", `Set :ProgramArguments:1 ${newIndexJs}`, plistPath], { stdio: "ignore" });
    execFileSync("launchctl", ["load", plistPath], { stdio: "ignore" });
    appendLog(`[start] daemon reloaded from ${newIndexJs}`);
    await new Promise((r) => setTimeout(r, sleepMs));
  } catch (e) {
    logger.warn("[octowiz - start] daemon restart failed:", e?.message ?? e);
    appendLog(`[start] daemon restart failed: ${e?.message ?? e}`);
  }
}

async function handleStart(input) {
  const { post } = require("../../src/a2a-client");
  const { captureContext, getLiveContext } = require("../../src/git-context");

  const sessionId = input.session_id || `cc-${Date.now()}-${process.pid}`;
  const cwd = input.cwd || process.cwd();

  logger.log("[octowiz - start] session starting", sessionId);

  if (!config.authToken()) {
    logger.warn("[octowiz - start] AELLI_AUTH_TOKEN not set — advisory delivery disabled");
    appendLog("[octowiz - start] AELLI_AUTH_TOKEN not set — advisory delivery disabled");
  }

  await ensureA2AServer();
  await ensureDaemonVersion();

  const ctx = captureContext(sessionId, cwd);
  const payload = { ...ctx, ...getLiveContext(sessionId) };
  await post("session-start", payload, { sync: true, timeoutMs: 500 }).catch((e) => {
    logger.error("[octowiz - start] session-start post failed:", e?.message ?? e);
    appendLog(`[octowiz - start] session-start post failed: ${e?.message ?? e}`);
  });

}

if (require.main === module) {
  let raw = "";
  process.stdin.on("data", (c) => (raw += c));
  process.stdin.on("end", async () => {
    let input = {};
    try { input = JSON.parse(raw); } catch {}
    try { await handleStart(input); } catch (e) {
      logger.error("[octowiz - start] error:", e.message);
      appendLog(`[start] error: ${e.message}`);
    }
    process.exit(0);
  });
}

module.exports = { handleStart, ensureDaemonVersion, ensureA2AServer };
