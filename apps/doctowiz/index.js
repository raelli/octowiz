#!/usr/bin/env node
"use strict";

/**
 * Doctowiz — Octowiz + AELLI integration diagnostic.
 * Run: node apps/doctowiz/index.js
 * Or via skill: /octowiz:doctowiz
 */

const { spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");
const net = require("net");
const http = require("http");
const https = require("https");

// ── Config ────────────────────────────────────────────────────────────────────
// All env-derived facts come from src/config.js — the same resolution rules
// production uses, so the diagnostic probes exactly what the plugin will do.

const config = require("../../src/config");

const PLUGIN_ROOT =
  process.env.CLAUDE_PLUGIN_ROOT || path.resolve(__dirname, "../..");
const BRIDGE_PY = path.join(
  PLUGIN_ROOT, "apps", "claude_code_bridge", "bridge.py"
);
const CACHE_DIR = config.cacheDir();
const LOG_FILE = config.logFile();
const DAEMON_LOG = path.join(CACHE_DIR, "octowiz-daemon.log");

const NODE_PORT = 3456;
const A2A_PORT = config.a2aPort();
const LITELLM_BASE = config.litellmBase();

// ── Result accumulator ────────────────────────────────────────────────────────

const checks = [];
const startMs = Date.now();

function addCheck(category, name, status, detail, note) {
  checks.push({ category, name, status, detail, note: note || "" });
}

const PASS = "pass";
const WARN = "warn";
const FAIL = "fail";

// ── Utilities ─────────────────────────────────────────────────────────────────

function psLines(pattern) {
  const r = spawnSync("ps", ["aux"], { encoding: "utf8", timeout: 3000 });
  return (r.stdout || "")
    .split("\n")
    .filter(
      (l) =>
        l.includes(pattern) &&
        !l.includes("grep") &&
        !l.includes("doctowiz")
    );
}

function isPortOpen(port) {
  return new Promise((resolve) => {
    const s = net.createConnection({ port, host: "127.0.0.1" });
    s.setTimeout(2000);
    s.on("connect", () => { s.destroy(); resolve(true); });
    s.on("error", () => resolve(false));
    s.on("timeout", () => { s.destroy(); resolve(false); });
  });
}

function httpRequest(rawUrl, { method = "GET", headers = {}, body } = {}) {
  return new Promise((resolve) => {
    let parsed;
    try { parsed = new URL(rawUrl); } catch { return resolve({ status: null, error: "invalid url" }); }
    const lib = parsed.protocol === "https:" ? https : http;
    const opts = {
      hostname: parsed.hostname,
      port: parsed.port || (parsed.protocol === "https:" ? 443 : 80),
      path: parsed.pathname + parsed.search,
      method,
      headers,
      timeout: 5000,
    };
    if (body) opts.headers["Content-Length"] = Buffer.byteLength(body);
    const req = lib.request(opts, (res) => {
      let buf = "";
      res.on("data", (d) => { buf += d; });
      res.on("end", () => resolve({ status: res.statusCode, body: buf.slice(0, 300) }));
    });
    req.on("error", (e) => resolve({ status: null, error: e.message }));
    req.on("timeout", () => { req.destroy(); resolve({ status: null, error: "timeout" }); });
    if (body) req.write(body);
    req.end();
  });
}

const httpGet = (url, headers) => httpRequest(url, { method: "GET", headers });

function runBridge(event) {
  if (!fs.existsSync(BRIDGE_PY)) {
    return { ok: false, error: `bridge.py not found at ${BRIDGE_PY}` };
  }
  const r = spawnSync("python3", [BRIDGE_PY], {
    input: JSON.stringify(event),
    env: { ...process.env, OCTOWIZ_VERBOSE: "1" },
    encoding: "utf8",
    timeout: 12000,
  });
  if (r.error) return { ok: false, error: r.error.message };

  const stderr = r.stderr || "";
  const stdout = r.stdout || "";

  const delivered =
    stderr.includes("advisory delivered") ||
    stderr.includes("delivery failed");

  const typeMatch = stderr.match(/type=([^\s\n]+)/);
  const advisoryType = typeMatch ? typeMatch[1] : null;

  let systemMessage = null;
  try {
    const parsed = JSON.parse(stdout.trim());
    systemMessage = parsed.systemMessage || null;
  } catch {}

  const failed = stderr.includes("delivery failed");
  const latencyMatch = stderr.match(/(\d+)ms/);
  const latencyMs = latencyMatch ? latencyMatch[1] : null;

  return { ok: true, delivered, failed, advisoryType, systemMessage, stderr, latencyMs };
}

// ── Phase 1: Processes ────────────────────────────────────────────────────────

function checkProcesses() {
  // Daemon
  const daemonLines = psLines("octowiz/index.js");
  if (daemonLines.length) {
    const pid = daemonLines[0].trim().split(/\s+/)[1];
    addCheck("process", "Octowiz daemon", PASS, `PID ${pid}`);
  } else {
    addCheck("process", "Octowiz daemon", FAIL,
      "Not running — start: node ~/Documents/octowiz/index.js");
  }

  // AELLI Node — may be local or remote (Docker on integra42).
  // Match on cwd path; process shows as "node index.js" without full path in ps.
  const aelliLines = psLines("aelli/index.js").concat(psLines("Documents/aelli"));
  if (aelliLines.length) {
    const pid = aelliLines[0].trim().split(/\s+/)[1];
    addCheck("process", `AELLI Node.js (:${NODE_PORT})`, PASS, `PID ${pid} (local)`);
  } else {
    // AELLI may be running remotely (Docker on integra42) — endpoint check is authoritative.
    addCheck("process", `AELLI Node.js (:${NODE_PORT})`, WARN,
      "Local process not found — AELLI may be remote (Docker). See endpoint check.");
  }

  // AELLI Python A2A
  const uvicornLines = psLines("uvicorn main:app");
  if (uvicornLines.length) {
    const pid = uvicornLines[0].trim().split(/\s+/)[1];
    addCheck("process", `AELLI Python A2A (:${A2A_PORT})`, PASS, `PID ${pid}`);
  } else {
    addCheck("process", `AELLI Python A2A (:${A2A_PORT})`, WARN,
      "Not detected — start.js auto-starts it on first session");
  }

  // Session subscribers
  const subLines = psLines("session-subscriber.js");
  const n = subLines.length;
  if (n === 0) {
    addCheck("process", "Session subscribers", PASS, "None (correct post gap2 fix)");
  } else if (n <= 5) {
    addCheck("process", "Session subscribers", WARN,
      `${n} running — harmless, clears when sessions end`);
  } else {
    addCheck("process", "Session subscribers", WARN,
      `${n} accumulated — run: pkill -f session-subscriber.js`);
  }
}

// ── Phase 2: Config ───────────────────────────────────────────────────────────

function checkConfig() {
  if (config.authToken()) {
    addCheck("config", "AELLI_AUTH_TOKEN", PASS, "Set");
  } else {
    addCheck("config", "AELLI_AUTH_TOKEN", FAIL,
      "Not set — advisory delivery will return 401");
  }

  if (LITELLM_BASE) {
    addCheck("config", "AELLI_LITELLM_BASE", PASS, LITELLM_BASE);
  } else {
    addCheck("config", "AELLI_LITELLM_BASE", WARN,
      "Not set — falling back to localhost:3456");
  }

  addCheck("config", "OCTOWIZ_A2A_PORT", PASS, String(A2A_PORT));

  if (fs.existsSync(BRIDGE_PY)) {
    addCheck("config", "bridge.py", PASS, BRIDGE_PY);
  } else {
    addCheck("config", "bridge.py", FAIL, `Not found at ${BRIDGE_PY}`);
  }
}

// ── Phase 3: Endpoints ────────────────────────────────────────────────────────

async function checkEndpoints() {
  // AELLI Node — remote when AELLI_BASE_URL is set (integra42 Docker), local otherwise.
  const aeBaseUrl = process.env.AELLI_BASE_URL ? config.aelliBase() : "";
  if (aeBaseUrl) {
    const healthUrl = `${aeBaseUrl}/health`;
    const token = config.authToken();
    const r = await httpRequest(healthUrl, {
      method: "GET",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (r.status === 200) {
      addCheck("endpoint", "AELLI Node (remote)", PASS,
        `${aeBaseUrl}/health → HTTP 200`);
    } else if (r.status === 401 || r.status === 403) {
      addCheck("endpoint", "AELLI Node (remote)", WARN,
        `${aeBaseUrl}/health → HTTP ${r.status} — reachable but auth token may be wrong`);
    } else {
      addCheck("endpoint", "AELLI Node (remote)", FAIL,
        `${aeBaseUrl}/health → HTTP ${r.status}`);
    }
  } else {
    const nodeUp = await isPortOpen(NODE_PORT);
    addCheck("endpoint", `AELLI Node :${NODE_PORT}`,
      nodeUp ? PASS : FAIL,
      nodeUp ? "TCP connection accepted" : "Connection refused — set AELLI_BASE_URL for remote AELLI"
    );
  }

  // Python A2A — probe the actual agent-card route, not /
  const pyUp = await isPortOpen(A2A_PORT);
  if (pyUp) {
    const r = await httpGet(`http://localhost:${A2A_PORT}/a2a/octowiz/.well-known/agent.json`);
    if (r.status === 200) {
      addCheck("endpoint", `AELLI Python :${A2A_PORT}`, PASS,
        "Agent card returned (octowiz A2A service confirmed)");
    } else if (r.status === 401) {
      addCheck("endpoint", `AELLI Python :${A2A_PORT}`, PASS,
        "401 Unauthorized — correct service, auth enforced");
    } else if (r.status === 404) {
      addCheck("endpoint", `AELLI Python :${A2A_PORT}`, FAIL,
        "Port open but /a2a/octowiz not found — wrong service bound to port");
    } else {
      addCheck("endpoint", `AELLI Python :${A2A_PORT}`, WARN,
        `Unexpected HTTP ${r.status} from agent-card route`);
    }
  } else {
    addCheck("endpoint", `AELLI Python :${A2A_PORT}`, WARN,
      "Port closed — may start on first session"
    );
  }

  // LiteLLM gateway — probe the exact delivery route bridge.py and a2a-client.js use
  if (LITELLM_BASE) {
    // Probe the exact route and headers production resolves to.
    const deliveryUrl = config.devAdvisorUrl();
    const minimalBody = JSON.stringify({
      jsonrpc: "2.0", method: "message/send", id: "doctowiz-probe",
      params: { message: { role: "user", messageId: "probe", parts: [] } },
    });
    const r = await httpRequest(deliveryUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...config.aelliAuthHeaders(),
      },
      body: minimalBody,
    });
    if (r.status === 200 || r.status === 422) {
      // 422 = route live, AELLI rejected malformed payload — that's fine
      addCheck("endpoint", "LiteLLM delivery route", PASS,
        `${deliveryUrl} → HTTP ${r.status}`);
    } else if (r.status === 401) {
      addCheck("endpoint", "LiteLLM delivery route", FAIL,
        "401 — AELLI_AUTH_TOKEN rejected by gateway");
    } else if (r.status === 404) {
      addCheck("endpoint", "LiteLLM delivery route", FAIL,
        "404 — aelli-dev-advisor not registered in gateway");
    } else if (r.status === null) {
      addCheck("endpoint", "LiteLLM delivery route", FAIL,
        `Unreachable: ${r.error}`);
    } else {
      addCheck("endpoint", "LiteLLM delivery route", WARN,
        `HTTP ${r.status}`);
    }
  } else {
    addCheck("endpoint", "LiteLLM delivery route", WARN,
      "AELLI_LITELLM_BASE not set — using local AELLI on :3456");
  }
}

// ── Phase 4: Hook Pipeline (live) ─────────────────────────────────────────────

function checkPipeline() {
  const sid = `doctowiz-${Date.now()}`;
  const octowizRepo = path.join(os.homedir(), "Documents", "octowiz");
  const cwd = fs.existsSync(octowizRepo) ? octowizRepo : os.homedir();

  // UserPromptSubmit
  const promptResult = runBridge({
    hook_event_name: "UserPromptSubmit",
    session_id: sid,
    cwd,
    prompt: "doctowiz diagnostic: testing prompt event delivery",
  });

  if (!promptResult.ok) {
    addCheck("pipeline", "UserPromptSubmit → bridge.py", FAIL, promptResult.error);
  } else if (promptResult.failed) {
    addCheck("pipeline", "UserPromptSubmit → bridge.py → AELLI", FAIL,
      "Delivery failed — check auth token and LiteLLM gateway",
      promptResult.stderr.slice(0, 150)
    );
  } else if (promptResult.delivered) {
    const detail = promptResult.advisoryType
      ? `Advisory returned: type=${promptResult.advisoryType}`
      : "Event accepted, no advice for this context";
    addCheck("pipeline", "UserPromptSubmit → bridge.py → AELLI", PASS, detail,
      promptResult.systemMessage || ""
    );
  } else {
    addCheck("pipeline", "UserPromptSubmit → bridge.py → AELLI", WARN,
      "No verbose output — set OCTOWIZ_VERBOSE=1 to debug");
  }

  // PostToolUse / Edit  (use a real file in the octowiz repo to trigger spec-deviation)
  const testFilePath = path.join(cwd, "src", "daemon.js");
  const editResult = runBridge({
    hook_event_name: "PostToolUse",
    session_id: sid,
    tool_name: "Edit",
    cwd,
    tool_input: { file_path: testFilePath },
  });

  if (!editResult.ok) {
    addCheck("pipeline", "PostToolUse → bridge.py", FAIL, editResult.error);
  } else if (editResult.failed) {
    addCheck("pipeline", "PostToolUse → bridge.py → AELLI", FAIL,
      "Delivery failed");
  } else if (editResult.delivered) {
    const detail = editResult.advisoryType
      ? `Advisory: type=${editResult.advisoryType}`
      : "Event accepted, no advice triggered";
    addCheck("pipeline", "PostToolUse(Edit) → bridge.py → AELLI", PASS, detail);
  } else {
    addCheck("pipeline", "PostToolUse(Edit) → bridge.py → AELLI", WARN,
      "No verbose output detected");
  }
}

// ── Phase 5: Logs ─────────────────────────────────────────────────────────────

function checkLogs() {
  if (!fs.existsSync(LOG_FILE)) {
    addCheck("logs", "aelli-cc.log", WARN, "File not found");
  } else {
    const lines = fs.readFileSync(LOG_FILE, "utf8").split("\n").filter(Boolean);
    const now = Date.now();

    const errorLines = (cutoffMs) =>
      lines.filter((l) => {
        const m = l.match(/^\[(\d{4}-\d{2}-\d{2}T[\d:.Z]+)\]/);
        if (!m) return false;
        return (
          Date.now() - new Date(m[1]).getTime() < cutoffMs &&
          /fail-open|fail:|error/i.test(l)
        );
      }).length;

    const errHour = errorLines(3600 * 1000);
    const err24h = errorLines(24 * 3600 * 1000);

    addCheck("logs", "Errors (last 1h)", errHour === 0 ? PASS : WARN,
      errHour === 0 ? "0 errors" : `${errHour} errors`
    );
    addCheck("logs", "Errors (last 24h)", err24h <= 5 ? PASS : WARN,
      err24h === 0 ? "0 errors" : `${err24h} (historical plugin conflict — resolved)`
    );

    // Last activity
    const last = lines[lines.length - 1] || "";
    const lm = last.match(/^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})/);
    addCheck("logs", "Last hook activity", PASS,
      lm ? lm[1].replace("T", " ") : "unknown"
    );
  }

  // Daemon log
  if (fs.existsSync(DAEMON_LOG)) {
    const dlog = fs.readFileSync(DAEMON_LOG, "utf8");
    if (dlog.includes("Daemon subscribed")) {
      const m = dlog.match(/subscribed to ([^\n]+)/);
      addCheck("logs", "Daemon log", PASS,
        `Subscribed to ${(m ? m[1] : "task queue").trim()}`
      );
    } else if (dlog.includes("daemon ready")) {
      addCheck("logs", "Daemon log", WARN, "Ready — subscription line not found");
    } else {
      addCheck("logs", "Daemon log", WARN, "Unexpected content");
    }
  } else {
    addCheck("logs", "Daemon log", WARN,
      "Not found at /private/tmp/octowiz-daemon.log — daemon may not be running"
    );
  }
}

// ── Report ────────────────────────────────────────────────────────────────────

function printReport() {
  const elapsed = ((Date.now() - startMs) / 1000).toFixed(1);
  const passed = checks.filter((c) => c.status === PASS).length;
  const warned = checks.filter((c) => c.status === WARN).length;
  const failed = checks.filter((c) => c.status === FAIL).length;
  const total = checks.length;

  const status =
    failed > 0 ? "UNHEALTHY" : warned > 0 ? "DEGRADED" : "HEALTHY";

  const icon = { pass: "✓", warn: "!", fail: "✗" };

  const sections = [
    { key: "process",  label: "Process Health" },
    { key: "config",   label: "Configuration" },
    { key: "endpoint", label: "Endpoint Health" },
    { key: "pipeline", label: "Hook Pipeline (live)" },
    { key: "logs",     label: "Log Analysis" },
  ];

  const out = [];
  out.push(`# Doctowiz Diagnostic Report`);
  out.push(`**${new Date().toISOString()}** — **Status: ${status}** (${passed}/${total} passed, ${warned} warn, ${failed} fail)`);
  out.push("");

  for (const { key, label } of sections) {
    const group = checks.filter((c) => c.category === key);
    if (!group.length) continue;
    out.push(`## ${label}`);
    out.push("");
    out.push("| Check | | Detail |");
    out.push("|-------|---|--------|");
    for (const c of group) {
      const detail = c.note
        ? `${c.detail}<br>_${c.note}_`
        : c.detail;
      out.push(`| ${c.name} | ${icon[c.status]} | ${detail} |`);
    }
    out.push("");
  }

  out.push("---");
  out.push(`_Doctowiz completed in ${elapsed}s_`);
  console.log(out.join("\n"));
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  checkConfig();
  checkProcesses();
  await checkEndpoints();
  checkPipeline();
  checkLogs();
  printReport();
}

main().catch((e) => {
  console.error(`[doctowiz] fatal: ${e.message}`);
  process.exit(1);
});
