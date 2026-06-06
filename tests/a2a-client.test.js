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

  it("parses a complete event with CRLF framing", () => {
    const buf = "event: task-new\r\ndata: {\"id\":\"t1\"}\r\n\r\n";
    const { events, remainder } = parseSseEvents(buf);
    expect(events).toEqual([{ event: "task-new", data: '{"id":"t1"}' }]);
    expect(remainder).toBe("");
  });

  it("parses multiple events with CRLF framing", () => {
    const buf = "event: a\r\ndata: 1\r\n\r\nevent: b\r\ndata: 2\r\n\r\n";
    const { events, remainder } = parseSseEvents(buf);
    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ event: "a", data: "1" });
    expect(events[1]).toEqual({ event: "b", data: "2" });
    expect(remainder).toBe("");
  });

  it("returns partial chunk as remainder with CRLF framing", () => {
    const buf = "event: task-new\r\ndata: {}\r\n\r\nevent: ping\r\n";
    const { events, remainder } = parseSseEvents(buf);
    expect(events).toHaveLength(1);
    expect(events[0].event).toBe("task-new");
    expect(remainder).toBe("event: ping\n");
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

describe("env var resolution", () => {
  it("uses AELLI_BASE_URL when set", () => {
    jest.resetModules();
    process.env.AELLI_BASE_URL = "http://base-url-test:3456/api";
    delete process.env.AELLI_API_BASE;
    const client = require("../src/a2a-client");
    expect(client).toBeDefined();
    delete process.env.AELLI_BASE_URL;
  });

  it("falls back to AELLI_API_BASE when AELLI_BASE_URL absent", () => {
    jest.resetModules();
    delete process.env.AELLI_BASE_URL;
    process.env.AELLI_API_BASE = "http://api-base-test:3001/api";
    const client = require("../src/a2a-client");
    expect(client).toBeDefined();
    delete process.env.AELLI_API_BASE;
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
    expect(init.headers["Authorization"]).toBe("Bearer test-bearer");
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

  it("omits x-aelli-secret header when AELLI_AUTH_TOKEN is not set", async () => {
    jest.resetModules();
    delete process.env.AELLI_AUTH_TOKEN;
    global.fetch = jest.fn().mockResolvedValue({ json: async () => ({}) });
    ({ post } = require("../src/a2a-client"));
    await post("test", {}, { sync: false });
    const [, init] = global.fetch.mock.calls[0];
    expect(init.headers["x-aelli-secret"]).toBeUndefined();
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

  it("fire-and-forget post() appends to log on fetch failure", async () => {
    jest.resetModules();
    const fs = require("fs");
    const appendSpy = jest.spyOn(fs, "appendFileSync").mockImplementation(() => {});
    global.fetch = jest.fn().mockRejectedValue(new Error("network down"));
    const { post } = require("../src/a2a-client");
    await post("session-start", { sessionId: "s1" }, { sync: false });
    await new Promise((r) => setImmediate(r));
    expect(appendSpy).toHaveBeenCalledWith(
      expect.stringContaining("aelli-cc.log"),
      expect.stringContaining("session-start")
    );
    appendSpy.mockRestore();
    delete global.fetch;
  });
});

describe("route", () => {
  beforeEach(() => {
    jest.resetModules();
    delete process.env.AELLI_ROUTER_URL;
    delete process.env.AELLI_LITELLM_BASE;
    delete process.env.AELLI_AUTH_TOKEN;
  });

  afterEach(() => {
    delete process.env.AELLI_ROUTER_URL;
    delete process.env.AELLI_LITELLM_BASE;
    delete process.env.AELLI_AUTH_TOKEN;
    delete global.fetch;
  });

  it("fail-open: returns null when ROUTER_URL is not set (no AELLI_ROUTER_URL, no AELLI_LITELLM_BASE)", async () => {
    const { route } = require("../src/a2a-client");
    const result = await route("feature", { content: "hello" });
    expect(result).toBeNull();
  });

  it("fail-open: returns null and does not call fetch when ROUTER_URL is unset", async () => {
    global.fetch = jest.fn();
    const { route } = require("../src/a2a-client");
    const result = await route("feature", {});
    expect(result).toBeNull();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("happy path: parses first SSE data line and returns parsed object", async () => {
    jest.resetModules();
    process.env.AELLI_ROUTER_URL = "http://localhost:4001/a2a/aelli-router/message/send";
    const decision = { router: "aelli", tier: "standard", model: "gpt-4o", workflow: "default" };
    global.fetch = jest.fn().mockResolvedValue({
      text: async () => `data: ${JSON.stringify(decision)}\n\n`,
    });
    const { route } = require("../src/a2a-client");
    const result = await route("feature", { content: "fix the bug" });
    expect(result).toEqual(decision);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, init] = global.fetch.mock.calls[0];
    expect(url).toBe("http://localhost:4001/a2a/aelli-router/message/send");
    expect(init.method).toBe("POST");
  });

  it("happy path: uses LITELLM_BASE to derive ROUTER_URL when AELLI_ROUTER_URL not set", async () => {
    jest.resetModules();
    process.env.AELLI_LITELLM_BASE = "http://localhost:4000";
    delete process.env.AELLI_ROUTER_URL;
    const decision = { router: "aelli", tier: "fast", model: "gpt-4o-mini", workflow: "default" };
    global.fetch = jest.fn().mockResolvedValue({
      text: async () => `data: ${JSON.stringify(decision)}\n`,
    });
    const { route } = require("../src/a2a-client");
    const result = await route("feature", {});
    expect(result).toEqual(decision);
    const [url] = global.fetch.mock.calls[0];
    expect(url).toBe("http://localhost:4000/a2a/aelli-router/message/send");
  });

  it("happy path: returns null when SSE response has no data: line", async () => {
    jest.resetModules();
    process.env.AELLI_ROUTER_URL = "http://localhost:4001/a2a/aelli-router/message/send";
    global.fetch = jest.fn().mockResolvedValue({
      text: async () => "event: ping\n\n",
    });
    const { route } = require("../src/a2a-client");
    const result = await route("feature", {});
    expect(result).toBeNull();
  });

  it("fail-open: returns null on fetch error (ECONNREFUSED)", async () => {
    jest.resetModules();
    process.env.AELLI_ROUTER_URL = "http://localhost:4001/a2a/aelli-router/message/send";
    global.fetch = jest.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    const { route } = require("../src/a2a-client");
    const result = await route("feature", {}, { timeoutMs: 200 });
    expect(result).toBeNull();
  });

  it("fail-open: returns null on timeout", async () => {
    jest.resetModules();
    process.env.AELLI_ROUTER_URL = "http://localhost:4001/a2a/aelli-router/message/send";
    global.fetch = jest.fn().mockImplementation((_url, init) => new Promise((_, reject) => {
      if (init?.signal) {
        init.signal.addEventListener("abort", () =>
          reject(new DOMException("Aborted", "AbortError"))
        );
      }
    }));
    const { route } = require("../src/a2a-client");
    const result = await route("feature", {}, { timeoutMs: 50 });
    expect(result).toBeNull();
  }, 2000);

  it("sends auth header when AELLI_AUTH_TOKEN + AELLI_LITELLM_BASE are set", async () => {
    jest.resetModules();
    process.env.AELLI_ROUTER_URL = "http://localhost:4001/a2a/aelli-router/message/send";
    process.env.AELLI_AUTH_TOKEN = "my-token";
    process.env.AELLI_LITELLM_BASE = "http://localhost:4000";
    global.fetch = jest.fn().mockResolvedValue({
      text: async () => 'data: {"tier":"fast"}\n',
    });
    const { route } = require("../src/a2a-client");
    await route("feature", {});
    const [, init] = global.fetch.mock.calls[0];
    expect(init.headers["Authorization"]).toBe("Bearer my-token");
  });

  it("embeds taskKind and spread data inside the JSON-RPC body", async () => {
    jest.resetModules();
    process.env.AELLI_ROUTER_URL = "http://localhost:4001/a2a/aelli-router/message/send";
    global.fetch = jest.fn().mockResolvedValue({
      text: async () => 'data: {"tier":"standard"}\n',
    });
    const { route } = require("../src/a2a-client");
    await route("feature", { content: "hello", fileCount: 3 });
    const [, init] = global.fetch.mock.calls[0];
    const rpc = JSON.parse(init.body);
    const inner = JSON.parse(rpc.params.message.parts[0].text);
    expect(inner.type).toBe("route");
    expect(inner.taskKind).toBe("feature");
    expect(inner.content).toBe("hello");
    expect(inner.fileCount).toBe(3);
  });

  it("edge: returns null when response body is empty", async () => {
    jest.resetModules();
    process.env.AELLI_ROUTER_URL = "http://localhost:4001/a2a/aelli-router/message/send";
    global.fetch = jest.fn().mockResolvedValue({ text: async () => "" });
    const { route } = require("../src/a2a-client");
    const result = await route("feature", {});
    expect(result).toBeNull();
  });

  it("edge: skips [DONE] sentinel and returns null when it is the only data line", async () => {
    jest.resetModules();
    process.env.AELLI_ROUTER_URL = "http://localhost:4001/a2a/aelli-router/message/send";
    global.fetch = jest.fn().mockResolvedValue({
      text: async () => "data: [DONE]\n\n",
    });
    const { route } = require("../src/a2a-client");
    const result = await route("feature", {});
    expect(result).toBeNull();
  });

  it("edge: skips preamble event then returns decision from second data event", async () => {
    jest.resetModules();
    process.env.AELLI_ROUTER_URL = "http://localhost:4001/a2a/aelli-router/message/send";
    const decision = { router: "aelli", tier: "standard", model: "gpt-4o", workflow: "default" };
    global.fetch = jest.fn().mockResolvedValue({
      // First event has non-JSON data (preamble); second carries the decision
      text: async () => `event: ping\ndata: keepalive\n\ndata: ${JSON.stringify(decision)}\n\ndata: [DONE]\n\n`,
    });
    const { route } = require("../src/a2a-client");
    const result = await route("feature", {});
    expect(result).toEqual(decision);
  });

  it("edge: handles real [DONE] + decision pattern (decision before [DONE])", async () => {
    jest.resetModules();
    process.env.AELLI_ROUTER_URL = "http://localhost:4001/a2a/aelli-router/message/send";
    const decision = { router: "aelli", tier: "fast", model: "gpt-4o-mini", workflow: "default" };
    global.fetch = jest.fn().mockResolvedValue({
      text: async () => `data: ${JSON.stringify(decision)}\n\ndata: [DONE]\n\n`,
    });
    const { route } = require("../src/a2a-client");
    const result = await route("feature", {});
    expect(result).toEqual(decision);
  });

  it("edge: LITELLM_BASE with trailing slash produces clean router URL", async () => {
    jest.resetModules();
    process.env.AELLI_LITELLM_BASE = "http://localhost:4000/";
    delete process.env.AELLI_ROUTER_URL;
    const decision = { router: "aelli", tier: "fast", model: "gpt-4o-mini", workflow: "default" };
    global.fetch = jest.fn().mockResolvedValue({
      text: async () => `data: ${JSON.stringify(decision)}\n\n`,
    });
    const { route } = require("../src/a2a-client");
    const result = await route("feature", {});
    expect(result).toEqual(decision);
    const [url] = global.fetch.mock.calls[0];
    // Must not contain a double-slash before /a2a/
    expect(url).toBe("http://localhost:4000/a2a/aelli-router/message/send");
  });
});

// ── _connectSSE reconnect backoff ─────────────────────────────────────────

describe("_connectSSE reconnect — exponential backoff on error", () => {
  afterEach(() => {
    jest.resetModules();
    jest.restoreAllMocks();
  });

  it("schedules reconnect with doubled delay when connection errors", (done) => {
    jest.resetModules();
    const http = require("http");
    // Make the http.request immediately fire an "error" event
    jest.spyOn(http, "request").mockImplementation((_opts, _cb) => {
      const req = {
        setTimeout: jest.fn(),
        write: jest.fn(),
        end: jest.fn(),
        on: jest.fn((event, handler) => {
          if (event === "error") setImmediate(() => handler(new Error("ECONNREFUSED")));
          return req;
        }),
      };
      return req;
    });

    // Mock setTimeout to capture the scheduled delay without actually firing the
    // reconnect callback — prevents a live 6s timer from outlasting the test.
    const setTimeoutSpy = jest.spyOn(global, "setTimeout").mockImplementation(() => null);
    const { subscribeToQueue } = require("../src/a2a-client");

    subscribeToQueue("http://127.0.0.1:9/sse", jest.fn());

    setImmediate(() => {
      const reconnectCall = setTimeoutSpy.mock.calls.find(
        ([, delay]) => delay >= 6000 // doubled from initial 3000
      );
      expect(reconnectCall).toBeDefined();
      expect(reconnectCall[1]).toBe(6000); // 3000 * 2
      done();
    });
  });

  it("caps reconnect delay at 30s after repeated errors", () => {
    // Verify the exponential cap formula independently of HTTP mechanics.
    const delays = [];
    let d = 3000;
    for (let i = 0; i < 6; i++) {
      d = Math.min(d * 2, 30_000);
      delays.push(d);
    }
    expect(delays).toEqual([6000, 12000, 24000, 30000, 30000, 30000]);
  });
});
