#!/usr/bin/env node
"use strict";
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const CACHE_DIR = process.env.AELLI_CACHE_DIR || path.join(os.homedir(), ".cache", "aelli-cc");
const LOG_FILE = path.join(CACHE_DIR, "aelli-cc.log");

function appendLog(msg) {
  try {
    fs.mkdirSync(CACHE_DIR, { recursive: true });
    fs.appendFileSync(LOG_FILE, `[${new Date().toISOString()}] ${msg}\n`);
  } catch {}
}

function spawnSubscriber(sessionId) {
  const subscriberJs = path.join(__dirname, "session-subscriber.js");
  const child = spawn(process.execPath, [subscriberJs], {
    env: { ...process.env, PTY_SESSION_ID: sessionId },
    detached: true,
    stdio: "ignore",
  });
  child.unref();
  fs.mkdirSync(CACHE_DIR, { recursive: true });
  fs.writeFileSync(path.join(CACHE_DIR, `${sessionId}.pid`), String(child.pid));
}

async function handleStart(input) {
  const { post } = require("../../src/a2a-client");
  const { captureContext } = require("../../src/git-context");
  const { buildSessionStart } = require("../../src/event-builder");

  const sessionId = input.session_id || `cc-${Date.now()}-${process.pid}`;
  const cwd = input.cwd || process.cwd();

  if (!process.env.AELLI_LITELLM_BASE) {
    appendLog("[start] AELLI_LITELLM_BASE not set — session-start event will not be delivered");
  }
  if (!process.env.AELLI_AUTH_TOKEN) {
    appendLog("[start] AELLI_AUTH_TOKEN not set — session-start event will not be delivered");
  }

  const ctx = captureContext(sessionId, cwd);
  const payload = buildSessionStart(ctx);
  await post("session-start", payload, { sync: true, timeoutMs: 500 });

  spawnSubscriber(sessionId);
}

if (require.main === module) {
  let raw = "";
  process.stdin.on("data", (c) => (raw += c));
  process.stdin.on("end", async () => {
    let input = {};
    try { input = JSON.parse(raw); } catch {}
    try { await handleStart(input); } catch (e) {
      appendLog(`[start] error: ${e.message}`);
    }
    process.exit(0);
  });
}

module.exports = { handleStart };
