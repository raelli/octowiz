"use strict";
const { version } = require("./package.json");
const daemon = require("./src/daemon");

// Daemon only — start once out-of-band (node index.js or make start).
// Per-session push subscriptions run via hooks/scripts/session-subscriber.js.
async function start() {
  daemon.start();
  console.log(`[octowiz v${version}] daemon ready`);
  console.log("plugin-ready");
  setInterval(() => {}, 60_000);
}

start().catch((e) => {
  console.error("[octowiz] Start error:", e.message);
  process.exit(1);
});
