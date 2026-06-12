#!/usr/bin/env node
"use strict";
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const net = require("net");
const logger = require("../../src/logger");

const CACHE_DIR = process.env.AELLI_CACHE_DIR || path.join(os.homedir(), ".cache", "aelli-cc");
const LOG_FILE = path.join(CACHE_DIR, "aelli-cc.log");

function appendLog(msg) {
  try {
    fs.mkdirSync(CACHE_DIR, { recursive: true });
    fs.appendFileSync(LOG_FILE, `[${new Date().toISOString()}] ${msg}\n`);
  } catch {}
}

function isPortOpen(port) {
  return new Promise((resolve) => {
    const s = net.createConnection({ port, host: "127.0.0.1" });
    s.on("connect", () => { s.destroy(); resolve(true); });
    s.on("error", () => resolve(false));
  });
}

async function ensureA2AServer() {
  const port = parseInt(process.env.OCTOWIZ_A2A_PORT || "8765", 10);
  if (await isPortOpen(port)) return;

  const pluginRoot = process.env.CLAUDE_PLUGIN_ROOT || path.join(__dirname, "../..");
  const agentDir = path.join(pluginRoot, "apps", "a2a-agent");
  if (!fs.existsSync(path.join(agentDir, "main.py"))) {
    appendLog("[start] a2a-agent not found — skipping Python server startup");
    return;
  }

  const child = spawn("python3", ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: agentDir,
    env: { ...process.env },
    detached: true,
    stdio: "ignore",
  });
  child.unref();
  fs.mkdirSync(CACHE_DIR, { recursive: true });
  fs.writeFileSync(path.join(CACHE_DIR, "a2a-agent.pid"), String(child.pid));
  appendLog(`[start] Python A2A server started on port ${port} (pid ${child.pid})`);
}

async function handleStart(input) {
  const { post } = require("../../src/a2a-client");
  const { captureContext, getLiveContext } = require("../../src/git-context");

  const sessionId = input.session_id || `cc-${Date.now()}-${process.pid}`;
  const cwd = input.cwd || process.cwd();

  logger.log("[octowiz - start] session starting", sessionId);

  if (!process.env.AELLI_AUTH_TOKEN) {
    logger.warn("[octowiz - start] AELLI_AUTH_TOKEN not set — advisory delivery disabled");
    appendLog("[octowiz - start] AELLI_AUTH_TOKEN not set — advisory delivery disabled");
  }

  await ensureA2AServer();

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

module.exports = { handleStart };
