"use strict";

describe("src/session-subscriber.js", () => {
  it("calls subscribe() with a function callback", () => {
    jest.resetModules();
    const mockSubscribe = jest.fn();
    jest.mock("../src/a2a-client", () => ({
      subscribe: mockSubscribe,
      updateTask: jest.fn().mockResolvedValue(null),
    }));
    require("../src/session-subscriber");
    expect(mockSubscribe).toHaveBeenCalledWith(expect.any(Function));
  });

  it("does not call daemon.start()", () => {
    jest.resetModules();
    jest.mock("../src/a2a-client", () => ({ subscribe: jest.fn(), updateTask: jest.fn() }));
    const mockDaemon = { start: jest.fn() };
    jest.mock("../src/daemon", () => mockDaemon);
    require("../src/session-subscriber");
    expect(mockDaemon.start).not.toHaveBeenCalled();
  });

  it("onTask handler calls updateTask with working then completed", async () => {
    jest.resetModules();
    const mockUpdateTask = jest.fn().mockResolvedValue(null);
    let capturedHandler;
    jest.mock("../src/a2a-client", () => ({
      subscribe: (fn) => { capturedHandler = fn; },
      updateTask: mockUpdateTask,
    }));
    require("../src/session-subscriber");
    await capturedHandler({ id: "task-1", messages: [{ parts: [{ text: "{}" }] }] });
    expect(mockUpdateTask).toHaveBeenCalledWith("task-1", "working");
    expect(mockUpdateTask).toHaveBeenCalledWith("task-1", "completed", expect.any(Object));
  });

  it("onTask handler does not throw on malformed task", async () => {
    jest.resetModules();
    let capturedHandler;
    jest.mock("../src/a2a-client", () => ({
      subscribe: (fn) => { capturedHandler = fn; },
      updateTask: jest.fn().mockResolvedValue(null),
    }));
    require("../src/session-subscriber");
    await expect(capturedHandler({ id: "bad" })).resolves.not.toThrow();
  });
});
