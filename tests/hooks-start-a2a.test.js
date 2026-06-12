"use strict";
const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");

// Tests for ensureA2AServer's version-skew restart (#116).
//
// A fixture HTTP server plays the role of the running A2A service; a fixture
// plugin root provides .claude-plugin/plugin.json and apps/a2a-agent/main.py.
// killFn / spawnFn / wait timing are injected so no real process is touched.

function listen(handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

function octowizServer({ version, publicHealth = true }) {
  return listen((req, res) => {
    if (req.url === "/health") {
      if (!publicHealth) {
        res.writeHead(401, { "Content-Type": "application/json" });
        return res.end(JSON.stringify({ error: "Unauthorized" }));
      }
      res.writeHead(200, { "Content-Type": "application/json" });
      return res.end(JSON.stringify({ status: "ok", version }));
    }
    if (req.url === "/a2a/octowiz/.well-known/agent.json") {
      res.writeHead(200, { "Content-Type": "application/json" });
      return res.end(JSON.stringify({ name: "octowiz" }));
    }
    res.writeHead(404);
    res.end();
  });
}

function foreignServer() {
  return listen((req, res) => {
    if (req.url === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      return res.end(JSON.stringify({ status: "healthy" }));
    }
    res.writeHead(404);
    res.end();
  });
}

function makePluginRoot(version) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "octowiz-plugin-fixture-"));
  fs.mkdirSync(path.join(root, ".claude-plugin"), { recursive: true });
  fs.writeFileSync(
    path.join(root, ".claude-plugin", "plugin.json"),
    JSON.stringify({ name: "octowiz", version })
  );
  fs.mkdirSync(path.join(root, "apps", "a2a-agent"), { recursive: true });
  fs.writeFileSync(path.join(root, "apps", "a2a-agent", "main.py"), "# fixture\n");
  return root;
}

describe("ensureA2AServer version-skew restart", () => {
  let server;
  let savedEnv;

  beforeEach(() => {
    savedEnv = {
      OCTOWIZ_A2A_PORT: process.env.OCTOWIZ_A2A_PORT,
      CLAUDE_PLUGIN_ROOT: process.env.CLAUDE_PLUGIN_ROOT,
    };
  });

  afterEach((done) => {
    for (const [k, v] of Object.entries(savedEnv)) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
    if (server) {
      server.close(done);
      server = null;
    } else done();
  });

  async function run({ serverInstance, pluginVersion, pidFile = 12345 }) {
    server = serverInstance;
    if (server) {
      process.env.OCTOWIZ_A2A_PORT = String(server.address().port);
    }
    process.env.CLAUDE_PLUGIN_ROOT = makePluginRoot(pluginVersion);
    const config = require("../src/config");
    const pidPath = path.join(config.cacheDir(), "a2a-agent.pid");
    if (pidFile !== null) {
      fs.mkdirSync(config.cacheDir(), { recursive: true });
      fs.writeFileSync(pidPath, String(pidFile));
    } else {
      // The worker-shared cache dir may hold a pid file from a previous test.
      try { fs.unlinkSync(pidPath); } catch {}
    }

    const killed = [];
    const spawned = [];
    const killFn = (pid) => {
      killed.push(pid);
      // Simulate the process dying: free the port.
      if (server) {
        server.close();
        server = null;
      }
    };
    const spawnFn = (cmd, args, opts) => {
      spawned.push({ cmd, args, opts });
      return { pid: 99999, unref() {} };
    };

    const { ensureA2AServer } = require("../hooks/scripts/start");
    await ensureA2AServer({ killFn, spawnFn, waitMs: 10, waitTries: 20 });
    return { killed, spawned };
  }

  it("leaves a fresh same-version server untouched", async () => {
    const { killed, spawned } = await run({
      serverInstance: await octowizServer({ version: "1.2.3" }),
      pluginVersion: "1.2.3",
    });
    expect(killed).toEqual([]);
    expect(spawned).toEqual([]);
  });

  it("kills and respawns a stale octowiz server (version mismatch)", async () => {
    const { killed, spawned } = await run({
      serverInstance: await octowizServer({ version: "1.0.0" }),
      pluginVersion: "1.2.3",
    });
    expect(killed).toEqual([12345]);
    expect(spawned).toHaveLength(1);
    expect(spawned[0].args).toContain("uvicorn");
  });

  it("treats an auth-gated /health with a public agent card as a stale pre-/health octowiz server", async () => {
    const { killed, spawned } = await run({
      serverInstance: await octowizServer({ version: "0.9.13", publicHealth: false }),
      pluginVersion: "1.2.3",
    });
    expect(killed).toEqual([12345]);
    expect(spawned).toHaveLength(1);
  });

  it("never touches a foreign service on the port", async () => {
    const { killed, spawned } = await run({
      serverInstance: await foreignServer(),
      pluginVersion: "1.2.3",
    });
    expect(killed).toEqual([]);
    expect(spawned).toEqual([]);
  });

  it("does not kill when the server is stale but no pid file exists", async () => {
    const { killed, spawned } = await run({
      serverInstance: await octowizServer({ version: "1.0.0" }),
      pluginVersion: "1.2.3",
      pidFile: null,
    });
    expect(killed).toEqual([]);
    expect(spawned).toEqual([]);
  });

  it("refuses to kill when the recorded pid is not the uvicorn on the configured port", async () => {
    // Use the default killFn (pid verification via ps) against our own test
    // process pid — alive, but not a uvicorn — so the SIGTERM must be refused
    // and nothing respawned.
    server = await octowizServer({ version: "1.0.0" });
    process.env.OCTOWIZ_A2A_PORT = String(server.address().port);
    process.env.CLAUDE_PLUGIN_ROOT = makePluginRoot("1.2.3");
    const config = require("../src/config");
    fs.mkdirSync(config.cacheDir(), { recursive: true });
    fs.writeFileSync(path.join(config.cacheDir(), "a2a-agent.pid"), String(process.pid));

    const spawned = [];
    const spawnFn = (cmd, args) => {
      spawned.push({ cmd, args });
      return { pid: 99999, unref() {} };
    };
    const { ensureA2AServer } = require("../hooks/scripts/start");
    await ensureA2AServer({ spawnFn, waitMs: 10, waitTries: 2 });

    expect(spawned).toEqual([]); // refusal short-circuits before respawn
    // and we are still alive to assert it (no SIGTERM landed on this process)
  });

  it("spawns when the port is closed (existing behavior)", async () => {
    const closed = await listen(() => {});
    const port = closed.address().port;
    await new Promise((r) => closed.close(r)); // port now guaranteed free
    process.env.OCTOWIZ_A2A_PORT = String(port);
    const { killed, spawned } = await run({ serverInstance: null, pluginVersion: "1.2.3" });
    expect(killed).toEqual([]);
    expect(spawned).toHaveLength(1);
  });
});
