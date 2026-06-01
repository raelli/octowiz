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

// Notify the Octowiz Python A2A server directly so StoreRegistry.drop() fires
// and per-session memory is freed. This is separate from the AELLI notification
// below because a2a-client.post() routes to AELLI (port 3456), not the Python
// server (OCTOWIZ_A2A_PORT, default 8765).
async function notifyOctowizServer(sessionId, ctx) {
  const base = process.env.OCTOWIZ_A2A_URL ||
    `http://localhost:${process.env.OCTOWIZ_A2A_PORT || "8765"}`;
  const secret = process.env.OCTOWIZ_INBOUND_SECRET || "";
  const body = JSON.stringify({
    jsonrpc: "2.0",
    method: "octowiz/event",
    id: `stop-${sessionId}`,
    params: {
      message: {
        parts: [{ kind: "text", text: JSON.stringify({
          type: "session-end",
          sessionId,
          repo: ctx?.repo,
          repoRoot: ctx?.repoRoot,
        }) }],
      },
    },
  });
  await fetch(`${base}/a2a/octowiz`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-octowiz-secret": secret },
    body,
    signal: AbortSignal.timeout(500),
  });
}

async function handleStop(input) {
  const { post } = require("../../src/a2a-client");
  const { getContext } = require("../../src/git-context");

  const sessionId = input.session_id || "";
  if (!sessionId) return;

  killSubscriber(sessionId);

  const ctx = getContext(sessionId);

  // Notify AELLI (advisory history, telemetry)
  await post(
    "session-end",
    { sessionId, repo: ctx?.repo, repoRoot: ctx?.repoRoot },
    { sync: true, timeoutMs: 500 }
  ).catch(() => {});

  // Notify Octowiz Python server (StoreRegistry cleanup)
  await notifyOctowizServer(sessionId, ctx).catch(() => {});
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
