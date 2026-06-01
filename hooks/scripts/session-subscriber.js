#!/usr/bin/env node
"use strict";
// Per-session background process: placeholder for AELLI per-session push tasks.
// Spawned detached by hooks/scripts/start.js. PTY_SESSION_ID must be set by caller.
require("../../src/session-subscriber");
// Keep alive for when per-session SSE push is wired to /a2a/tasks/subscribe.
setInterval(() => {}, 60_000);
