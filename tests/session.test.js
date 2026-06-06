"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

// Use a real temp dir so tests exercise actual filesystem paths.
function makeTmpDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "octowiz-session-test-"));
}

function loadSession(cacheDir) {
  jest.resetModules();
  process.env.AELLI_CACHE_DIR = cacheDir;
  return require("../src/session");
}

afterEach(() => {
  jest.resetModules();
  delete process.env.AELLI_CACHE_DIR;
});

// ── stop() ────────────────────────────────────────────────────────────────

describe("stop()", () => {
  it("is a no-op when no PID file exists", () => {
    const dir = makeTmpDir();
    const { stop } = loadSession(dir);
    expect(() => stop("sess-missing")).not.toThrow();
  });

  it("sends SIGTERM and removes PID file when valid PID exists", () => {
    const dir = makeTmpDir();
    const { stop } = loadSession(dir);

    const pidFile = path.join(dir, "aelli-cc.sess-1.pid");
    fs.writeFileSync(pidFile, String(process.pid)); // use own PID — SIGTERM to self succeeds

    const killSpy = jest.spyOn(process, "kill").mockImplementation(() => {});
    stop("sess-1");

    expect(killSpy).toHaveBeenCalledWith(process.pid, "SIGTERM");
    expect(fs.existsSync(pidFile)).toBe(false);
    killSpy.mockRestore();
  });

  it("removes PID file even when process is already dead (ESRCH)", () => {
    const dir = makeTmpDir();
    const { stop } = loadSession(dir);

    const pidFile = path.join(dir, "aelli-cc.sess-2.pid");
    fs.writeFileSync(pidFile, "99999999"); // very unlikely to be a real process

    // process.kill throws ESRCH for dead processes — stop() must swallow it
    expect(() => stop("sess-2")).not.toThrow();
    expect(fs.existsSync(pidFile)).toBe(false);
  });

  it("removes the git-context cache file", () => {
    const dir = makeTmpDir();
    const { stop } = loadSession(dir);

    const ctxFile = path.join(dir, "git-context-sess-3.json");
    fs.writeFileSync(ctxFile, "{}");

    const killSpy = jest.spyOn(process, "kill").mockImplementation(() => {});
    stop("sess-3");
    killSpy.mockRestore();

    expect(fs.existsSync(ctxFile)).toBe(false);
  });

  it("is safe to call twice for the same session", () => {
    const dir = makeTmpDir();
    const { stop } = loadSession(dir);

    const killSpy = jest.spyOn(process, "kill").mockImplementation(() => {});
    expect(() => { stop("sess-4"); stop("sess-4"); }).not.toThrow();
    killSpy.mockRestore();
  });
});

// ── get() ─────────────────────────────────────────────────────────────────

describe("get()", () => {
  it("returns null for an unknown session", () => {
    const dir = makeTmpDir();
    const { get } = loadSession(dir);
    const result = get("unknown-session-xyz");
    // getContext returns null when no context file exists
    expect(result).toBeNull();
  });
});
