"use strict";
const mockPost = jest.fn().mockResolvedValue(null);
const mockGetContext = jest.fn().mockReturnValue({
  sessionId: "s1", repoRoot: "/repo", repo: "origin",
  branch: "main", modifiedFiles: [],
});

jest.mock("../src/a2a-client", () => ({ post: mockPost }));
jest.mock("../src/git-context", () => ({ getContext: mockGetContext }));

const { handleEvent } = require("../hooks/scripts/report-event");

beforeEach(() => jest.clearAllMocks());

describe("hooks/scripts/report-event.js", () => {
  it("posts file-edit for Edit tool", async () => {
    await handleEvent({ session_id: "s1", tool_name: "Edit",
      tool_input: { file_path: "/repo/src/foo.js" } });
    expect(mockPost).toHaveBeenCalledWith(
      "file-edit",
      expect.objectContaining({ sessionId: "s1", file: "src/foo.js" }),
      expect.objectContaining({ sync: false })
    );
  });

  it("posts file-write for Write tool", async () => {
    await handleEvent({ session_id: "s1", tool_name: "Write",
      tool_input: { file_path: "/repo/src/bar.js" } });
    expect(mockPost).toHaveBeenCalledWith(
      "file-write",
      expect.objectContaining({ file: "src/bar.js" }),
      expect.objectContaining({ sync: false })
    );
  });

  it("posts prompt event when no tool_name (UserPromptSubmit)", async () => {
    await handleEvent({ session_id: "s1", prompt: "fix the bug" });
    expect(mockPost).toHaveBeenCalledWith(
      "prompt",
      expect.objectContaining({ sessionId: "s1", prompt_summary: "fix the bug" }),
      expect.objectContaining({ sync: false })
    );
  });

  it("exits cleanly when getContext returns null", async () => {
    mockGetContext.mockReturnValueOnce(null);
    await expect(handleEvent({ session_id: "s1", tool_name: "Edit",
      tool_input: { file_path: "/repo/src/foo.js" } })).resolves.not.toThrow();
  });

  it("exits cleanly on empty input", async () => {
    await expect(handleEvent({})).resolves.not.toThrow();
  });
});
