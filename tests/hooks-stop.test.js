"use strict";
const mockPost = jest.fn().mockResolvedValue(null);
const mockGetContext = jest.fn().mockReturnValue({
  sessionId: "s1", repoRoot: "/repo", repo: "origin",
});

jest.mock("../src/a2a-client", () => ({ post: mockPost }));
jest.mock("../src/git-context", () => ({ getContext: mockGetContext }));

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

  it("does not throw when getContext returns null", async () => {
    mockGetContext.mockReturnValueOnce(null);
    await expect(handleStop({ session_id: "s1" })).resolves.not.toThrow();
  });
});

describe("hooks/scripts/stop.js — subscriber cleanup", () => {
  let existsSyncMock, readFileSyncMock, unlinkSyncMock, killMock;

  beforeEach(() => {
    jest.resetModules();
    jest.mock("../src/a2a-client", () => ({ post: jest.fn().mockResolvedValue(null) }));
    jest.mock("../src/git-context", () => ({
      getContext: jest.fn().mockReturnValue({ sessionId: "s1", repo: null, repoRoot: null }),
    }));
    const fs = require("fs");
    existsSyncMock = jest.spyOn(fs, "existsSync").mockReturnValue(true);
    readFileSyncMock = jest.spyOn(fs, "readFileSync").mockReturnValue("5678");
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
