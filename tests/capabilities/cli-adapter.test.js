const { ClaudeCliAdapter } = require("../../src/capabilities/cli-adapter");

describe("ClaudeCliAdapter", () => {
  describe("startSession", () => {
    it("parses session ID from --bg output with bullet separator", () => {
      const adapter = new ClaudeCliAdapter((args, _cwd) => {
        return [0, "\x1b[32mbackgrounded · abc123def4\x1b[0m", ""];
      });
      const result = adapter.startSession("fix the bug", "/repo");
      expect(result).toEqual({ ok: true, sessionId: "abc123def4" });
    });

    it("parses session ID with middle-dot separator", () => {
      const adapter = new ClaudeCliAdapter((_args, _cwd) => {
        return [0, "backgrounded • xyz-session-99", ""];
      });
      const result = adapter.startSession("task", "/repo");
      expect(result.sessionId).toBe("xyz-session-99");
    });

    it("returns error when exit code is non-zero", () => {
      const adapter = new ClaudeCliAdapter(() => [1, "", "claude: command failed"]);
      const result = adapter.startSession("task", "/repo");
      expect(result).toEqual({ ok: false, error: "claude: command failed" });
    });

    it("returns parse error when session ID not in output", () => {
      const adapter = new ClaudeCliAdapter(() => [0, "some other output", ""]);
      const result = adapter.startSession("task", "/repo");
      expect(result.ok).toBe(false);
      expect(result.error).toMatch(/parse/i);
    });

    it("passes cwd to runner", () => {
      const calls = [];
      const adapter = new ClaudeCliAdapter((args, cwd) => { calls.push({ args, cwd }); return [0, "backgrounded · s1", ""]; });
      adapter.startSession("task", "/my/repo");
      expect(calls[0].cwd).toBe("/my/repo");
      expect(calls[0].args).toContain("--bg");
    });
  });

  describe("listSessions", () => {
    it("parses sessionId/cwd/startedAt from JSON output", () => {
      const raw = JSON.stringify([
        { sessionId: "s1", cwd: "/repo", startedAt: 1000, status: "running", needsInput: false }
      ]);
      const adapter = new ClaudeCliAdapter(() => [0, raw, ""]);
      const sessions = adapter.listSessions();
      expect(sessions[0]).toEqual({ sessionId: "s1", cwd: "/repo", startedAt: 1000, status: "running", needsInput: false });
    });

    it("falls back to legacy id/repoRoot/createdAt fields", () => {
      const raw = JSON.stringify([{ id: "s2", repoRoot: "/legacy", createdAt: 2000, status: "idle" }]);
      const adapter = new ClaudeCliAdapter(() => [0, raw, ""]);
      const [s] = adapter.listSessions();
      expect(s.sessionId).toBe("s2");
      expect(s.cwd).toBe("/legacy");
    });

    it("returns empty array on CLI error", () => {
      const adapter = new ClaudeCliAdapter(() => [1, "", "error"]);
      expect(adapter.listSessions()).toEqual([]);
    });
  });

  describe("control", () => {
    it("returns output string on success", () => {
      const adapter = new ClaudeCliAdapter(() => [0, "stopped", ""]);
      expect(adapter.control("stop", "s1")).toBe("stopped");
    });

    it("throws on non-zero exit", () => {
      const adapter = new ClaudeCliAdapter(() => [1, "", "not found"]);
      expect(() => adapter.control("stop", "s1")).toThrow("not found");
    });
  });
});
