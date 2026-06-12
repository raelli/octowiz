"use strict";

describe("hooks/scripts/start.js", () => {
  beforeEach(() => {
    jest.resetModules();
    process.env.AELLI_LITELLM_BASE = "https://llm.test";
    process.env.AELLI_AUTH_TOKEN = "tok";
    jest.mock("../src/a2a-client", () => ({ post: jest.fn().mockResolvedValue(null) }));
    jest.mock("../src/git-context", () => ({
      captureContext: jest.fn().mockReturnValue({
        sessionId: "s1", repoRoot: "/repo", repo: "origin", cwd: "/repo",
      }),
      getLiveContext: jest.fn().mockReturnValue({ branch: "main", modifiedFiles: [] }),
    }));
  });

  afterEach(() => {
    delete process.env.AELLI_LITELLM_BASE;
    delete process.env.AELLI_AUTH_TOKEN;
    jest.restoreAllMocks();
  });

  it("calls post with session-start and correct sessionId and branch", async () => {
    const { post: mockPost } = require("../src/a2a-client");
    const { handleStart } = require("../hooks/scripts/start");
    await handleStart({ session_id: "s1", cwd: "/repo" });
    expect(mockPost).toHaveBeenCalledWith(
      "session-start",
      expect.objectContaining({ sessionId: "s1", branch: "main" }),
      expect.objectContaining({ sync: true, timeoutMs: 500 })
    );
  });

  it("does not throw on missing AELLI_AUTH_TOKEN, appends warning to log", async () => {
    delete process.env.AELLI_AUTH_TOKEN;
    const fs = require("fs");
    const spy = jest.spyOn(fs, "appendFileSync").mockImplementation(() => {});
    jest.spyOn(fs, "mkdirSync").mockImplementation(() => {});
    const { handleStart } = require("../hooks/scripts/start");
    await expect(handleStart({ session_id: "s1", cwd: "/repo" })).resolves.not.toThrow();
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("aelli-cc.log"),
      expect.stringContaining("AELLI_AUTH_TOKEN")
    );
  });

  it("does not throw on empty stdin object", async () => {
    const { handleStart } = require("../hooks/scripts/start");
    await expect(handleStart({})).resolves.not.toThrow();
  });
});

describe("hooks/scripts/start.js — subscriber spawn", () => {
  let spawnMock, writeFileSyncMock;

  beforeEach(() => {
    jest.resetModules();
    process.env.AELLI_LITELLM_BASE = "https://llm.test";
    process.env.AELLI_AUTH_TOKEN = "tok";
    jest.mock("../src/a2a-client", () => ({ post: jest.fn().mockResolvedValue(null) }));
    jest.mock("../src/git-context", () => ({
      captureContext: jest.fn().mockReturnValue({
        sessionId: "s1", repoRoot: "/repo", repo: "origin", cwd: "/repo",
      }),
      getLiveContext: jest.fn().mockReturnValue({ branch: "main", modifiedFiles: [] }),
    }));
    const childProcess = require("child_process");
    spawnMock = jest.spyOn(childProcess, "spawn").mockReturnValue({
      unref: jest.fn(),
      pid: 1234,
    });
    const fs = require("fs");
    jest.spyOn(fs, "mkdirSync").mockImplementation(() => {});
    writeFileSyncMock = jest.spyOn(fs, "writeFileSync").mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
    delete process.env.AELLI_LITELLM_BASE;
    delete process.env.AELLI_AUTH_TOKEN;
  });

  it("does not spawn session-subscriber.js (endpoint absent)", async () => {
    const { handleStart } = require("../hooks/scripts/start");
    await handleStart({ session_id: "s1", cwd: "/repo" });
    const subscriberSpawn = spawnMock.mock.calls.find(
      (args) => String(args[1]?.[0]).includes("session-subscriber.js")
    );
    expect(subscriberSpawn).toBeUndefined();
  });

  it("does not write PID file for subscriber (not spawned)", async () => {
    const { handleStart } = require("../hooks/scripts/start");
    await handleStart({ session_id: "s1", cwd: "/repo" });
    const pidWrite = writeFileSyncMock.mock.calls.find(
      (args) => String(args[0]).includes("s1.pid")
    );
    expect(pidWrite).toBeUndefined();
  });

  it("does not spawn subscriber even when post() rejects", async () => {
    const { post: mockPost } = require("../src/a2a-client");
    mockPost.mockRejectedValueOnce(new Error("AELLI unreachable"));
    const { handleStart } = require("../hooks/scripts/start");
    await handleStart({ session_id: "s1", cwd: "/repo" });
    const subscriberSpawn = spawnMock.mock.calls.find(
      (args) => String(args[1]?.[0]).includes("session-subscriber.js")
    );
    expect(subscriberSpawn).toBeUndefined();
  });
});

describe("ensureDaemonVersion", () => {
  let http, execFileSyncSpy, readFileSyncSpy;

  beforeEach(() => {
    jest.resetModules();
    http = require("http");
    readFileSyncSpy = jest.spyOn(require("fs"), "readFileSync");
    execFileSyncSpy = jest.spyOn(require("child_process"), "execFileSync").mockImplementation(() => {});
  });

  afterEach(() => {
    delete process.env.CLAUDE_PLUGIN_ROOT;
    jest.restoreAllMocks();
  });

  function mockHealth(version) {
    jest.spyOn(http, "get").mockImplementation((opts, cb) => {
      const res = {
        on: (ev, handler) => {
          if (ev === "data") handler(JSON.stringify({ status: "ok", version }));
          if (ev === "end") handler();
          return res;
        },
      };
      cb(res);
      return { on: () => {} };
    });
  }

  it("is a no-op when CLAUDE_PLUGIN_ROOT is not set", async () => {
    delete process.env.CLAUDE_PLUGIN_ROOT;
    const { ensureDaemonVersion } = require("../hooks/scripts/start");
    await expect(ensureDaemonVersion(8765)).resolves.not.toThrow();
    expect(execFileSyncSpy).not.toHaveBeenCalled();
  });

  it("is a no-op when plugin.json cannot be read", async () => {
    process.env.CLAUDE_PLUGIN_ROOT = "/nonexistent/path";
    readFileSyncSpy.mockImplementation(() => { throw new Error("ENOENT"); });
    const { ensureDaemonVersion } = require("../hooks/scripts/start");
    await expect(ensureDaemonVersion(8765)).resolves.not.toThrow();
    expect(execFileSyncSpy).not.toHaveBeenCalled();
  });

  it("is a no-op when health check fails", async () => {
    process.env.CLAUDE_PLUGIN_ROOT = "/plugin/root";
    readFileSyncSpy.mockReturnValue(JSON.stringify({ version: "1.0.0" }));
    jest.spyOn(http, "get").mockImplementation((opts, cb) => {
      const req = { on: (ev, h) => { if (ev === "error") h(new Error("ECONNREFUSED")); return req; }, destroy: () => {} };
      return req;
    });
    const { ensureDaemonVersion } = require("../hooks/scripts/start");
    await expect(ensureDaemonVersion(8765)).resolves.not.toThrow();
    expect(execFileSyncSpy).not.toHaveBeenCalled();
  });

  it("is a no-op when versions match", async () => {
    process.env.CLAUDE_PLUGIN_ROOT = "/plugin/root";
    readFileSyncSpy.mockReturnValue(JSON.stringify({ version: "0.9.16" }));
    mockHealth("0.9.16");
    const { ensureDaemonVersion } = require("../hooks/scripts/start");
    await ensureDaemonVersion(8765);
    expect(execFileSyncSpy).not.toHaveBeenCalled();
  });

  it("restarts daemon when versions differ", async () => {
    process.env.CLAUDE_PLUGIN_ROOT = "/plugin/root";
    readFileSyncSpy.mockReturnValue(JSON.stringify({ version: "0.9.16" }));
    mockHealth("0.9.8");
    const { ensureDaemonVersion } = require("../hooks/scripts/start");
    await ensureDaemonVersion(8765, { sleepMs: 0 });
    const launchctlCalls = execFileSyncSpy.mock.calls.filter((c) => c[0] === "launchctl");
    expect(launchctlCalls.length).toBe(2); // unload + load
    const plistBuddyCalls = execFileSyncSpy.mock.calls.filter((c) =>
      String(c[0]).includes("PlistBuddy")
    );
    expect(plistBuddyCalls.length).toBe(1);
    expect(plistBuddyCalls[0][1][1]).toContain("/plugin/root/index.js");
  });

  it("does not throw when restart fails", async () => {
    process.env.CLAUDE_PLUGIN_ROOT = "/plugin/root";
    readFileSyncSpy.mockReturnValue(JSON.stringify({ version: "0.9.16" }));
    mockHealth("0.9.8");
    execFileSyncSpy.mockImplementation(() => { throw new Error("launchctl failed"); });
    const { ensureDaemonVersion } = require("../hooks/scripts/start");
    await expect(ensureDaemonVersion(8765)).resolves.not.toThrow();
  });
});
