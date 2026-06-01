describe("SandcastleProvider", () => {
  it("exports SandcastleProvider class", () => {
    const { SandcastleProvider } = require("../../src/providers/sandcastle");
    expect(typeof SandcastleProvider).toBe("function");
  });

  it("run() calls the runFn with task, cwd, branch", async () => {
    const mockRun = jest.fn().mockResolvedValue({ commits: ["abc123"], output: "done" });
    const { SandcastleProvider } = require("../../src/providers/sandcastle");
    const provider = new SandcastleProvider(mockRun);
    const result = await provider.run({ task: "fix the bug", cwd: "/repo", branch: "feat/fix" });
    expect(mockRun).toHaveBeenCalledWith(expect.objectContaining({ task: "fix the bug", cwd: "/repo" }));
    expect(result.commits).toEqual(["abc123"]);
  });

  it("run() throws when task is missing", async () => {
    const { SandcastleProvider } = require("../../src/providers/sandcastle");
    const provider = new SandcastleProvider(jest.fn());
    await expect(provider.run({ cwd: "/r" })).rejects.toThrow("task is required");
  });

  it("run() throws when cwd is missing", async () => {
    const { SandcastleProvider } = require("../../src/providers/sandcastle");
    const provider = new SandcastleProvider(jest.fn());
    await expect(provider.run({ task: "t" })).rejects.toThrow("cwd is required");
  });

  it("run() propagates errors from runFn", async () => {
    const mockRun = jest.fn().mockRejectedValue(new Error("Docker not running"));
    const { SandcastleProvider } = require("../../src/providers/sandcastle");
    const provider = new SandcastleProvider(mockRun);
    await expect(provider.run({ task: "t", cwd: "/r" })).rejects.toThrow("Docker not running");
  });
});
