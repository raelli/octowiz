#!/usr/bin/env node
"use strict";

async function handleEvent(input) {
  const { post } = require("../../src/a2a-client");
  const { getContext } = require("../../src/git-context");
  const { buildFileEvent, buildPrompt } = require("../../src/event-builder");

  const sessionId = input.session_id || "";
  const toolName = input.tool_name || "";
  const ctx = getContext(sessionId);

  if (toolName) {
    const filePath = input.tool_input?.file_path || input.tool_input?.path || "";
    const payload = buildFileEvent(ctx, toolName, filePath);
    const eventType = toolName === "Write" ? "file-write" : "file-edit";
    await post(eventType, payload, { sync: false });
  } else {
    const prompt = input.prompt || input.message || "";
    const payload = buildPrompt(ctx, prompt);
    await post("prompt", payload, { sync: false });
  }
}

if (require.main === module) {
  let raw = "";
  process.stdin.on("data", (c) => (raw += c));
  process.stdin.on("end", async () => {
    let input = {};
    try { input = JSON.parse(raw); } catch {}
    try { await handleEvent(input); } catch {}
    process.exit(0);
  });
}

module.exports = { handleEvent };
