const { subscribe, updateTask } = require("./src/a2a-client");
const { version } = require("./package.json");
const daemon = require("./src/daemon");

if (!process.env.PTY_SESSION_ID) {
  process.env.PTY_SESSION_ID = `cc-${Date.now()}-${process.pid}`;
}

async function processMonitoringEvent(task) {
  console.log(`[AELLI A2A] Task received: ${task.id} — ${task.messages?.[0]?.parts?.[0]?.text?.slice(0, 60)}`);
  await updateTask(task.id, "working");
  await updateTask(task.id, "completed", {
    name: "aelli-response",
    parts: [{ kind: "text", text: "AELLI received the task." }],
  });
}

async function start() {
  subscribe(processMonitoringEvent);
  daemon.start();
  console.log(`[octowiz v${version}] ready (sessionId=${process.env.PTY_SESSION_ID})`);
  console.log("plugin-ready");
  setInterval(() => {}, 60_000);
}

start().catch((e) => {
  console.error("[octowiz] Start error:", e.message);
  process.exit(1);
});
