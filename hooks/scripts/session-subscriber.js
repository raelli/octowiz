#!/usr/bin/env node
"use strict";
// Per-session background process: subscribes to AELLI push tasks for this session.
// Spawned detached by hooks/scripts/start.js. PTY_SESSION_ID must be set by caller.
require("../../src/session-subscriber");
// Keep alive — subscribe() maintains an SSE connection and reconnects indefinitely
setInterval(() => {}, 60_000);
