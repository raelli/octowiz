const { handleManageAgents } = require("../../src/capabilities/manage-agents");
const owners = require("../../src/session-owners");

const mockAdapter = (sessions = [], controlOut = "") => ({
  listSessions: jest.fn(() => sessions),
  control: jest.fn(() => controlOut),
});

beforeEach(() => owners.clear());

describe("list", () => {
  it("returns sessions array", async () => {
    const adapter = mockAdapter([{ sessionId: "s1", status: "running", cwd: "/r", needsInput: false }]);
    const r = await handleManageAgents({ operation: "list" }, adapter);
    expect(r.status).toBe("ok");
    expect(r.sessions[0].sessionId).toBe("s1");
  });

  it("returns ok with empty sessions when adapter errors", async () => {
    const adapter = { listSessions: jest.fn(() => { throw new Error("fail"); }) };
    const r = await handleManageAgents({ operation: "list" }, adapter);
    expect(r.status).toBe("ok");
    expect(r.sessions).toEqual([]);
  });
});

describe("control ops", () => {
  it("rejects unowned session", async () => {
    const adapter = mockAdapter();
    const r = await handleManageAgents({ operation: "stop", sessionId: "s1", _principal: "alice" }, adapter);
    expect(r.status).toBe("error");
    expect(r.message).toMatch(/not owned/i);
  });

  it("runs stop on owned session", async () => {
    owners.register("s1", "alice");
    const adapter = mockAdapter([], "");
    const r = await handleManageAgents({ operation: "stop", sessionId: "s1", _principal: "alice" }, adapter);
    expect(r.status).toBe("ok");
    expect(adapter.control).toHaveBeenCalledWith("stop", "s1");
  });

  it("deregisters ownership after rm", async () => {
    owners.register("s1", "alice");
    const adapter = mockAdapter([], "");
    await handleManageAgents({ operation: "rm", sessionId: "s1", _principal: "alice" }, adapter);
    expect(owners.check("s1", "alice")).toBe(false);
  });

  it("rejects invalid sessionId", async () => {
    const r = await handleManageAgents({ operation: "stop", sessionId: "../evil", _principal: "x" }, mockAdapter());
    expect(r.status).toBe("error");
    expect(r.message).toMatch(/invalid.*sessionId/i);
  });

  it("returns error on unknown operation", async () => {
    const r = await handleManageAgents({ operation: "nuke" }, mockAdapter());
    expect(r.status).toBe("error");
  });
});
