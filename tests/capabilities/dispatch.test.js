const { handleDispatch } = require("../../src/capabilities/dispatch");
const owners = require("../../src/session-owners");

beforeEach(() => owners.clear());

function makeAdapter({ startResult, sessions = [], logsOut = "done" }) {
  return {
    startSession: jest.fn(() => startResult),
    listSessions: jest.fn(() => sessions),
    control: jest.fn(() => logsOut),
  };
}

describe("handleDispatch", () => {
  it("returns error when task is missing", async () => {
    const r = await handleDispatch({ cwd: "/r" }, { adapter: makeAdapter({ startResult: { ok: true, sessionId: "s1" } }) });
    expect(r.status).toBe("error");
    expect(r.message).toMatch(/task.*required/i);
  });

  it("returns error when cwd is missing", async () => {
    const r = await handleDispatch({ task: "fix" }, { adapter: makeAdapter({ startResult: { ok: true, sessionId: "s1" } }) });
    expect(r.status).toBe("error");
  });

  it("returns error when startSession fails", async () => {
    const adapter = makeAdapter({ startResult: { ok: false, error: "no claude" } });
    const r = await handleDispatch({ task: "fix", cwd: "/r" }, { adapter, principal: "u1" });
    expect(r.status).toBe("error");
    expect(r.message).toMatch(/failed to start/i);
  });

  it("returns completed when session reaches idle state", async () => {
    const adapter = makeAdapter({
      startResult: { ok: true, sessionId: "s1" },
      sessions: [{ sessionId: "s1", status: "idle", needsInput: false }],
    });
    adapter.control = jest.fn(() => "output text");
    const r = await handleDispatch({ task: "fix", cwd: "/r" }, { adapter, principal: "u1", pollInterval: 0, timeout: 5000 });
    expect(r.status).toBe("completed");
    expect(r.sessionId).toBe("s1");
  });

  it("returns needs-input when session needs input", async () => {
    const adapter = makeAdapter({
      startResult: { ok: true, sessionId: "s1" },
      sessions: [{ sessionId: "s1", status: "running", needsInput: true }],
    });
    adapter.control = jest.fn(() => "waiting for input...");
    const r = await handleDispatch({ task: "fix", cwd: "/r" }, { adapter, principal: "u1", pollInterval: 0, timeout: 5000 });
    expect(r.status).toBe("needs-input");
  });

  it("times out when session never completes", async () => {
    const adapter = makeAdapter({
      startResult: { ok: true, sessionId: "s1" },
      sessions: [{ sessionId: "s1", status: "running", needsInput: false }],
    });
    const r = await handleDispatch({ task: "fix", cwd: "/r" }, { adapter, principal: "u1", pollInterval: 0, timeout: 1 });
    expect(r.status).toBe("error");
    expect(r.message).toMatch(/timeout/i);
  });
});
