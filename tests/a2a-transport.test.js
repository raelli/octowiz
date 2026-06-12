const http = require("http");
const {
  buildEnvelope,
  extractArtifact,
  httpJson,
  sendEvent,
} = require("../src/a2a-transport");

function listen(handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

describe("buildEnvelope", () => {
  it("builds the minimal route-style envelope", () => {
    expect(buildEnvelope("message/send", '{"type":"route"}')).toEqual({
      jsonrpc: "2.0",
      method: "message/send",
      params: { message: { parts: [{ kind: "text", text: '{"type":"route"}' }] } },
    });
  });

  it("includes id, role, and messageId when given", () => {
    const env = buildEnvelope("octowiz/event", "{}", {
      id: "daemon-1",
      role: "user",
      messageId: "m-1",
    });
    expect(env.id).toBe("daemon-1");
    expect(env.params.message.role).toBe("user");
    expect(env.params.message.messageId).toBe("m-1");
    expect(env.params.message.parts).toEqual([{ kind: "text", text: "{}" }]);
  });

  it("emits empty parts for a null text", () => {
    expect(buildEnvelope("message/send", null).params.message.parts).toEqual([]);
  });
});

describe("extractArtifact", () => {
  const rpc = {
    result: { artifacts: [{ parts: [{ text: '{"status":"completed","n":1}' }] }] },
  };

  it("parses the first artifact text", () => {
    expect(extractArtifact(rpc)).toEqual({ status: "completed", n: 1 });
  });

  it("returns the fallback when no artifact text is present", () => {
    expect(extractArtifact({}, null)).toBeNull();
    expect(extractArtifact({ result: {} }, {})).toEqual({});
    expect(extractArtifact(null, null)).toBeNull();
  });

  it("throws on malformed artifact JSON", () => {
    const bad = { result: { artifacts: [{ parts: [{ text: "not json" }] }] } };
    expect(() => extractArtifact(bad)).toThrow();
  });
});

describe("httpJson", () => {
  let server;
  afterEach((done) => {
    if (server) {
      server.close(done);
      server = null;
    } else done();
  });

  it("POSTs JSON and resolves status + parsed body", async () => {
    let seen;
    server = await listen((req, res) => {
      let data = "";
      req.on("data", (c) => (data += c));
      req.on("end", () => {
        seen = { body: JSON.parse(data), headers: req.headers, method: req.method };
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true }));
      });
    });
    const { port } = server.address();
    const { status, body } = await httpJson(
      "POST",
      `http://127.0.0.1:${port}/x`,
      { a: 1 },
      { headers: { "x-test": "yes" } }
    );
    expect(status).toBe(200);
    expect(body).toEqual({ ok: true });
    expect(seen.body).toEqual({ a: 1 });
    expect(seen.headers["x-test"]).toBe("yes");
    expect(seen.headers["content-type"]).toBe("application/json");
  });

  it("resolves raw text when the body is not JSON", async () => {
    server = await listen((req, res) => {
      res.writeHead(502);
      res.end("bad gateway");
    });
    const { port } = server.address();
    const { status, body } = await httpJson("POST", `http://127.0.0.1:${port}/x`, {});
    expect(status).toBe(502);
    expect(body).toBe("bad gateway");
  });

  it("rejects on connection failure", async () => {
    await expect(
      httpJson("POST", "http://127.0.0.1:1/x", {}, { timeoutMs: 2000 })
    ).rejects.toThrow();
  });

  it("rejects with an explicit timeout error", async () => {
    server = await listen(() => {
      /* never respond */
    });
    const { port } = server.address();
    await expect(
      httpJson("POST", `http://127.0.0.1:${port}/x`, {}, { timeoutMs: 100 })
    ).rejects.toThrow(/timed out after 100ms/);
  });
});

describe("sendEvent", () => {
  let server;
  afterEach((done) => {
    if (server) {
      server.close(done);
      server = null;
    } else done();
  });

  it("wraps the payload in an envelope and returns the artifact", async () => {
    let seenEnvelope;
    server = await listen((req, res) => {
      let data = "";
      req.on("data", (c) => (data += c));
      req.on("end", () => {
        seenEnvelope = JSON.parse(data);
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            result: { artifacts: [{ parts: [{ text: '{"status":"completed"}' }] }] },
          })
        );
      });
    });
    const { port } = server.address();
    const artifact = await sendEvent(`http://127.0.0.1:${port}/a2a/octowiz`, {
      method: "octowiz/event",
      id: "daemon-1",
      payload: { capability: "octowiz.plan", task: "t" },
    });
    expect(artifact).toEqual({ status: "completed" });
    expect(seenEnvelope.jsonrpc).toBe("2.0");
    expect(seenEnvelope.method).toBe("octowiz/event");
    expect(JSON.parse(seenEnvelope.params.message.parts[0].text)).toEqual({
      capability: "octowiz.plan",
      task: "t",
    });
  });

  it("returns the fallback when the response has no artifact", async () => {
    server = await listen((req, res) => {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ result: {} }));
    });
    const { port } = server.address();
    const artifact = await sendEvent(`http://127.0.0.1:${port}/x`, {
      method: "octowiz/event",
      payload: {},
    });
    expect(artifact).toEqual({});
  });

  it("throws on non-200 with the status and body excerpt", async () => {
    server = await listen((req, res) => {
      res.writeHead(500);
      res.end("boom");
    });
    const { port } = server.address();
    await expect(
      sendEvent(`http://127.0.0.1:${port}/x`, { method: "octowiz/event", payload: {} })
    ).rejects.toThrow(/A2A server returned HTTP 500.*boom/);
  });

  it("throws a parse error on malformed artifact JSON", async () => {
    server = await listen((req, res) => {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({ result: { artifacts: [{ parts: [{ text: "not json" }] }] } })
      );
    });
    const { port } = server.address();
    await expect(
      sendEvent(`http://127.0.0.1:${port}/x`, { method: "octowiz/event", payload: {} })
    ).rejects.toThrow(/Failed to parse A2A response/);
  });
});
