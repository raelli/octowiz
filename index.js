"use strict";
const logger = require("./src/logger");
const { version } = require("./package.json");
const daemon = require("./src/daemon");

// Daemon only — start once out-of-band (node index.js or make start).
// Per-session push subscriptions are not yet implemented (subscribe endpoint pending).
async function start() {
  daemon.start();
  logger.log(`[octowiz v${version}] daemon ready`);
  console.log("plugin-ready");
  setInterval(() => {}, 60_000);
}

start().catch((e) => {
  logger.error("[octowiz] Start error:", e.message);
  process.exit(1);
});
