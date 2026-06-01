describe("parseSseEvents", () => {
  let parseSseEvents;

  beforeEach(() => {
    jest.resetModules();
    ({ parseSseEvents } = require("../src/a2a-client"));
  });

  it("parses a single complete event", () => {
    const { events, remainder } = parseSseEvents('event: task-new\ndata: {"id":"t1"}\n\n');
    expect(events).toEqual([{ event: "task-new", data: '{"id":"t1"}' }]);
    expect(remainder).toBe("");
  });

  it("defaults event name to 'message' when no event field", () => {
    const { events } = parseSseEvents("data: hello\n\n");
    expect(events[0]).toEqual({ event: "message", data: "hello" });
  });

  it("returns partial chunk as remainder", () => {
    const { events, remainder } = parseSseEvents("event: task-new\ndata: {}\n\nevent: ping\n");
    expect(events).toHaveLength(1);
    expect(events[0].event).toBe("task-new");
    expect(remainder).toBe("event: ping\n");
  });

  it("parses multiple events in one buffer", () => {
    const buf = "event: a\ndata: 1\n\nevent: b\ndata: 2\n\n";
    const { events, remainder } = parseSseEvents(buf);
    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ event: "a", data: "1" });
    expect(events[1]).toEqual({ event: "b", data: "2" });
    expect(remainder).toBe("");
  });

  it("returns empty events and the full input as remainder when no complete event", () => {
    const buf = "event: ping\ndata: {}";
    const { events, remainder } = parseSseEvents(buf);
    expect(events).toHaveLength(0);
    expect(remainder).toBe(buf);
  });

  it("handles empty string", () => {
    const { events, remainder } = parseSseEvents("");
    expect(events).toHaveLength(0);
    expect(remainder).toBe("");
  });

  it("concatenates multi-line data fields with newlines per SSE spec", () => {
    const buf = "event: task-new\ndata: line1\ndata: line2\ndata: line3\n\n";
    const { events } = parseSseEvents(buf);
    expect(events).toHaveLength(1);
    expect(events[0].data).toBe("line1\nline2\nline3");
  });
});

describe("subscribe", () => {
  beforeEach(() => {
    jest.resetModules();
  });

  it("throws synchronously when onTask is not provided", () => {
    const { subscribe } = require("../src/a2a-client");
    expect(() => subscribe()).toThrow(TypeError);
    expect(() => subscribe()).toThrow("subscribe() requires an onTask callback function");
  });

  it("throws synchronously when onTask is not a function", () => {
    const { subscribe } = require("../src/a2a-client");
    expect(() => subscribe("not-a-function")).toThrow(TypeError);
    expect(() => subscribe(null)).toThrow(TypeError);
    expect(() => subscribe(42)).toThrow(TypeError);
  });
});

describe("subscribeToQueue", () => {
  let subscribeToQueue, parseSseEvents;
  beforeEach(() => {
    jest.resetModules();
    ({ subscribeToQueue, parseSseEvents } = require("../src/a2a-client"));
  });

  it("exports subscribeToQueue as a function", () => {
    expect(typeof subscribeToQueue).toBe("function");
  });

  it("throws TypeError when onTask is not a function", () => {
    expect(() => subscribeToQueue("http://localhost:3456/a2a/task-queue", "not-a-function"))
      .toThrow(TypeError);
  });

  it("throws TypeError when onTask is missing", () => {
    expect(() => subscribeToQueue("http://localhost:3456/a2a/task-queue"))
      .toThrow(TypeError);
  });
});

describe("post", () => {
  let post;

  beforeEach(() => {
    jest.resetModules();
    process.env.AELLI_AUTH_TOKEN = "test-bearer";
    process.env.AELLI_LITELLM_BASE = "http://localhost:4000";
    global.fetch = jest.fn();
    ({ post } = require("../src/a2a-client"));
  });

  afterEach(() => {
    delete process.env.AELLI_AUTH_TOKEN;
    delete process.env.AELLI_LITELLM_BASE;
  });

  it("fire-and-forget: calls fetch with correct URL, method, auth header and returns null", async () => {
    global.fetch.mockResolvedValue({ json: async () => ({}) });

    const result = await post("file-write", { sessionId: "s1" }, { sync: false });
    expect(result).toBeNull();
    expect(global.fetch).toHaveBeenCalledTimes(1);

    const [url, init] = global.fetch.mock.calls[0];
    expect(url).toBe("http://localhost:4000/a2a/aelli-dev-advisor/message/send");
    expect(init.method).toBe("POST");
    expect(init.headers.Authorization).toBe("Bearer test-bearer");
  });

  it("fire-and-forget: embeds eventType inside the JSON-RPC payload", async () => {
    global.fetch.mockResolvedValue({ json: async () => ({}) });

    await post("session-start", { sessionId: "s1" }, { sync: false });
    const [, init] = global.fetch.mock.calls[0];
    const rpc = JSON.parse(init.body);
    const inner = JSON.parse(rpc.params.message.parts[0].text);
    expect(inner.type).toBe("session-start");
    expect(inner.sessionId).toBe("s1");
  });

  it("sync: returns decoded artifact from response", async () => {
    const artifact = { type: "file-conflict", message: "conflict detected" };
    global.fetch.mockResolvedValue({
      json: async () => ({
        result: { artifacts: [{ parts: [{ kind: "text", text: JSON.stringify(artifact) }] }] },
      }),
    });
    const result = await post("prompt", { sessionId: "s1" }, { sync: true, timeoutMs: 2000 });
    expect(result).toEqual(artifact);
  });

  it("sync: returns null when response has no artifact", async () => {
    global.fetch.mockResolvedValue({ json: async () => ({ result: {} }) });
    const result = await post("prompt", {}, { sync: true, timeoutMs: 2000 });
    expect(result).toBeNull();
  });

  it("sync: returns null on timeout (fail-open)", async () => {
    global.fetch.mockImplementation((_url, init) => new Promise((_, reject) => {
      if (init?.signal) {
        init.signal.addEventListener("abort", () =>
          reject(new DOMException("Aborted", "AbortError"))
        );
      }
    }));
    const result = await post("prompt", {}, { sync: true, timeoutMs: 50 });
    expect(result).toBeNull();
  }, 2000);

  it("sync: returns null when fetch throws (fail-open)", async () => {
    global.fetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const result = await post("prompt", {}, { sync: true, timeoutMs: 200 });
    expect(result).toBeNull();
  });

  it("omits Authorization header when AELLI_AUTH_TOKEN is not set", async () => {
    jest.resetModules();
    delete process.env.AELLI_AUTH_TOKEN;
    global.fetch = jest.fn().mockResolvedValue({ json: async () => ({}) });
    ({ post } = require("../src/a2a-client"));
    await post("test", {}, { sync: false });
    const [, init] = global.fetch.mock.calls[0];
    expect(init.headers.Authorization).toBeUndefined();
  });

  it("uses dev-advisor URL directly when AELLI_LITELLM_BASE is not set", async () => {
    jest.resetModules();
    delete process.env.AELLI_LITELLM_BASE;
    process.env.AELLI_DEV_ADVISOR_URL = "http://localhost:3456/a2a/dev-advisor";
    global.fetch = jest.fn().mockResolvedValue({ json: async () => ({}) });
    ({ post } = require("../src/a2a-client"));
    await post("test", {}, { sync: false });
    const [url] = global.fetch.mock.calls[0];
    expect(url).toBe("http://localhost:3456/a2a/dev-advisor");
    delete process.env.AELLI_DEV_ADVISOR_URL;
  });
});
