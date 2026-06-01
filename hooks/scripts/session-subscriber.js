#!/usr/bin/env node
"use strict";
// Per-session background process: placeholder for AELLI per-session push tasks.
// Not spawned until /a2a/tasks/subscribe is implemented; re-enable spawnSubscriber()
// in hooks/scripts/start.js when the endpoint is wired.
require("../../src/session-subscriber");
