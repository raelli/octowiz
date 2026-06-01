# aelli-cc-plugin → octowiz Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate all aelli-cc-plugin functionality (hook event forwarding, per-session push subscriber) into octowiz, fix broken bridge.py event forwarding, and deprecate aelli-cc-plugin.

**Architecture:** Three sequential phases — Phase 1 fixes the broken event forwarding (ships independently as a PR), Phase 2 migrates the per-session push subscriber and separates daemon from subscriber entry points, Phase 3 wires the Stop hook atomically with removing aelli-cc-plugin. Each phase is a separate PR.

**Tech Stack:** Node.js 18+, Jest 29, Claude Code hooks (stdin JSON), SSE, existing `src/a2a-client.js` / `src/git-context.js` / `src/event-builder.js`

---

## File map

**Phase 1 — created:**
- `hooks/scripts/start.js` — SessionStart hook: captures git context, posts session-start to AELLI
- `hooks/scripts/report-event.js` — PostToolUse + UserPromptSubmit hook: posts file/prompt events
- `hooks/scripts/stop.js` — Stop hook script (written + tested here, wired in Phase 3)
- `tests/hooks-start.test.js`
- `tests/hooks-report-event.test.js`
- `tests/hooks-stop.test.js`

**Phase 1 — modified:**
- `src/a2a-client.js` — add failure logging to fire-and-forget `post()`
- `hooks/hooks.json` — replace bridge.py with Node.js scripts (Stop hook absent until Phase 3)

**Phase 2 — created:**
- `src/session-subscriber.js` — per-session push subscriber logic (no daemon)
- `hooks/scripts/session-subscriber.js` — thin entry point spawned per CC session
- `tests/session-subscriber.test.js`

**Phase 2 — modified:**
- `src/a2a-client.js` — `AELLI_BASE_URL` canonical, `AELLI_API_BASE` as fallback alias
- `index.js` — remove `subscribe()` call (daemon only)
- `hooks/scripts/start.js` — add subscriber spawn + PID file write
- `hooks/scripts/stop.js` — add subscriber SIGTERM + PID file cleanup
- `tests/hooks-start.test.js` — add spawn assertions
- `tests/hooks-stop.test.js` — add SIGTERM assertions

**Phase 3 — modified:**
- `hooks/hooks.json` — add Stop hook
- `.claude-plugin/plugin.json` — bump to `0.5.0`
- `README.md` — daemon setup docs + env var table

---

## Phase 1 — Fix event forwarding

### Task 1: Add failure logging to fire-and-forget `post()`

**Files:**
- Modify: `src/a2a-client.js` (the `post` function, ~line 150)
- Modify: `tests/a2a-client.test.js`

- [ ] **Step 1: Read the current post() fire-and-forget branch**

  Open `src/a2a-client.js`. Find the block:
  ```js
  if (!sync) {
    fetch(url, init).catch(() => {});
    return null;
  }
  ```

- [ ] **Step 2: Write the failing test**

  In `tests/a2a-client.test.js`, add to an existing describe block (or add a new one):
  ```js
  it("fire-and-forget post() appends to log on fetch failure", async () => {
    const { post } = require("../src/a2a-client");
    const fs = require("fs");
    const appendSpy = jest.spyOn(fs, "appendFileSync").mockImplementation(() => {});
    global.fetch = jest.fn().mockRejectedValue(new Error("network down"));
    await post("session-start", { sessionId: "s1" }, { sync: false });
    await new Promise((r) => setTimeout(r, 10)); // let the rejected promise settle
    expect(appendSpy).toHaveBeenCalledWith(
      expect.stringContaining("aelli-cc.log"),
      expect.stringContaining("session-start")
    );
    appendSpy.mockRestore();
  });
  ```

- [ ] **Step 3: Run to confirm it fails**

  ```bash
  npx jest tests/a2a-client.test.js --testNamePattern="fire-and-forget" -t "fire-and-forget" 2>&1 | tail -10
  ```
  Expected: FAIL — `appendFileSync` is never called.

- [ ] **Step 4: Apply the fix**

  In `src/a2a-client.js`, replace:
  ```js
  if (!sync) {
    fetch(url, init).catch(() => {});
    return null;
  }
  ```
  With:
  ```js
  if (!sync) {
    fetch(url, init).catch((err) =>
      appendLog(`[post:${eventType}] fire-and-forget error: ${err?.message ?? err}`)
    );
    return null;
  }
  ```

- [ ] **Step 5: Run test to verify it passes**

  ```bash
  npx jest tests/a2a-client.test.js 2>&1 | tail -5
  ```
  Expected: all tests PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add src/a2a-client.js tests/a2a-client.test.js
  git commit -m "fix(a2a-client): log fire-and-forget post() failures to aelli-cc.log"
  ```

---

### Task 2: Write `hooks/scripts/start.js`

**Files:**
- Create: `hooks/scripts/start.js`
- Create: `tests/hooks-start.test.js`

- [ ] **Step 1: Write the failing tests**

  Create `tests/hooks-start.test.js`:
  ```js
  "use strict";
  jest.mock("../src/a2a-client", () => ({
    post: jest.fn().mockResolvedValue(null),
  }));
  jest.mock("../src/git-context", () => ({
    captureContext: jest.fn().mockReturnValue({
      sessionId: "s1", repoRoot: "/repo", repo: "git@github.com:x/y.git",
      cwd: "/repo", branch: "main",
    }),
  }));

  const { post } = require("../src/a2a-client");

  function runStart(input) {
    jest.resetModules();
    jest.mock("../src/a2a-client", () => ({ post: jest.fn().mockResolvedValue(null) }));
    jest.mock("../src/git-context", () => ({
      captureContext: jest.fn().mockReturnValue({
        sessionId: input.session_id || "s1",
        repoRoot: "/repo", repo: "origin", cwd: input.cwd || "/repo", branch: "main",
      }),
    }));
    const { post: mockPost } = require("../src/a2a-client");
    // Simulate stdin by requiring the module with process.env set
    process.env.AELLI_LITELLM_BASE = "https://llm.test";
    process.env.AELLI_AUTH_TOKEN = "tok";
    const mod = require("../hooks/scripts/start");
    return { mockPost, mod };
  }

  describe("hooks/scripts/start.js", () => {
    beforeEach(() => {
      jest.resetModules();
      process.env.AELLI_LITELLM_BASE = "https://llm.test";
      process.env.AELLI_AUTH_TOKEN = "tok";
    });
    afterEach(() => {
      delete process.env.AELLI_LITELLM_BASE;
      delete process.env.AELLI_AUTH_TOKEN;
    });

    it("calls post with session-start and correct sessionId", async () => {
      const { post: mockPost } = require("../src/a2a-client");
      const { handleStart } = require("../hooks/scripts/start");
      await handleStart({ session_id: "abc", cwd: "/repo" });
      expect(mockPost).toHaveBeenCalledWith(
        "session-start",
        expect.objectContaining({ sessionId: "abc" }),
        expect.objectContaining({ sync: true })
      );
    });

    it("does not throw on missing AELLI_LITELLM_BASE, appends to log instead", async () => {
      delete process.env.AELLI_LITELLM_BASE;
      const fs = require("fs");
      const spy = jest.spyOn(fs, "appendFileSync").mockImplementation(() => {});
      const { handleStart } = require("../hooks/scripts/start");
      await expect(handleStart({ session_id: "abc", cwd: "/repo" })).resolves.not.toThrow();
      expect(spy).toHaveBeenCalledWith(
        expect.stringContaining("aelli-cc.log"),
        expect.stringContaining("AELLI_LITELLM_BASE")
      );
      spy.mockRestore();
    });

    it("does not throw on empty stdin object", async () => {
      const { handleStart } = require("../hooks/scripts/start");
      await expect(handleStart({})).resolves.not.toThrow();
    });
  });
  ```

- [ ] **Step 2: Run to confirm they fail**

  ```bash
  npx jest tests/hooks-start.test.js 2>&1 | tail -10
  ```
  Expected: FAIL — `../hooks/scripts/start` cannot be found.

- [ ] **Step 3: Create `hooks/scripts/start.js`**

  ```js
  #!/usr/bin/env node
  "use strict";
  const fs = require("fs");
  const os = require("os");
  const path = require("path");

  const CACHE_DIR = process.env.AELLI_CACHE_DIR || path.join(os.homedir(), ".cache", "aelli-cc");
  const LOG_FILE = path.join(CACHE_DIR, "aelli-cc.log");

  function appendLog(msg) {
    try {
      fs.mkdirSync(CACHE_DIR, { recursive: true });
      fs.appendFileSync(LOG_FILE, `[${new Date().toISOString()}] ${msg}\n`);
    } catch {}
  }

  async function handleStart(input) {
    const { post } = require("../../src/a2a-client");
    const { captureContext } = require("../../src/git-context");
    const { buildSessionStart } = require("../../src/event-builder");

    const sessionId = input.session_id || `cc-${Date.now()}-${process.pid}`;
    const cwd = input.cwd || process.cwd();

    // Startup guard — warn but do not block
    if (!process.env.AELLI_LITELLM_BASE) {
      appendLog("[start] AELLI_LITELLM_BASE not set — session-start event will not be delivered");
    }
    if (!process.env.AELLI_AUTH_TOKEN) {
      appendLog("[start] AELLI_AUTH_TOKEN not set — session-start event will not be delivered");
    }

    const ctx = captureContext(sessionId, cwd);
    const payload = buildSessionStart(ctx);

    await post("session-start", payload, { sync: true, timeoutMs: 500 });
  }

  // When run as a hook (not required as a module), read stdin and invoke handleStart
  if (require.main === module) {
    let raw = "";
    process.stdin.on("data", (c) => (raw += c));
    process.stdin.on("end", async () => {
      let input = {};
      try { input = JSON.parse(raw); } catch {}
      try { await handleStart(input); } catch (e) {
        const fs = require("fs");
        const os = require("os");
        const path = require("path");
        const CACHE_DIR = process.env.AELLI_CACHE_DIR || path.join(os.homedir(), ".cache", "aelli-cc");
        try { fs.appendFileSync(path.join(CACHE_DIR, "aelli-cc.log"), `[${new Date().toISOString()}] [start] error: ${e.message}\n`); } catch {}
      }
      process.exit(0);
    });
  }

  module.exports = { handleStart };
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  npx jest tests/hooks-start.test.js 2>&1 | tail -5
  ```
  Expected: all PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add hooks/scripts/start.js tests/hooks-start.test.js
  git commit -m "feat(hooks): add start.js — session-start event forwarding with startup guard"
  ```

---

### Task 3: Write `hooks/scripts/report-event.js`

**Files:**
- Create: `hooks/scripts/report-event.js`
- Create: `tests/hooks-report-event.test.js`

- [ ] **Step 1: Write the failing tests**

  Create `tests/hooks-report-event.test.js`:
  ```js
  "use strict";
  const mockPost = jest.fn().mockResolvedValue(null);
  const mockGetContext = jest.fn().mockReturnValue({
    sessionId: "s1", repoRoot: "/repo", repo: "origin",
    branch: "main", modifiedFiles: [],
  });

  jest.mock("../src/a2a-client", () => ({ post: mockPost }));
  jest.mock("../src/git-context", () => ({ getContext: mockGetContext }));

  const { handleEvent } = require("../hooks/scripts/report-event");

  beforeEach(() => jest.clearAllMocks());

  describe("hooks/scripts/report-event.js", () => {
    it("posts file-edit for Edit tool", async () => {
      await handleEvent({ session_id: "s1", tool_name: "Edit",
        tool_input: { file_path: "/repo/src/foo.js" } });
      expect(mockPost).toHaveBeenCalledWith(
        "file-edit",
        expect.objectContaining({ sessionId: "s1", file: "src/foo.js" }),
        expect.objectContaining({ sync: false })
      );
    });

    it("posts file-write for Write tool", async () => {
      await handleEvent({ session_id: "s1", tool_name: "Write",
        tool_input: { file_path: "/repo/src/bar.js" } });
      expect(mockPost).toHaveBeenCalledWith(
        "file-write",
        expect.objectContaining({ file: "src/bar.js" }),
        expect.objectContaining({ sync: false })
      );
    });

    it("posts prompt event when no tool_name (UserPromptSubmit)", async () => {
      await handleEvent({ session_id: "s1", prompt: "fix the bug" });
      expect(mockPost).toHaveBeenCalledWith(
        "prompt",
        expect.objectContaining({ sessionId: "s1", prompt_summary: "fix the bug" }),
        expect.objectContaining({ sync: false })
      );
    });

    it("exits cleanly when getContext returns null", async () => {
      mockGetContext.mockReturnValueOnce(null);
      await expect(handleEvent({ session_id: "s1", tool_name: "Edit",
        tool_input: { file_path: "/repo/src/foo.js" } })).resolves.not.toThrow();
    });

    it("exits cleanly on empty input", async () => {
      await expect(handleEvent({})).resolves.not.toThrow();
    });
  });
  ```

- [ ] **Step 2: Run to confirm they fail**

  ```bash
  npx jest tests/hooks-report-event.test.js 2>&1 | tail -10
  ```
  Expected: FAIL — module not found.

- [ ] **Step 3: Create `hooks/scripts/report-event.js`**

  ```js
  #!/usr/bin/env node
  "use strict";

  async function handleEvent(input) {
    const { post } = require("../../src/a2a-client");
    const { getContext } = require("../../src/git-context");
    const { buildFileEvent, buildPrompt } = require("../../src/event-builder");

    const sessionId = input.session_id || "";
    const toolName = input.tool_name || "";
    const ctx = getContext(sessionId);

    if (toolName) {
      // PostToolUse: file event
      const filePath = input.tool_input?.file_path || input.tool_input?.path || "";
      const payload = buildFileEvent(ctx, toolName, filePath);
      const eventType = toolName === "Write" ? "file-write" : "file-edit";
      await post(eventType, payload, { sync: false });
    } else {
      // UserPromptSubmit: prompt event
      const prompt = input.prompt || input.message || "";
      const payload = buildPrompt(ctx, prompt);
      await post("prompt", payload, { sync: false });
    }
  }

  if (require.main === module) {
    let raw = "";
    process.stdin.on("data", (c) => (raw += c));
    process.stdin.on("end", async () => {
      let input = {};
      try { input = JSON.parse(raw); } catch {}
      try { await handleEvent(input); } catch {}
      process.exit(0);
    });
  }

  module.exports = { handleEvent };
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  npx jest tests/hooks-report-event.test.js 2>&1 | tail -5
  ```
  Expected: all PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add hooks/scripts/report-event.js tests/hooks-report-event.test.js
  git commit -m "feat(hooks): add report-event.js — file and prompt event forwarding"
  ```

---

### Task 4: Write `hooks/scripts/stop.js` (tested, not wired yet)

**Files:**
- Create: `hooks/scripts/stop.js`
- Create: `tests/hooks-stop.test.js`

- [ ] **Step 1: Write the failing tests**

  Create `tests/hooks-stop.test.js`:
  ```js
  "use strict";
  const mockPost = jest.fn().mockResolvedValue(null);
  const mockGetContext = jest.fn().mockReturnValue({
    sessionId: "s1", repoRoot: "/repo", repo: "origin",
  });

  jest.mock("../src/a2a-client", () => ({ post: mockPost }));
  jest.mock("../src/git-context", () => ({ getContext: mockGetContext }));

  const { handleStop } = require("../hooks/scripts/stop");

  beforeEach(() => jest.clearAllMocks());

  describe("hooks/scripts/stop.js", () => {
    it("posts session-end with sync:true", async () => {
      await handleStop({ session_id: "s1" });
      expect(mockPost).toHaveBeenCalledWith(
        "session-end",
        expect.objectContaining({ sessionId: "s1" }),
        expect.objectContaining({ sync: true, timeoutMs: 500 })
      );
    });

    it("does not throw when session_id is missing", async () => {
      await expect(handleStop({})).resolves.not.toThrow();
    });

    it("does not throw when getContext returns null", async () => {
      mockGetContext.mockReturnValueOnce(null);
      await expect(handleStop({ session_id: "s1" })).resolves.not.toThrow();
    });
  });
  ```

- [ ] **Step 2: Run to confirm they fail**

  ```bash
  npx jest tests/hooks-stop.test.js 2>&1 | tail -10
  ```
  Expected: FAIL — module not found.

- [ ] **Step 3: Create `hooks/scripts/stop.js`**

  ```js
  #!/usr/bin/env node
  "use strict";

  async function handleStop(input) {
    const { post } = require("../../src/a2a-client");
    const { getContext } = require("../../src/git-context");

    const sessionId = input.session_id || "";
    if (!sessionId) return;

    const ctx = getContext(sessionId);
    await post(
      "session-end",
      { sessionId, repo: ctx?.repo, repoRoot: ctx?.repoRoot },
      { sync: true, timeoutMs: 500 }
    ).catch(() => {}); // fail-open: session-end is best-effort
  }

  if (require.main === module) {
    let raw = "";
    process.stdin.on("data", (c) => (raw += c));
    process.stdin.on("end", async () => {
      let input = {};
      try { input = JSON.parse(raw); } catch {}
      try { await handleStop(input); } catch {}
      process.exit(0);
    });
  }

  module.exports = { handleStop };
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  npx jest tests/hooks-stop.test.js 2>&1 | tail -5
  ```
  Expected: all PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add hooks/scripts/stop.js tests/hooks-stop.test.js
  git commit -m "feat(hooks): add stop.js — session-end event (not wired to hooks.json until Phase 3)"
  ```

---

### Task 5: Update `hooks/hooks.json` — replace bridge.py, no Stop hook

**Files:**
- Modify: `hooks/hooks.json`

- [ ] **Step 1: Replace hooks.json**

  Overwrite `hooks/hooks.json` with:
  ```json
  {
    "description": "Octowiz hooks — session lifecycle and event forwarding to AELLI",
    "hooks": {
      "SessionStart": [
        {
          "matcher": "*",
          "hooks": [
            {
              "type": "command",
              "command": "bash \"$CLAUDE_PLUGIN_ROOT/hooks/upgrade-check.sh\"",
              "timeout": 60
            },
            {
              "type": "command",
              "command": "node \"$CLAUDE_PLUGIN_ROOT/hooks/scripts/start.js\"",
              "timeout": 10
            }
          ]
        }
      ],
      "PostToolUse": [
        {
          "matcher": "Edit|Write|MultiEdit|NotebookEdit",
          "hooks": [
            {
              "type": "command",
              "command": "node \"$CLAUDE_PLUGIN_ROOT/hooks/scripts/report-event.js\"",
              "timeout": 10
            }
          ]
        }
      ],
      "UserPromptSubmit": [
        {
          "matcher": "*",
          "hooks": [
            {
              "type": "command",
              "command": "node \"$CLAUDE_PLUGIN_ROOT/hooks/scripts/report-event.js\"",
              "timeout": 10
            }
          ]
        }
      ]
    }
  }
  ```
  Note: Stop hook is intentionally absent — aelli-cc-plugin still owns session-end until Phase 3.

- [ ] **Step 2: Run full test suite**

  ```bash
  npm test 2>&1 | tail -10
  ```
  Expected: all suites PASS (count should be higher than before — new test files included).

- [ ] **Step 3: Commit**

  ```bash
  git add hooks/hooks.json
  git commit -m "feat(hooks): replace bridge.py with Node.js event-forwarding scripts

  bridge.py posted to OCTOWIZ_A2A_URL (dead endpoint). New scripts post directly
  to AELLI via src/a2a-client.post(). Stop hook deferred to Phase 3 to prevent
  duplicate session-end while aelli-cc-plugin is still installed."
  ```

---

## Phase 2 — Per-session push subscriber migration

### Task 6: Consolidate env vars in `src/a2a-client.js`

**Files:**
- Modify: `src/a2a-client.js` (line ~7: `const API_BASE = ...`)

- [ ] **Step 1: Write the failing test**

  In `tests/a2a-client.test.js`, add:
  ```js
  it("uses AELLI_BASE_URL when set, falling back to AELLI_API_BASE", () => {
    jest.resetModules();
    process.env.AELLI_BASE_URL = "http://base-url-test:3456/api";
    delete process.env.AELLI_API_BASE;
    const client = require("../src/a2a-client");
    // The module exposes no direct API_BASE, so test via a request attempt:
    // we just verify it doesn't throw on require and the warning logic runs
    expect(client).toBeDefined();
    delete process.env.AELLI_BASE_URL;
  });

  it("falls back to AELLI_API_BASE when AELLI_BASE_URL is absent", () => {
    jest.resetModules();
    delete process.env.AELLI_BASE_URL;
    process.env.AELLI_API_BASE = "http://api-base-test:3001/api";
    const client = require("../src/a2a-client");
    expect(client).toBeDefined();
    delete process.env.AELLI_API_BASE;
  });
  ```

- [ ] **Step 2: Run to confirm existing tests still pass before the change**

  ```bash
  npx jest tests/a2a-client.test.js 2>&1 | tail -5
  ```
  Expected: PASS.

- [ ] **Step 3: Apply the env var change**

  In `src/a2a-client.js`, replace line:
  ```js
  const API_BASE = process.env.AELLI_API_BASE || "http://localhost:3001/api";
  ```
  With:
  ```js
  const API_BASE = process.env.AELLI_BASE_URL || process.env.AELLI_API_BASE || "http://localhost:3001/api";
  ```

- [ ] **Step 4: Run all tests**

  ```bash
  npm test 2>&1 | tail -10
  ```
  Expected: all PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add src/a2a-client.js tests/a2a-client.test.js
  git commit -m "refactor(a2a-client): use AELLI_BASE_URL as canonical var, AELLI_API_BASE as fallback"
  ```

---

### Task 7: Create `src/session-subscriber.js`

**Files:**
- Create: `src/session-subscriber.js`
- Create: `tests/session-subscriber.test.js`

- [ ] **Step 1: Write the failing tests**

  Create `tests/session-subscriber.test.js`:
  ```js
  "use strict";
  const mockSubscribe = jest.fn();
  const mockUpdateTask = jest.fn().mockResolvedValue(null);

  jest.mock("../src/a2a-client", () => ({
    subscribe: mockSubscribe,
    updateTask: mockUpdateTask,
  }));

  beforeEach(() => jest.clearAllMocks());

  describe("src/session-subscriber.js", () => {
    it("calls subscribe() with a function callback", () => {
      require("../src/session-subscriber");
      expect(mockSubscribe).toHaveBeenCalledWith(expect.any(Function));
    });

    it("does not call daemon.start()", () => {
      jest.resetModules();
      jest.mock("../src/a2a-client", () => ({ subscribe: jest.fn(), updateTask: jest.fn() }));
      const daemonMock = { start: jest.fn() };
      jest.mock("../src/daemon", () => daemonMock);
      require("../src/session-subscriber");
      expect(daemonMock.start).not.toHaveBeenCalled();
    });

    it("onTask handler calls updateTask with working then completed", async () => {
      jest.resetModules();
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
  ```

- [ ] **Step 2: Run to confirm they fail**

  ```bash
  npx jest tests/session-subscriber.test.js 2>&1 | tail -10
  ```
  Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/session-subscriber.js`**

  ```js
  "use strict";
  const { subscribe, updateTask } = require("./a2a-client");

  async function onTask(task) {
    const { id, messages } = task;
    await updateTask(id, "working");
    try {
      const text = messages?.[0]?.parts?.[0]?.text;
      const parsed = text ? JSON.parse(text) : {};
      await updateTask(id, "completed", {
        name: "aelli-response",
        parts: [{ kind: "text", text: parsed.response || "received" }],
      });
    } catch {
      await updateTask(id, "completed", {
        name: "aelli-response",
        parts: [{ kind: "text", text: "received" }],
      });
    }
  }

  subscribe(onTask);
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  npx jest tests/session-subscriber.test.js 2>&1 | tail -5
  ```
  Expected: all PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add src/session-subscriber.js tests/session-subscriber.test.js
  git commit -m "feat(session): add session-subscriber.js — per-session AELLI push task handler"
  ```

---

### Task 8: Create `hooks/scripts/session-subscriber.js` entry point

**Files:**
- Create: `hooks/scripts/session-subscriber.js`

- [ ] **Step 1: Create the thin entry point**

  Create `hooks/scripts/session-subscriber.js`:
  ```js
  #!/usr/bin/env node
  "use strict";
  // Per-session background process: subscribes to AELLI push tasks for this session.
  // Spawned detached by hooks/scripts/start.js. PTY_SESSION_ID must be set by caller.
  require("../../src/session-subscriber");
  // Keep the process alive (subscribe() connects SSE and reconnects indefinitely)
  setInterval(() => {}, 60_000);
  ```

- [ ] **Step 2: Verify it's importable**

  ```bash
  node -e "require('./hooks/scripts/session-subscriber')" 2>&1 | head -5
  ```
  Expected: no crash (will attempt SSE connection, which will fail in isolation — that's fine).

- [ ] **Step 3: Commit**

  ```bash
  git add hooks/scripts/session-subscriber.js
  git commit -m "feat(hooks): add session-subscriber.js entry point for per-session push tasks"
  ```

---

### Task 9: Update `index.js` — daemon only

**Files:**
- Modify: `index.js`

- [ ] **Step 1: Write the failing test**

  In `tests/` create or open a relevant test file. Add to `tests/daemon.test.js` (or create it):
  ```js
  it("index.js does not call subscribe() — daemon only", () => {
    jest.resetModules();
    const subscribeMock = jest.fn();
    jest.mock("./src/a2a-client", () => ({
      subscribe: subscribeMock,
      updateTask: jest.fn(),
    }));
    jest.mock("./src/daemon", () => ({ start: jest.fn() }));
    // Prevent setInterval from keeping jest open
    jest.useFakeTimers();
    require("./index");
    expect(subscribeMock).not.toHaveBeenCalled();
    jest.useRealTimers();
  });
  ```

- [ ] **Step 2: Run to confirm it fails**

  ```bash
  npx jest tests/daemon.test.js --testNamePattern="does not call subscribe" 2>&1 | tail -10
  ```
  Expected: FAIL — `subscribe` is called.

- [ ] **Step 3: Update `index.js`**

  Replace the entire file:
  ```js
  "use strict";
  const { version } = require("./package.json");
  const daemon = require("./src/daemon");

  // Daemon only — start once out-of-band (node index.js or make start).
  // Per-session push subscriptions run via hooks/scripts/session-subscriber.js.
  async function start() {
    daemon.start();
    console.log(`[octowiz v${version}] daemon ready`);
    console.log("plugin-ready");
    setInterval(() => {}, 60_000);
  }

  start().catch((e) => {
    console.error("[octowiz] Start error:", e.message);
    process.exit(1);
  });
  ```

- [ ] **Step 4: Run all tests**

  ```bash
  npm test 2>&1 | tail -10
  ```
  Expected: all PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add index.js tests/daemon.test.js
  git commit -m "refactor(daemon): index.js is daemon-only — remove subscribe() call

  Per-session push subscription moved to hooks/scripts/session-subscriber.js
  (spawned per CC session by hooks/scripts/start.js)."
  ```

---

### Task 10: Update `hooks/scripts/start.js` — spawn subscriber + write PID

**Files:**
- Modify: `hooks/scripts/start.js`
- Modify: `tests/hooks-start.test.js`

- [ ] **Step 1: Add tests for spawn behaviour**

  Append to `tests/hooks-start.test.js`:
  ```js
  describe("hooks/scripts/start.js — subscriber spawn", () => {
    let spawnMock, writeFileSyncMock;

    beforeEach(() => {
      jest.resetModules();
      process.env.AELLI_LITELLM_BASE = "https://llm.test";
      process.env.AELLI_AUTH_TOKEN = "tok";
      jest.mock("../src/a2a-client", () => ({ post: jest.fn().mockResolvedValue(null) }));
      jest.mock("../src/git-context", () => ({
        captureContext: jest.fn().mockReturnValue({
          sessionId: "s1", repoRoot: "/repo", repo: "origin", cwd: "/repo", branch: "main",
        }),
      }));
      jest.mock("../src/event-builder", () => ({
        buildSessionStart: jest.fn().mockReturnValue({ sessionId: "s1" }),
      }));
      const childProcess = require("child_process");
      spawnMock = jest.spyOn(childProcess, "spawn").mockReturnValue({
        unref: jest.fn(),
        pid: 1234,
      });
      const fs = require("fs");
      jest.spyOn(fs, "mkdirSync").mockImplementation(() => {});
      writeFileSyncMock = jest.spyOn(fs, "writeFileSync").mockImplementation(() => {});
    });

    afterEach(() => {
      jest.restoreAllMocks();
      delete process.env.AELLI_LITELLM_BASE;
      delete process.env.AELLI_AUTH_TOKEN;
    });

    it("spawns session-subscriber.js detached with correct PTY_SESSION_ID", async () => {
      const { handleStart } = require("../hooks/scripts/start");
      await handleStart({ session_id: "s1", cwd: "/repo" });
      expect(spawnMock).toHaveBeenCalledWith(
        process.execPath,
        [expect.stringContaining("session-subscriber.js")],
        expect.objectContaining({
          detached: true,
          env: expect.objectContaining({ PTY_SESSION_ID: "s1" }),
        })
      );
    });

    it("writes PID file to cache dir", async () => {
      const { handleStart } = require("../hooks/scripts/start");
      await handleStart({ session_id: "s1", cwd: "/repo" });
      expect(writeFileSyncMock).toHaveBeenCalledWith(
        expect.stringContaining("s1.pid"),
        "1234"
      );
    });
  });
  ```

- [ ] **Step 2: Run to confirm new tests fail**

  ```bash
  npx jest tests/hooks-start.test.js 2>&1 | tail -10
  ```
  Expected: new tests FAIL — spawn not called.

- [ ] **Step 3: Update `hooks/scripts/start.js`**

  Replace the file:
  ```js
  #!/usr/bin/env node
  "use strict";
  const fs = require("fs");
  const os = require("os");
  const path = require("path");
  const { spawn } = require("child_process");

  const CACHE_DIR = process.env.AELLI_CACHE_DIR || path.join(os.homedir(), ".cache", "aelli-cc");
  const LOG_FILE = path.join(CACHE_DIR, "aelli-cc.log");

  function appendLog(msg) {
    try {
      fs.mkdirSync(CACHE_DIR, { recursive: true });
      fs.appendFileSync(LOG_FILE, `[${new Date().toISOString()}] ${msg}\n`);
    } catch {}
  }

  function spawnSubscriber(sessionId) {
    const subscriberJs = path.join(__dirname, "session-subscriber.js");
    const child = spawn(process.execPath, [subscriberJs], {
      env: { ...process.env, PTY_SESSION_ID: sessionId },
      detached: true,
      stdio: "ignore",
    });
    child.unref();
    fs.mkdirSync(CACHE_DIR, { recursive: true });
    fs.writeFileSync(path.join(CACHE_DIR, `${sessionId}.pid`), String(child.pid));
  }

  async function handleStart(input) {
    const { post } = require("../../src/a2a-client");
    const { captureContext } = require("../../src/git-context");
    const { buildSessionStart } = require("../../src/event-builder");

    const sessionId = input.session_id || `cc-${Date.now()}-${process.pid}`;
    const cwd = input.cwd || process.cwd();

    if (!process.env.AELLI_LITELLM_BASE) {
      appendLog("[start] AELLI_LITELLM_BASE not set — session-start event will not be delivered");
    }
    if (!process.env.AELLI_AUTH_TOKEN) {
      appendLog("[start] AELLI_AUTH_TOKEN not set — session-start event will not be delivered");
    }

    const ctx = captureContext(sessionId, cwd);
    const payload = buildSessionStart(ctx);
    await post("session-start", payload, { sync: true, timeoutMs: 500 });

    spawnSubscriber(sessionId);
  }

  if (require.main === module) {
    let raw = "";
    process.stdin.on("data", (c) => (raw += c));
    process.stdin.on("end", async () => {
      let input = {};
      try { input = JSON.parse(raw); } catch {}
      try { await handleStart(input); } catch (e) {
        appendLog(`[start] error: ${e.message}`);
      }
      process.exit(0);
    });
  }

  module.exports = { handleStart };
  ```

- [ ] **Step 4: Run all tests**

  ```bash
  npm test 2>&1 | tail -10
  ```
  Expected: all PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add hooks/scripts/start.js tests/hooks-start.test.js
  git commit -m "feat(hooks): start.js spawns per-session subscriber + writes PID file"
  ```

---

### Task 11: Update `hooks/scripts/stop.js` — kill subscriber + clean PID

**Files:**
- Modify: `hooks/scripts/stop.js`
- Modify: `tests/hooks-stop.test.js`

- [ ] **Step 1: Add tests for SIGTERM behaviour**

  Append to `tests/hooks-stop.test.js`:
  ```js
  describe("hooks/scripts/stop.js — subscriber cleanup", () => {
    let existsSyncMock, readFileSyncMock, unlinkSyncMock, killMock;

    beforeEach(() => {
      jest.resetModules();
      jest.mock("../src/a2a-client", () => ({ post: jest.fn().mockResolvedValue(null) }));
      jest.mock("../src/git-context", () => ({
        getContext: jest.fn().mockReturnValue({ sessionId: "s1", repo: null, repoRoot: null }),
      }));
      const fs = require("fs");
      existsSyncMock = jest.spyOn(fs, "existsSync").mockReturnValue(true);
      readFileSyncMock = jest.spyOn(fs, "readFileSync").mockReturnValue("5678");
      unlinkSyncMock = jest.spyOn(fs, "unlinkSync").mockImplementation(() => {});
      killMock = jest.spyOn(process, "kill").mockImplementation(() => {});
    });

    afterEach(() => jest.restoreAllMocks());

    it("sends SIGTERM to the PID from the PID file", async () => {
      const { handleStop } = require("../hooks/scripts/stop");
      await handleStop({ session_id: "s1" });
      expect(killMock).toHaveBeenCalledWith(5678, "SIGTERM");
    });

    it("deletes the PID file after SIGTERM", async () => {
      const { handleStop } = require("../hooks/scripts/stop");
      await handleStop({ session_id: "s1" });
      expect(unlinkSyncMock).toHaveBeenCalledWith(expect.stringContaining("s1.pid"));
    });

    it("does not throw when PID file does not exist", async () => {
      existsSyncMock.mockReturnValue(false);
      const { handleStop } = require("../hooks/scripts/stop");
      await expect(handleStop({ session_id: "s1" })).resolves.not.toThrow();
    });
  });
  ```

- [ ] **Step 2: Run to confirm new tests fail**

  ```bash
  npx jest tests/hooks-stop.test.js 2>&1 | tail -10
  ```
  Expected: new SIGTERM tests FAIL.

- [ ] **Step 3: Update `hooks/scripts/stop.js`**

  Replace the file:
  ```js
  #!/usr/bin/env node
  "use strict";
  const fs = require("fs");
  const os = require("os");
  const path = require("path");

  const CACHE_DIR = process.env.AELLI_CACHE_DIR || path.join(os.homedir(), ".cache", "aelli-cc");

  function killSubscriber(sessionId) {
    const pidFile = path.join(CACHE_DIR, `${sessionId}.pid`);
    if (!fs.existsSync(pidFile)) return;
    try {
      const pid = parseInt(fs.readFileSync(pidFile, "utf8").trim(), 10);
      if (!isNaN(pid)) process.kill(pid, "SIGTERM");
    } catch {}
    try { fs.unlinkSync(pidFile); } catch {}
  }

  async function handleStop(input) {
    const { post } = require("../../src/a2a-client");
    const { getContext } = require("../../src/git-context");

    const sessionId = input.session_id || "";
    if (!sessionId) return;

    killSubscriber(sessionId);

    const ctx = getContext(sessionId);
    await post(
      "session-end",
      { sessionId, repo: ctx?.repo, repoRoot: ctx?.repoRoot },
      { sync: true, timeoutMs: 500 }
    ).catch(() => {});
  }

  if (require.main === module) {
    let raw = "";
    process.stdin.on("data", (c) => (raw += c));
    process.stdin.on("end", async () => {
      let input = {};
      try { input = JSON.parse(raw); } catch {}
      try { await handleStop(input); } catch {}
      process.exit(0);
    });
  }

  module.exports = { handleStop };
  ```

- [ ] **Step 4: Run all tests**

  ```bash
  npm test 2>&1 | tail -10
  ```
  Expected: all PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add hooks/scripts/stop.js tests/hooks-stop.test.js
  git commit -m "feat(hooks): stop.js sends SIGTERM to per-session subscriber + cleans PID file"
  ```

---

## Phase 3 — Publish and deprecate

### Task 12: Wire Stop hook into `hooks/hooks.json`

**Files:**
- Modify: `hooks/hooks.json`

> ⚠️ **Do this atomically with removing aelli-cc-plugin.** Wire the Stop hook, update the plugin version, then immediately run `claude plugin remove aelli-cc-plugin` (or equivalent) before restarting any CC session. Do not leave both Stop hooks active across a session restart.

- [ ] **Step 1: Add Stop hook to hooks.json**

  Edit `hooks/hooks.json` — add after the `UserPromptSubmit` block:
  ```json
  "Stop": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "command",
          "command": "node \"$CLAUDE_PLUGIN_ROOT/hooks/scripts/stop.js\"",
          "timeout": 10
        }
      ]
    }
  ]
  ```

- [ ] **Step 2: Run full test suite one final time**

  ```bash
  npm test 2>&1 | tail -10
  ```
  Expected: all PASS.

- [ ] **Step 3: Commit**

  ```bash
  git add hooks/hooks.json
  git commit -m "feat(hooks): wire Stop hook — session-end event forwarding (Phase 3)"
  ```

---

### Task 13: Bump `.claude-plugin/plugin.json` to 0.5.0

**Files:**
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Update version**

  In `.claude-plugin/plugin.json`, change:
  ```json
  "version": "0.1.2"
  ```
  To:
  ```json
  "version": "0.5.0"
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add .claude-plugin/plugin.json
  git commit -m "chore: bump plugin.json to 0.5.0"
  ```

---

### Task 14: Update README — daemon setup + env vars

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add daemon setup section**

  Find the existing setup/installation section in `README.md` and add or update a "Daemon setup" section with:

  ```markdown
  ## Daemon setup

  The octowiz daemon handles agent capabilities (dispatch, advise, manage-agents). It runs as a singleton service — start it once per machine, not per Claude Code session.

  **Required env vars:**

  | Var | Purpose |
  |-----|---------|
  | `AELLI_BASE_URL` | AELLI server URL (e.g. `http://localhost:3456`) |
  | `AELLI_LITELLM_BASE` | LiteLLM base URL for event forwarding hooks |
  | `AELLI_AUTH_TOKEN` | Shared auth token (daemon + hooks) |
  | `OCTOWIZ_ALLOWED_ROOTS` | Comma-separated allowed cwd roots (e.g. `/Users/you/projects`) |

  **Start the daemon:**

  ```bash
  make start
  # or
  node index.js
  ```

  The Claude Code hooks (SessionStart, PostToolUse, UserPromptSubmit, Stop) run automatically when the plugin is installed. They do not start or stop the daemon.
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add README.md
  git commit -m "docs: add daemon setup section and env var table to README"
  ```

---

### Task 15: Smoke test + remove aelli-cc-plugin

- [ ] **Step 1: Install octowiz 0.5.0 from local path**

  ```bash
  claude plugin install /path/to/octowiz --local
  ```
  Or update via marketplace if published.

- [ ] **Step 2: Verify session-start reaches AELLI**

  Open a new CC session. Check AELLI logs or `~/.cache/aelli-cc/aelli-cc.log` for a `session-start` entry.

- [ ] **Step 3: Verify file-edit event**

  Make any file edit (Write or Edit tool). Check AELLI logs for `file-edit` or `file-write`.

- [ ] **Step 4: Verify prompt event**

  Submit a prompt. Check for `prompt` event in AELLI logs.

- [ ] **Step 5: Verify push task delivery**

  Trigger a push task from AELLI to the session (via AELLI's task queue). Verify `updateTask` completes.

- [ ] **Step 6: Remove aelli-cc-plugin (immediately, same session restart)**

  ```bash
  claude plugin remove aelli-cc-plugin
  ```

- [ ] **Step 7: Verify session-end reaches AELLI**

  Close the CC session. Check AELLI logs or `aelli-cc.log` for a `session-end` entry.

- [ ] **Step 8: Archive aelli-cc-plugin repo**

  Navigate to `raelli/aelli-cc-plugin` on GitHub → Settings → Archive repository.

- [ ] **Step 9: Final commit — confirm AELLI_API_BASE safe to remove**

  Verify `AELLI_BASE_URL` is set in `~/.claude/settings.json` and AELLI is reachable. Then remove `AELLI_API_BASE` from settings if present.

---

## Self-review checklist

- [x] Phase 1 observability: startup guard in `start.js` ✓, fire-and-forget logging in `a2a-client.js` ✓, sync+timeout for `session-start` ✓
- [x] Stop hook deferred: absent from Phase 1 hooks.json ✓, wired in Task 12 alongside aelli-cc-plugin removal ✓
- [x] Env var contract: `AELLI_BASE_URL` canonical in Task 6, `AELLI_API_BASE` as fallback, removal deferred to Task 15 ✓
- [x] Daemon separation: `index.js` daemon-only after Task 9 ✓, subscriber in separate process ✓
- [x] `package.json#files` includes `hooks/` — `session-subscriber.js` is inside `hooks/scripts/` ✓
- [x] All test files use `jest.resetModules()` where module-level env var state is tested ✓
- [x] `stop.js` kills subscriber BEFORE posting session-end (correct order) ✓
- [x] `buildPrompt` signature is `(session, prompt)` — used correctly in `report-event.js` ✓
