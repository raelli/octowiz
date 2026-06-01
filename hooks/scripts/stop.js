#!/usr/bin/env node
"use strict";

async function handleStop(input) {
  const { post } = require("../../src/a2a-client");
  const { getContext } = require("../../src/git-context");

  const sessionId = input.session_id || "";
  if (!sessionId) return;

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
