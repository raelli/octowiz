"use strict";
const mockPost = jest.fn().mockResolvedValue(null);
const mockGetStableContext = jest.fn().mockReturnValue({
  sessionId: "s1", repoRoot: "/repo", repo: "origin",
});

jest.mock("../src/a2a-client", () => ({ post: mockPost }));
jest.mock("../src/git-context", () => ({ getStableContext: mockGetStableContext }));

const { handleStop } = require("../hooks/scripts/stop");

beforeEach(() => jest.clearAllMocks());

describe("hooks/scripts/stop.js", () => {
  it("posts session-end with sync:true and timeoutMs:500", async () => {
    await handleStop({ session_id: "s1" });
    expect(mockPost).toHaveBeenCalledWith(
      "session-end",
      expect.objectContaining({ sessionId: "s1" }),
      expect.objectContaining({ sync: true, timeoutMs: 500 })
    );
  });

  it("does not throw when session_id is missing", async () => {
    await expect(handleStop({})).resolves.not.toThrow();
  });

  it("does not throw when getStableContext returns null", async () => {
    mockGetStableContext.mockReturnValueOnce(null);
    await expect(handleStop({ session_id: "s1" })).resolves.not.toThrow();
  });

  it("only calls post once — notifyOctowizServer is gone", async () => {
    await handleStop({ session_id: "s1" });
    // Only the AELLI session-end post; the old notifyOctowizServer call is removed
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost).toHaveBeenCalledWith("session-end", expect.any(Object), expect.any(Object));
  });
});

describe("hooks/scripts/stop.js — subscriber cleanup", () => {
  let existsSyncMock, unlinkSyncMock, killMock;

  beforeEach(() => {
    jest.resetModules();
    jest.mock("../src/a2a-client", () => ({ post: jest.fn().mockResolvedValue(null) }));
    jest.mock("../src/git-context", () => ({
      getStableContext: jest.fn().mockReturnValue({ sessionId: "s1", repo: null, repoRoot: null }),
    }));
    const fs = require("fs");
    existsSyncMock = jest.spyOn(fs, "existsSync").mockReturnValue(true);
    jest.spyOn(fs, "readFileSync").mockReturnValue("5678");
    unlinkSyncMock = jest.spyOn(fs, "unlinkSync").mockImplementation(() => {});
    killMock = jest.spyOn(process, "kill").mockImplementation(() => {});
  });

  afterEach(() => jest.restoreAllMocks());

  it("sends SIGTERM to the PID from the PID file", async () => {
    const { handleStop } = require("../hooks/scripts/stop");
    await handleStop({ session_id: "s1" });
    expect(killMock).toHaveBeenCalledWith(5678, "SIGTERM");
  });

  it("deletes the PID file after SIGTERM", async () => {
    const { handleStop } = require("../hooks/scripts/stop");
    await handleStop({ session_id: "s1" });
    expect(unlinkSyncMock).toHaveBeenCalledWith(expect.stringContaining("s1.pid"));
  });

  it("does not throw when PID file does not exist", async () => {
    existsSyncMock.mockReturnValue(false);
    const { handleStop } = require("../hooks/scripts/stop");
    await expect(handleStop({ session_id: "s1" })).resolves.not.toThrow();
  });
});
