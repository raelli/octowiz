const https = require("https");
const http = require("http");
const logger = require("./logger");

const BASE = (process.env.AELLI_BASE_URL || "http://localhost:3456").replace(/\/$/, "");
const SECRET = process.env.AELLI_AUTH_TOKEN || process.env.AELLI_INBOUND_SECRET || "";

function _post(path, body) {
  return new Promise((resolve, reject) => {
    const url = new URL(BASE + path);
    const isHttps = url.protocol === "https:";
    const lib = isHttps ? https : http;
    const payload = JSON.stringify(body);
    const options = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(payload),
        "x-aelli-secret": SECRET,
      },
    };
    const req = lib.request(options, (res) => {
      let data = "";
      res.on("data", (c) => (data += c));
      res.on("end", () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(data) }); }
        catch { resolve({ status: res.statusCode, body: data }); }
      });
    });
    req.setTimeout(15_000, () => req.destroy());
    req.on("error", reject);
    req.write(payload);
    req.end();
  });
}

async function claimTask(taskId) {
  const { status, body } = await _post(`/a2a/task-queue/${taskId}/claim`, {});
  if (status === 200) return { ok: true, leaseToken: body.leaseToken };
  return { ok: false, reason: body.error || `HTTP ${status}` };
}

async function postResult(taskId, leaseToken, result) {
  let retries = 3;
  while (retries-- > 0) {
    try {
      const { status } = await _post(`/a2a/task-queue/${taskId}/result`, { leaseToken, ...result });
      if (status === 200 || status === 409) return; // 409 = late (lease expired or already done), discard
      if (status >= 500 && retries > 0) continue; // retry on server error
      return;
    } catch (err) {
      if (retries === 0) logger.error(`[daemon] postResult failed after retries: ${err.message}`);
    }
  }
}

module.exports = { claimTask, postResult };
