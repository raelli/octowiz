const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const CACHE_DIR = process.env.AELLI_CACHE_DIR || path.join(os.homedir(), ".cache", "aelli-cc");

function run(args, cwd) {
  try {
    return execFileSync("git", args, {
      cwd,
      encoding: "utf8",
      timeout: 3000,
      stdio: ["pipe", "pipe", "pipe"],
    }).trim();
  } catch {
    return null;
  }
}

// Pure parser for `git status --porcelain` output.
// Exported so it can be unit-tested without touching the filesystem or git.
function parseGitStatus(output) {
  if (!output) return [];
  const trimmed = output.trimEnd(); // trimEnd only — leading spaces carry status codes
  if (!trimmed) return [];
  return [...new Set(
    trimmed.split("\n")
      .filter((l) => l && !l.startsWith("??"))
      .map((l) => {
        const part = l.slice(3).trim();
        // Rename lines: "R  old.js -> new.js" — keep destination only
        const arrowIdx = part.indexOf(" -> ");
        return arrowIdx >= 0 ? part.slice(arrowIdx + 4) : part;
      })
      .filter(Boolean)
  )];
}

function readBranch(repoRoot) {
  if (!repoRoot) return null;
  return run(["rev-parse", "--abbrev-ref", "HEAD"], repoRoot);
}

function readModifiedFiles(repoRoot) {
  if (!repoRoot) return [];
  try {
    const out = execFileSync("git", ["status", "--porcelain"], {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 3000,
      stdio: ["pipe", "pipe", "pipe"],
    });
    return parseGitStatus(out);
  } catch {
    return [];
  }
}

// Capture the stable git context for a session (repo root + remote) and write
// it to the cache. Call once at SessionStart.
function captureContext(sessionId, cwd) {
  const repoRoot = run(["rev-parse", "--show-toplevel"], cwd);
  const repo = repoRoot ? run(["remote", "get-url", "origin"], repoRoot) : null;
  const ctx = { sessionId, repoRoot, repo, cwd };
  fs.mkdirSync(CACHE_DIR, { recursive: true });
  const tmp = path.join(CACHE_DIR, `git-context-${sessionId}.json.tmp`);
  const dest = path.join(CACHE_DIR, `git-context-${sessionId}.json`);
  fs.writeFileSync(tmp, JSON.stringify(ctx));
  fs.renameSync(tmp, dest); // atomic on POSIX
  return ctx;
}

// Read the cached stable fields and augment with live branch + modified files.
// Safe to call on every hook event — git reads are fast and always current.
function getContext(sessionId) {
  let cached;
  try {
    cached = JSON.parse(
      fs.readFileSync(path.join(CACHE_DIR, `git-context-${sessionId}.json`), "utf8")
    );
  } catch {
    return null;
  }
  const { repoRoot } = cached;
  return {
    ...cached,
    branch: readBranch(repoRoot),
    modifiedFiles: readModifiedFiles(repoRoot),
  };
}

module.exports = { captureContext, getContext, parseGitStatus };
