#!/usr/bin/env node
"use strict";
const fs = require("fs");
const os = require("os");
const path = require("path");

const CACHE_DIR = process.env.AELLI_CACHE_DIR || path.join(os.homedir(), ".cache", "aelli-cc");

function killSubscriber(sessionId) {
  const pidFile = path.join(CACHE_DIR, `${sessionId}.pid`);
  if (!fs.existsSync(pidFile)) return;
  try {
    const pid = parseInt(fs.readFileSync(pidFile, "utf8").trim(), 10);
    if (!isNaN(pid)) process.kill(pid, "SIGTERM");
  } catch {}
  try { fs.unlinkSync(pidFile); } catch {}
}

async function handleStop(input) {
  const { post } = require("../../src/a2a-client");
  const { getContext } = require("../../src/git-context");

  const sessionId = input.session_id || "";
  if (!sessionId) return;

  killSubscriber(sessionId);

  const ctx = getContext(sessionId);
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
