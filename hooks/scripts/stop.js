#!/usr/bin/env node
"use strict";
const fs = require("fs");
const path = require("path");
const logger = require("../../src/logger");
const { cacheDir } = require("../../src/config");

function killSubscriber(sessionId) {
  const pidFile = path.join(cacheDir(), `${sessionId}.pid`);
  if (!fs.existsSync(pidFile)) return;
  try {
    const pid = parseInt(fs.readFileSync(pidFile, "utf8").trim(), 10);
    if (!isNaN(pid)) process.kill(pid, "SIGTERM");
  } catch {}
  try { fs.unlinkSync(pidFile); } catch {}
}

async function handleStop(input) {
  const { post } = require("../../src/a2a-client");
  const { getStableContext } = require("../../src/git-context");

  const sessionId = input.session_id || "";
  if (!sessionId) return;

  logger.log("[octowiz - stop] session ending", sessionId);

  killSubscriber(sessionId);

  const ctx = getStableContext(sessionId);

  // Notify AELLI — advisory history, telemetry, and MemPalace session-end cleanup
  await post(
    "session-end",
    { sessionId, repo: ctx?.repo, repoRoot: ctx?.repoRoot },
    { sync: true, timeoutMs: 500 }
  ).catch(() => {});
}

if (require.main === module) {
  let raw = "";
  process.stdin.on("data", (c) => (raw += c));
  process.stdin.on("end", async () => {
    let input = {};
    try { input = JSON.parse(raw); } catch {}
    try { await handleStop(input); } catch {}
    process.exit(0);
  });
}

module.exports = { handleStop };
