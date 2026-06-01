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
