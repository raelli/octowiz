const { handleAdvise, SessionStore, RulesAdvisor, InvocationPolicy } = require("../../src/capabilities/advise");

describe("InvocationPolicy", () => {
  const policy = new InvocationPolicy();

  it("returns null for empty results", () => {
    expect(policy.decide([])).toBeNull();
  });

  it("returns advise level for branch-drift", () => {
    const d = policy.decide([{ type: "branch-drift", message: "too many changes" }]);
    expect(d.level).toBe("advise");
    expect(d.type).toBe("branch-drift");
  });

  it("returns intervene for file-conflict", () => {
    const d = policy.decide([{ type: "file-conflict", message: "conflict" }]);
    expect(d.level).toBe("intervene");
  });

  it("returns escalate for multiple results", () => {
    const d = policy.decide([
      { type: "file-conflict", message: "a" },
      { type: "branch-drift", message: "b" },
    ]);
    expect(d.level).toBe("escalate");
    expect(d.type).toBe("multi-rule");
  });
});

describe("BranchDriftRule", () => {
  it("fires after 20 file-write events", async () => {
    const store = new SessionStore();
    const event = { type: "prompt", sessionId: "s1", branch: "feat/x", repoRoot: "/r", live_modified_files: [] };
    for (let i = 0; i < 20; i++) store.recordEvent({ type: "file-write", sessionId: "s1", branch: "feat/x" });
    const session = store.getSession("s1");
    const advisor = new RulesAdvisor();
    const results = await advisor.adviseAll(event, session, { store });
    expect(results.some((r) => r.type === "branch-drift")).toBe(true);
  });
});

describe("handleAdvise", () => {
  it("returns null for an event with no violations", async () => {
    const result = await handleAdvise({ type: "prompt", sessionId: "s1", live_modified_files: [] });
    expect(result).toBeNull();
  });

  it("returns a decision when spec-deviation fires", async () => {
    const result = await handleAdvise({
      type: "prompt",
      sessionId: "s2",
      live_modified_files: ["src/foo.js"],
      prompt_summary: "fix header",
    });
    expect(result).not.toBeNull();
    expect(result.level).toBeDefined();
  });
});
