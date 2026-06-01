const fs = require("fs");

describe("daemon.processTask", () => {
  let processTask, claimTask, postResult, handleDispatch;
  let realpathSyncSpy;

  beforeEach(() => {
    realpathSyncSpy = jest.spyOn(fs, "realpathSync").mockImplementation((p) => p);
    jest.resetModules();
    jest.mock("../src/task-queue-client");
    jest.mock("../src/capabilities/dispatch");
    jest.mock("../src/capabilities/advise");
    jest.mock("../src/capabilities/manage-agents");
    process.env.OCTOWIZ_ALLOWED_ROOTS = "/allowed";
    process.env.AELLI_BASE_URL = "http://localhost:3456";
    ({ claimTask, postResult } = require("../src/task-queue-client"));
    ({ handleDispatch } = require("../src/capabilities/dispatch"));
    ({ processTask } = require("../src/daemon"));
    claimTask.mockResolvedValue({ ok: true, leaseToken: "lt-1" });
    postResult.mockResolvedValue();
    handleDispatch.mockResolvedValue({ status: "completed", output: "done" });
  });

  afterEach(() => {
    jest.clearAllMocks();
    realpathSyncSpy.mockRestore();
  });

  it("claims task and posts result for octowiz.dispatch", async () => {
    await processTask({ id: "t1", capability: "octowiz.dispatch", payload: { task: "fix", cwd: "/allowed/repo" } });
    expect(claimTask).toHaveBeenCalledWith("t1");
    expect(postResult).toHaveBeenCalledWith("t1", "lt-1", expect.objectContaining({ status: "completed" }));
  });

  it("skips processing when claim fails (409)", async () => {
    claimTask.mockResolvedValue({ ok: false, reason: "already_claimed" });
    await processTask({ id: "t1", capability: "octowiz.dispatch", payload: {} });
    expect(postResult).not.toHaveBeenCalled();
  });

  it("posts failed result for unknown capability", async () => {
    claimTask.mockResolvedValue({ ok: true, leaseToken: "lt-2" });
    await processTask({ id: "t2", capability: "octowiz.unknown", payload: {} });
    expect(postResult).toHaveBeenCalledWith("t2", "lt-2", expect.objectContaining({ status: "error" }));
  });

  it("posts failed result when capability throws", async () => {
    claimTask.mockResolvedValue({ ok: true, leaseToken: "lt-3" });
    handleDispatch.mockRejectedValue(new Error("exploded"));
    await processTask({ id: "t3", capability: "octowiz.dispatch", payload: { task: "x", cwd: "/allowed/r" } });
    expect(postResult).toHaveBeenCalledWith("t3", "lt-3", expect.objectContaining({ status: "error" }));
  });
});

it("index.js does not call subscribe() — daemon only", async () => {
  jest.resetModules();
  const mockSubscribe = jest.fn();
  jest.mock("../src/a2a-client", () => ({
    subscribe: mockSubscribe,
    updateTask: jest.fn(),
  }));
  jest.mock("../src/daemon", () => ({ start: jest.fn() }));
  jest.useFakeTimers({ doNotFake: ["setImmediate"] });
  require("../index");
  // Give the async start() a tick to run
  await new Promise((r) => setImmediate(r));
  expect(mockSubscribe).not.toHaveBeenCalled();
  jest.useRealTimers();
});
