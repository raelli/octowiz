"use strict";

describe("src/session-subscriber.js", () => {
  it("does not call subscribe() — endpoint not yet on AELLI", () => {
    jest.resetModules();
    const mockSubscribe = jest.fn();
    jest.mock("../src/a2a-client", () => ({
      subscribe: mockSubscribe,
      updateTask: jest.fn(),
    }));
    require("../src/session-subscriber");
    expect(mockSubscribe).not.toHaveBeenCalled();
  });

  it("loads without error", () => {
    jest.resetModules();
    expect(() => require("../src/session-subscriber")).not.toThrow();
  });

  it("does not call daemon.start()", () => {
    jest.resetModules();
    const mockDaemon = { start: jest.fn() };
    jest.mock("../src/daemon", () => mockDaemon);
    require("../src/session-subscriber");
    expect(mockDaemon.start).not.toHaveBeenCalled();
  });
});
