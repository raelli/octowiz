const { MemPalaceStore } = require("../../src/handoff/mempalace-store");
const { createHandoffStore } = require("../../src/handoff/store");

describe("MemPalaceStore stub", () => {
  it("throws with a clear not-yet-available message on store()", async () => {
    const store = new MemPalaceStore();
    await expect(store.store("summary", "content", {})).rejects.toThrow(/MemPalace.*not yet available/i);
  });

  it("throws with a clear not-yet-available message on fetch()", async () => {
    const store = new MemPalaceStore();
    await expect(store.fetch("some-ref")).rejects.toThrow(/MemPalace.*not yet available/i);
  });
});

describe("createHandoffStore factory", () => {
  it("returns GitHubIssueStore by default", () => {
    delete process.env.HANDOFF_STORE;
    jest.resetModules();
    const { createHandoffStore: cs } = require("../../src/handoff/store");
    const { GitHubIssueStore } = require("../../src/handoff/github-issue-store");
    expect(cs()).toBeInstanceOf(GitHubIssueStore);
  });

  it("returns MemPalaceStore when HANDOFF_STORE=mempalace", () => {
    process.env.HANDOFF_STORE = "mempalace";
    jest.resetModules();
    const { createHandoffStore: cs } = require("../../src/handoff/store");
    const { MemPalaceStore: MPS } = require("../../src/handoff/mempalace-store");
    const instance = cs();
    expect(instance).toBeInstanceOf(MPS);
    delete process.env.HANDOFF_STORE;
  });
});
