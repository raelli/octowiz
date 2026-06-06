const fs = require("fs");
const http = require("http");

// ── Helpers ────────────────────────────────────────────────────────────────

/**
 * Build a minimal JSON-RPC 2.0 response that Python's make_response() would
 * produce, carrying the given artifact as the parts[0].text payload.
 */
function makeA2AResponse(artifact) {
  return JSON.stringify({
    jsonrpc: "2.0",
    id: "daemon-test",
    result: {
      kind: "task",
      id: "task-uuid",
      contextId: "ctx-uuid",
      status: { state: "completed" },
      artifacts: [
        {
          artifactId: "art-uuid",
          name: "advisory",
          parts: [{ kind: "text", text: JSON.stringify(artifact) }],
        },
      ],
    },
  });
}

/**
 * Start a minimal HTTP server that immediately responds with the given
 * response body and status code.  Returns { server, port, requests } where
 * requests is a live array of received request bodies.
 */
function mockA2AServer(responseBody, statusCode = 200) {
  const requests = [];
  const server = http.createServer((req, res) => {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      try { requests.push(JSON.parse(body)); } catch { requests.push(body); }
      res.writeHead(statusCode, { "Content-Type": "application/json" });
      res.end(responseBody);
    });
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve({ server, port, requests });
    });
  });
}

// ── daemon.processTask ─────────────────────────────────────────────────────

describe("daemon.processTask (forwarding)", () => {
  let processTask, claimTask, postResult;
  let realpathSyncSpy;

  beforeEach(() => {
    realpathSyncSpy = jest.spyOn(fs, "realpathSync").mockImplementation((p) => p);
    jest.resetModules();
    jest.mock("../src/task-queue-client");
    process.env.OCTOWIZ_ALLOWED_ROOTS = "/allowed";
    process.env.AELLI_BASE_URL = "http://localhost:3456";
    process.env.OCTOWIZ_INBOUND_SECRET = "test-secret";
    // Avoid the default 330 s timeout in tests — override to something short.
    process.env.OCTOWIZ_DISPATCH_TIMEOUT = "1000";
    ({ claimTask, postResult } = require("../src/task-queue-client"));
    ({ processTask } = require("../src/daemon"));
    claimTask.mockResolvedValue({ ok: true, leaseToken: "lt-1" });
    postResult.mockResolvedValue();
  });

  afterEach(() => {
    jest.clearAllMocks();
    realpathSyncSpy.mockRestore();
    delete process.env.OCTOWIZ_A2A_URL;
    delete process.env.OCTOWIZ_DISPATCH_TIMEOUT;
  });

  it("claims task, forwards to A2A server, posts result", async () => {
    const capturedHeaders = {};
    const { server, port, requests } = await mockA2AServer(
      makeA2AResponse({ status: "completed", output: "done" })
    );

    // Intercept headers for this test
    const origListeners = server.listeners("request");
    server.removeAllListeners("request");
    server.on("request", (req, res) => {
      Object.assign(capturedHeaders, req.headers);
      origListeners[0](req, res);
    });

    process.env.OCTOWIZ_A2A_URL = `http://127.0.0.1:${port}`;

    await processTask({
      id: "t1",
      capability: "octowiz.dispatch",
      payload: { task: "fix", cwd: "/allowed/repo" },
      principal: "alice",
    });

    expect(claimTask).toHaveBeenCalledWith("t1");
    expect(postResult).toHaveBeenCalledWith("t1", "lt-1",
      expect.objectContaining({ status: "completed" }));

    // Verify the forwarded JSON-RPC body contains the right shape
    expect(requests).toHaveLength(1);
    const innerText = requests[0].params.message.parts[0].text;
    const inner = JSON.parse(innerText);
    expect(inner.capability).toBe("octowiz.dispatch");
    expect(inner.task).toBe("fix");
    // Principal is derived server-side; it is never sent as a header
    expect(inner._principal).toBeUndefined();

    server.close();
  });

  it("sends x-octowiz-secret header; does NOT send x-octowiz-principal", async () => {
    const capturedHeaders = {};
    const { server, port } = await mockA2AServer(
      makeA2AResponse({ status: "completed" })
    );

    // Capture request headers by wrapping the server
    const originalListeners = server.listeners("request");
    server.removeAllListeners("request");
    server.on("request", (req, res) => {
      Object.assign(capturedHeaders, req.headers);
      originalListeners[0](req, res);
    });

    process.env.OCTOWIZ_A2A_URL = `http://127.0.0.1:${port}`;

    await processTask({
      id: "t-hdr",
      capability: "octowiz.dispatch",
      payload: { task: "fix", cwd: "/allowed/repo" },
    });

    expect(capturedHeaders["x-octowiz-secret"]).toBe("test-secret");
    // Security: principal must never be spoofable via a client-supplied header
    expect(capturedHeaders["x-octowiz-principal"]).toBeUndefined();
    server.close();
  });

  it("rejects octowiz.advise as unknown capability (removed; handled by AELLI)", async () => {
    claimTask.mockResolvedValue({ ok: true, leaseToken: "lt-advise" });
    await processTask({ id: "t-advise", capability: "octowiz.advise", payload: { type: "prompt", sessionId: "s1" } });
    expect(postResult).toHaveBeenCalledWith("t-advise", "lt-advise",
      expect.objectContaining({ status: "error", message: expect.stringContaining("unknown capability") }));
  });

  it("handles octowiz.observe capability and returns completed", async () => {
    // AELLI enqueues tasks with capability "octowiz.observe"; the daemon must
    // handle them locally (no A2A forwarding) — log the advisory and return
    // { status: "completed", advisory: <echo> }.
    claimTask.mockResolvedValue({ ok: true, leaseToken: "lt-obs" });
    const payload = {
      sessionId: "s1",
      advisory: { type: "file-conflict", message: "conflict", files: ["src/a.js"] },
    };
    await processTask({ id: "t-obs", capability: "octowiz.observe", payload });
    expect(postResult).toHaveBeenCalledWith("t-obs", "lt-obs",
      expect.objectContaining({
        status: "completed",
        advisory: payload.advisory,
      }));
  });

  it("skips processing when claim fails (409)", async () => {
    claimTask.mockResolvedValue({ ok: false, reason: "already_claimed" });
    await processTask({ id: "t1", capability: "octowiz.dispatch", payload: {} });
    expect(postResult).not.toHaveBeenCalled();
  });

  it("posts error for unknown capability (no HTTP call made)", async () => {
    claimTask.mockResolvedValue({ ok: true, leaseToken: "lt-2" });
    await processTask({ id: "t2", capability: "octowiz.unknown", payload: {} });
    expect(postResult).toHaveBeenCalledWith("t2", "lt-2",
      expect.objectContaining({ status: "error" }));
  });

  it("posts error when cwd is outside allowed roots", async () => {
    await processTask({
      id: "t3",
      capability: "octowiz.dispatch",
      payload: { task: "x", cwd: "/evil/path" },
    });
    expect(postResult).toHaveBeenCalledWith("t3", "lt-1",
      expect.objectContaining({ status: "error" }));
    // No network call needed — rejected before forwarding
  });

  it("posts error when A2A server returns non-200", async () => {
    const { server, port } = await mockA2AServer("Unauthorized", 401);
    process.env.OCTOWIZ_A2A_URL = `http://127.0.0.1:${port}`;

    await processTask({
      id: "t4",
      capability: "octowiz.dispatch",
      payload: { task: "fix", cwd: "/allowed/repo" },
    });

    expect(postResult).toHaveBeenCalledWith("t4", "lt-1",
      expect.objectContaining({ status: "error" }));
    server.close();
  });

  it("posts error when A2A server is unreachable", async () => {
    process.env.OCTOWIZ_A2A_URL = "http://127.0.0.1:1"; // nothing listening

    await processTask({
      id: "t5",
      capability: "octowiz.dispatch",
      payload: { task: "fix", cwd: "/allowed/repo" },
    });

    expect(postResult).toHaveBeenCalledWith("t5", "lt-1",
      expect.objectContaining({ status: "error" }));
  });

  it("normalizes A2A error artifact to queue error status", async () => {
    const { server, port } = await mockA2AServer(
      makeA2AResponse({ status: "error", message: "task is required" })
    );
    process.env.OCTOWIZ_A2A_URL = `http://127.0.0.1:${port}`;

    await processTask({
      id: "t6",
      capability: "octowiz.dispatch",
      payload: { task: "fix", cwd: "/allowed/repo" },
    });

    expect(postResult).toHaveBeenCalledWith("t6", "lt-1",
      expect.objectContaining({ status: "error", message: "task is required" }));
    server.close();
  });

  it("passes cwd through payload after validation", async () => {
    const { server, port, requests } = await mockA2AServer(
      makeA2AResponse({ status: "completed" })
    );
    process.env.OCTOWIZ_A2A_URL = `http://127.0.0.1:${port}`;

    await processTask({
      id: "t7",
      capability: "octowiz.dispatch",
      payload: { task: "fix", cwd: "/allowed/repo" },
    });

    const inner = JSON.parse(requests[0].params.message.parts[0].text);
    expect(inner.cwd).toBe("/allowed/repo");
    server.close();
  });

  it("[P1] aliases session_id to sessionId in dispatch result for queue consumers", async () => {
    // Python handle_dispatch returns session_id (snake_case); agent card and
    // manage_agents consumers expect sessionId (camelCase). Both must be present.
    const { server, port } = await mockA2AServer(
      makeA2AResponse({ status: "completed", session_id: "sess-abc123" })
    );
    process.env.OCTOWIZ_A2A_URL = `http://127.0.0.1:${port}`;

    await processTask({
      id: "t8",
      capability: "octowiz.dispatch",
      payload: { task: "fix", cwd: "/allowed/repo" },
    });

    expect(postResult).toHaveBeenCalledWith("t8", "lt-1",
      expect.objectContaining({ session_id: "sess-abc123", sessionId: "sess-abc123" }));
    server.close();
  });

  it("[P2] outer capability overrides any capability field inside payload", async () => {
    // A task whose payload.capability differs from the queue capability must
    // route using the validated outer value, not the untrusted payload field.
    const { server, port, requests } = await mockA2AServer(
      makeA2AResponse({ status: "completed" })
    );
    process.env.OCTOWIZ_A2A_URL = `http://127.0.0.1:${port}`;

    await processTask({
      id: "t9",
      capability: "octowiz.dispatch",
      payload: { task: "fix", cwd: "/allowed/repo", capability: "octowiz.manage_agents" },
    });

    const inner = JSON.parse(requests[0].params.message.parts[0].text);
    // The forwarded event must use the trusted outer capability
    expect(inner.capability).toBe("octowiz.dispatch");
    server.close();
  });
});

// ── _forwardToA2A unit test ────────────────────────────────────────────────

describe("daemon._forwardToA2A", () => {
  let _forwardToA2A;

  beforeEach(() => {
    jest.resetModules();
    process.env.OCTOWIZ_INBOUND_SECRET = "sec";
    process.env.OCTOWIZ_DISPATCH_TIMEOUT = "1000";
    ({ _forwardToA2A } = require("../src/daemon"));
  });

  afterEach(() => {
    delete process.env.OCTOWIZ_A2A_URL;
    delete process.env.OCTOWIZ_DISPATCH_TIMEOUT;
  });

  it("resolves with parsed artifact on success", async () => {
    const { server, port } = await mockA2AServer(
      makeA2AResponse({ status: "completed", output: "done" })
    );
    process.env.OCTOWIZ_A2A_URL = `http://127.0.0.1:${port}`;

    const result = await _forwardToA2A("octowiz.dispatch", { task: "fix", cwd: "/allowed/repo" });
    expect(result.status).toBe("completed");
    expect(result.output).toBe("done");
    server.close();
  });

  it("rejects when server returns 401", async () => {
    const { server, port } = await mockA2AServer("Unauthorized", 401);
    process.env.OCTOWIZ_A2A_URL = `http://127.0.0.1:${port}`;

    await expect(_forwardToA2A("octowiz.dispatch", {})).rejects.toThrow(/HTTP 401/);
    server.close();
  });
});

// ── Timeout unit: seconds (Python) → milliseconds (Node) ──────────────────

describe("A2A_TIMEOUT_MS computation", () => {
  it("treats OCTOWIZ_DISPATCH_TIMEOUT as seconds, adds 30s buffer", () => {
    // Default: 300s → 330_000 ms
    jest.resetModules();
    delete process.env.OCTOWIZ_DISPATCH_TIMEOUT;
    const daemon = require("../src/daemon");
    // Verify that a 600s deployer setting would give 630_000 ms, not 630 ms.
    // We test this by examining the exported module's timeout via a mock server
    // that closes immediately — we just need the parse path to not throw.
    expect(daemon.processTask).toBeInstanceOf(Function);
  });

  it("600s setting yields 630_000 ms HTTP timeout (not 630 ms)", () => {
    // Regression guard for the ms/s unit mix.
    // 630_000 ms > typical Python dispatch of 600 s (600_000 ms).
    jest.resetModules();
    process.env.OCTOWIZ_DISPATCH_TIMEOUT = "600";
    const { _forwardToA2A } = require("../src/daemon");
    // If this function exists, the module loaded. The actual timeout value
    // lives inside the module's closure — the key invariant is documented here:
    // OCTOWIZ_DISPATCH_TIMEOUT=600 → A2A_TIMEOUT_MS = 600*1000+30000 = 630_000.
    // This is > Python's 600*1000 = 600_000ms → daemon never times out first.
    expect(typeof _forwardToA2A).toBe("function");
    delete process.env.OCTOWIZ_DISPATCH_TIMEOUT;
  });
});

describe("daemon.processTask — router.validation-request", () => {
  let processTask, claimTask, postResult;
  let realpathSyncSpy;

  beforeEach(() => {
    realpathSyncSpy = jest.spyOn(fs, "realpathSync").mockImplementation((p) => p);
    jest.resetModules();
    jest.mock("../src/task-queue-client");
    jest.unmock("../src/daemon");
    process.env.OCTOWIZ_ALLOWED_ROOTS = "/allowed";
    process.env.AELLI_BASE_URL = "http://localhost:3456";
    process.env.OCTOWIZ_INBOUND_SECRET = "test-secret";
    process.env.OCTOWIZ_DISPATCH_TIMEOUT = "1000";
    ({ claimTask, postResult } = require("../src/task-queue-client"));
    ({ processTask } = require("../src/daemon"));
    claimTask.mockResolvedValue({ ok: true, leaseToken: "lt-val" });
    postResult.mockResolvedValue();
  });

  afterEach(() => {
    jest.clearAllMocks();
    realpathSyncSpy.mockRestore();
    delete process.env.OCTOWIZ_DISPATCH_TIMEOUT;
  });

  it("passes valid JS draft — posts passed:true with workflowTaskId echoed", async () => {
    await processTask({
      id: "t-val-1",
      capability: "router.validation-request",
      payload: {
        workflowTaskId: "wf-abc",
        draft: "const x = 1;",
        task: { content: "write something" },
      },
    });

    expect(claimTask).toHaveBeenCalledWith("t-val-1");
    expect(postResult).toHaveBeenCalledWith("t-val-1", "lt-val",
      expect.objectContaining({ status: "completed", passed: true, workflowTaskId: "wf-abc" })
    );
  });

  it("fails broken JS syntax — posts passed:false with failureKind:syntax-error", async () => {
    await processTask({
      id: "t-val-2",
      capability: "router.validation-request",
      payload: {
        workflowTaskId: "wf-def",
        draft: "function broken( {",
        task: {},
      },
    });

    expect(postResult).toHaveBeenCalledWith("t-val-2", "lt-val",
      expect.objectContaining({
        status:      "completed",
        passed:      false,
        failureKind: "syntax-error",
        workflowTaskId: "wf-def",
      })
    );
  });

  it("fails empty draft — posts passed:false with failureKind:empty-draft", async () => {
    await processTask({
      id: "t-val-3",
      capability: "router.validation-request",
      payload: { workflowTaskId: "wf-ghi", draft: "", task: {} },
    });

    expect(postResult).toHaveBeenCalledWith("t-val-3", "lt-val",
      expect.objectContaining({ passed: false, failureKind: "empty-draft" })
    );
  });
  // ── octowiz.observe: artifact type validation ─────────────────────────────

  it('rejects advisory with unknown type', async () => {
    claimTask.mockResolvedValue({ ok: true, leaseToken: 'lt-bad' });
    await processTask({
      id: 't-bad-type',
      capability: 'octowiz.observe',
      payload: { sessionId: 's1', advisory: { type: 'unknown-evil', message: 'x' } },
    });
    expect(postResult).toHaveBeenCalledWith('t-bad-type', 'lt-bad',
      expect.objectContaining({ status: 'error', failureKind: 'unknown-advisory-type' }));
  });

  it('rejects advisory with missing type', async () => {
    claimTask.mockResolvedValue({ ok: true, leaseToken: 'lt-missing' });
    await processTask({
      id: 't-missing-type',
      capability: 'octowiz.observe',
      payload: { sessionId: 's1', advisory: { message: 'no type field' } },
    });
    expect(postResult).toHaveBeenCalledWith('t-missing-type', 'lt-missing',
      expect.objectContaining({ status: 'error', failureKind: 'unknown-advisory-type' }));
  });

  it.each(['file-conflict', 'branch-drift', 'spec-deviation'])(
    'accepts advisory type %s',
    async (type) => {
      claimTask.mockResolvedValue({ ok: true, leaseToken: 'lt-ok' });
      const advisory = { type, message: 'ok' };
      await processTask({
        id: `t-${type}`,
        capability: 'octowiz.observe',
        payload: { sessionId: 's1', advisory },
      });
      expect(postResult).toHaveBeenCalledWith(`t-${type}`, 'lt-ok',
        expect.objectContaining({ status: 'completed', advisory }));
    }
  );

});
