const os = require("os");
const fs = require("fs");
const path = require("path");

const CACHE_DIR = path.join(os.tmpdir(), `aelli-cc-test-${process.pid}`);
process.env.AELLI_CACHE_DIR = CACHE_DIR;

const { captureContext, getContext } = require("../src/git-context");

afterAll(() => {
  fs.rmSync(CACHE_DIR, { recursive: true, force: true });
});

describe("captureContext / getContext", () => {
  it("captures context and reads it back with live git state", () => {
    const ctx = captureContext("sess-001", process.cwd());
    expect(ctx).toMatchObject({ sessionId: "sess-001", cwd: process.cwd() });
    expect(typeof ctx.repoRoot).toBe("string");

    const loaded = getContext("sess-001");
    expect(loaded).toMatchObject({ sessionId: "sess-001", cwd: process.cwd() });
    expect(typeof loaded.branch).toBe("string");
    expect(Array.isArray(loaded.modifiedFiles)).toBe(true);
  });

  it("different sessionIds get separate cache files", () => {
    captureContext("sess-A", process.cwd());
    captureContext("sess-B", process.cwd());
    expect(getContext("sess-A").sessionId).toBe("sess-A");
    expect(getContext("sess-B").sessionId).toBe("sess-B");
  });

  it("returns null repoRoot for a non-git directory", () => {
    const ctx = captureContext("sess-nogit", os.tmpdir());
    expect(ctx.repoRoot).toBeNull();
    expect(ctx.repo).toBeNull();
  });

  it("getContext returns null when cache file does not exist", () => {
    expect(getContext("nonexistent-session")).toBeNull();
  });

  it("getContext returns null branch and empty modifiedFiles for non-git repoRoot", () => {
    captureContext("sess-nogit2", os.tmpdir());
    const loaded = getContext("sess-nogit2");
    expect(loaded.branch).toBeNull();
    expect(loaded.modifiedFiles).toEqual([]);
  });

  it("writes cache atomically (tmp + rename — no partial read window)", () => {
    captureContext("sess-atomic", process.cwd());
    const cacheFile = path.join(CACHE_DIR, "git-context-sess-atomic.json");
    const tmpFile = path.join(CACHE_DIR, "git-context-sess-atomic.json.tmp");
    expect(fs.existsSync(cacheFile)).toBe(true);
    expect(fs.existsSync(tmpFile)).toBe(false);
  });
});
