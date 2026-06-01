"use strict";

describe("hooks/scripts/start.js", () => {
  beforeEach(() => {
    jest.resetModules();
    process.env.AELLI_LITELLM_BASE = "https://llm.test";
    process.env.AELLI_AUTH_TOKEN = "tok";
    jest.mock("../src/a2a-client", () => ({ post: jest.fn().mockResolvedValue(null) }));
    jest.mock("../src/git-context", () => ({
      captureContext: jest.fn().mockReturnValue({
        sessionId: "s1", repoRoot: "/repo", repo: "origin", cwd: "/repo", branch: "main",
      }),
    }));
    jest.mock("../src/event-builder", () => ({
      buildSessionStart: jest.fn().mockReturnValue({ sessionId: "s1", branch: "main" }),
    }));
  });

  afterEach(() => {
    delete process.env.AELLI_LITELLM_BASE;
    delete process.env.AELLI_AUTH_TOKEN;
    jest.restoreAllMocks();
  });

  it("calls post with session-start and correct sessionId", async () => {
    const { post: mockPost } = require("../src/a2a-client");
    const { handleStart } = require("../hooks/scripts/start");
    await handleStart({ session_id: "s1", cwd: "/repo" });
    expect(mockPost).toHaveBeenCalledWith(
      "session-start",
      expect.objectContaining({ sessionId: "s1" }),
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
        sessionId: "s1", repoRoot: "/repo", repo: "origin", cwd: "/repo", branch: "main",
      }),
    }));
    jest.mock("../src/event-builder", () => ({
      buildSessionStart: jest.fn().mockReturnValue({ sessionId: "s1" }),
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
