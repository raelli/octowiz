const { handleAdvise, handleSessionEnd, StoreRegistry, SessionStore, RulesAdvisor, InvocationPolicy } = require("../../src/capabilities/advise");

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
    const registry = new StoreRegistry();
    const result = await handleAdvise({ type: "prompt", sessionId: "s1", live_modified_files: [] }, registry);
    expect(result).toBeNull();
  });

  it("returns a decision when spec-deviation fires", async () => {
    const registry = new StoreRegistry();
    const result = await handleAdvise({
      type: "prompt",
      sessionId: "s2",
      live_modified_files: ["src/foo.js"],
      prompt_summary: "fix header",
    }, registry);
    expect(result).not.toBeNull();
    expect(result.level).toBeDefined();
  });
});

describe("StoreRegistry", () => {
  it("creates a new store for an unknown sessionId", () => {
    const registry = new StoreRegistry();
    const store = registry.get("sess-A");
    expect(store).toBeInstanceOf(SessionStore);
    expect(registry.size).toBe(1);
  });

  it("returns the same store for the same sessionId", () => {
    const registry = new StoreRegistry();
    const store1 = registry.get("sess-A");
    const store2 = registry.get("sess-A");
    expect(store1).toBe(store2);
  });

  it("drop() removes the store and decrements size", () => {
    const registry = new StoreRegistry();
    registry.get("sess-A");
    expect(registry.size).toBe(1);
    registry.drop("sess-A");
    expect(registry.size).toBe(0);
  });

  it("drop() purges the session from the shared ConflictIndex so a re-get is empty", () => {
    const registry = new StoreRegistry();
    const store = registry.get("sess-A");
    store.recordEvent({
      type: "prompt", sessionId: "sess-A", branch: "feat/a",
      repoRoot: "/repo", live_modified_files: ["foo.js"],
    });
    registry.drop("sess-A");
    // After drop, a fresh get should have no knowledge of the old session
    const freshStore = registry.get("sess-A");
    expect(freshStore.getSession("sess-A")).toBeFalsy();
  });

  it("cross-session conflict detection still works via shared ConflictIndex", async () => {
    const registry = new StoreRegistry();
    const storeA = registry.get("sess-A");
    const storeB = registry.get("sess-B");

    storeA.recordEvent({
      type: "prompt", sessionId: "sess-A", branch: "feat/a",
      repoRoot: "/repo", live_modified_files: ["src/payment.js"],
    });
    const conflicts = storeB.findConflicts("/repo", ["src/payment.js"], "sess-B");
    expect(conflicts.length).toBe(1);
    expect(conflicts[0].file).toBe("src/payment.js");
    expect(conflicts[0].otherSessionId).toBe("sess-A");
  });

  it("drop() removes the dropped session from the conflict index so no stale conflicts appear", () => {
    const registry = new StoreRegistry();
    const storeA = registry.get("sess-A");
    storeA.recordEvent({
      type: "prompt", sessionId: "sess-A", branch: "feat/a",
      repoRoot: "/repo", live_modified_files: ["src/payment.js"],
    });
    registry.drop("sess-A");

    const storeB = registry.get("sess-B");
    const conflicts = storeB.findConflicts("/repo", ["src/payment.js"], "sess-B");
    expect(conflicts.length).toBe(0);
  });

  it("clear() removes all stores", () => {
    const registry = new StoreRegistry();
    registry.get("sess-A");
    registry.get("sess-B");
    expect(registry.size).toBe(2);
    registry.clear();
    expect(registry.size).toBe(0);
  });

  it("handleSessionEnd() drops the session via the registry", () => {
    const registry = new StoreRegistry();
    registry.get("sess-A");
    expect(registry.size).toBe(1);
    handleSessionEnd("sess-A", registry);
    expect(registry.size).toBe(0);
  });
});
