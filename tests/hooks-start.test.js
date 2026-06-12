"use strict";

// Hermetic plugin root: no plugin.json (so ensureA2AServer skips its probe
// path when a port is open) and no apps/a2a-agent/main.py (so nothing is
// ever really spawned when the port is closed). Keeps handleStart tests off
// the network and away from any real A2A server on the machine.
function makeBarePluginRoot() {
  const fs = require("fs");
  const os = require("os");
  const path = require("path");
  return fs.mkdtempSync(path.join(os.tmpdir(), "octowiz-bare-root-"));
}

describe("hooks/scripts/start.js", () => {
  beforeEach(() => {
    jest.resetModules();
    process.env.AELLI_LITELLM_BASE = "https://llm.test";
    process.env.AELLI_AUTH_TOKEN = "tok";
    process.env.CLAUDE_PLUGIN_ROOT = makeBarePluginRoot();
    jest.mock("../src/a2a-client", () => ({ post: jest.fn().mockResolvedValue(null) }));
    jest.mock("../src/git-context", () => ({
      captureContext: jest.fn().mockReturnValue({
        sessionId: "s1", repoRoot: "/repo", repo: "origin", cwd: "/repo",
      }),
      getLiveContext: jest.fn().mockReturnValue({ branch: "main", modifiedFiles: [] }),
    }));
    // With CLAUDE_PLUGIN_ROOT set, ensureDaemonVersion would otherwise read
    // the REAL launchd plist and try to reload the real daemon mid-test.
    jest.spyOn(require("child_process"), "execFileSync").mockImplementation(() => {
      throw new Error("child_process disabled in handleStart tests");
    });
  });

  afterEach(() => {
    delete process.env.AELLI_LITELLM_BASE;
    delete process.env.AELLI_AUTH_TOKEN;
    delete process.env.CLAUDE_PLUGIN_ROOT;
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
    process.env.CLAUDE_PLUGIN_ROOT = makeBarePluginRoot();
    const childProcess = require("child_process");
    spawnMock = jest.spyOn(childProcess, "spawn").mockReturnValue({
      unref: jest.fn(),
      pid: 1234,
    });
    jest.spyOn(childProcess, "execFileSync").mockImplementation(() => {
      throw new Error("child_process disabled in handleStart tests");
    });
    const fs = require("fs");
    jest.spyOn(fs, "mkdirSync").mockImplementation(() => {});
    writeFileSyncMock = jest.spyOn(fs, "writeFileSync").mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
    delete process.env.AELLI_LITELLM_BASE;
    delete process.env.AELLI_AUTH_TOKEN;
    delete process.env.CLAUDE_PLUGIN_ROOT;
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
  let execFileSyncSpy;

  beforeEach(() => {
    jest.resetModules();
    // default: return undefined — causes PlistBuddy Print's .trim() to throw,
    // so any test that doesn't set up its own mock gets a safe no-op
    execFileSyncSpy = jest.spyOn(require("child_process"), "execFileSync")
      .mockImplementation(() => {});
  });

  afterEach(() => {
    delete process.env.CLAUDE_PLUGIN_ROOT;
    jest.restoreAllMocks();
  });

  it("is a no-op when CLAUDE_PLUGIN_ROOT is not set", async () => {
    delete process.env.CLAUDE_PLUGIN_ROOT;
    const { ensureDaemonVersion } = require("../hooks/scripts/start");
    await expect(ensureDaemonVersion()).resolves.not.toThrow();
    expect(execFileSyncSpy).not.toHaveBeenCalled();
  });

  it("is a no-op when PlistBuddy read fails (plist absent or unreadable)", async () => {
    process.env.CLAUDE_PLUGIN_ROOT = "/plugin/root";
    execFileSyncSpy.mockImplementation(() => { throw new Error("file not found"); });
    const { ensureDaemonVersion } = require("../hooks/scripts/start");
    await expect(ensureDaemonVersion()).resolves.not.toThrow();
    const launchctlCalls = execFileSyncSpy.mock.calls.filter((c) => c[0] === "launchctl");
    expect(launchctlCalls.length).toBe(0);
  });

  it("is a no-op when daemon plist already points at current plugin", async () => {
    process.env.CLAUDE_PLUGIN_ROOT = "/plugin/root";
    execFileSyncSpy.mockReturnValue("/plugin/root/index.js"); // PlistBuddy Print returns matching path
    const { ensureDaemonVersion } = require("../hooks/scripts/start");
    await ensureDaemonVersion();
    const launchctlCalls = execFileSyncSpy.mock.calls.filter((c) => c[0] === "launchctl");
    expect(launchctlCalls.length).toBe(0);
  });

  it("restarts Node daemon when plist points at old index.js", async () => {
    process.env.CLAUDE_PLUGIN_ROOT = "/plugin/root";
    execFileSyncSpy
      .mockReturnValueOnce("/old/plugin/root/index.js") // PlistBuddy Print — stale path
      .mockImplementation(() => {});                    // launchctl + PlistBuddy Set + launchctl
    const { ensureDaemonVersion } = require("../hooks/scripts/start");
    await ensureDaemonVersion({ sleepMs: 0 });
    const launchctlCalls = execFileSyncSpy.mock.calls.filter((c) => c[0] === "launchctl");
    expect(launchctlCalls.length).toBe(2); // unload + load
    const plistBuddyCalls = execFileSyncSpy.mock.calls.filter((c) =>
      String(c[0]).includes("PlistBuddy")
    );
    expect(plistBuddyCalls.length).toBe(2); // Print + Set
    expect(plistBuddyCalls[1][1][1]).toContain("/plugin/root/index.js");
  });

  it("does not throw when restart fails", async () => {
    process.env.CLAUDE_PLUGIN_ROOT = "/plugin/root";
    execFileSyncSpy
      .mockReturnValueOnce("/old/plugin/root/index.js") // PlistBuddy Print succeeds
      .mockImplementation(() => { throw new Error("launchctl failed"); }); // restart fails
    const { ensureDaemonVersion } = require("../hooks/scripts/start");
    await expect(ensureDaemonVersion({ sleepMs: 0 })).resolves.not.toThrow();
  });
});
