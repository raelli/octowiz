/**
 * Git-context read model
 * ======================
 *
 * Two shapes are produced by this module:
 *
 * @typedef {object} SessionContext
 * @property {string}      sessionId  - Claude Code session identifier.
 * @property {string|null} repoRoot   - Absolute path to the git repo root (stable).
 * @property {string|null} repo       - Remote origin URL, e.g. "git@github.com:org/repo.git" (stable).
 * @property {string}      cwd        - Working directory at session start (stable).
 *
 * SessionContext fields are **stable**: they are captured exactly once at SessionStart,
 * written to a JSON cache, and do not change for the lifetime of the session.
 * Returned by: captureContext() (writes), getStableContext() (reads).
 *
 * @typedef {object} LiveContext
 * @property {string|null} branch        - Current git branch (changes during a session).
 * @property {string[]}    modifiedFiles - Files with staged or unstaged changes (changes often).
 *
 * LiveContext fields are **live**: they are read fresh from git on every call and
 * reflect the current working-tree state.
 * Returned by: getLiveContext().
 *
 * getContext(sessionId) merges both shapes into a single object (SessionContext & LiveContext).
 * Use it when you need all fields in one call (e.g. building a prompt event).
 * Use getStableContext() when you only need repo metadata (e.g. session-end notification)
 * to avoid unnecessary git subprocess calls.
 *
 * Note: apps/claude_code_bridge/bridge.py reads live context independently using its own
 * subprocess calls (_git_context / _git_modified_files). If the two read paths should be
 * unified, file a follow-up issue to replace bridge.py's git calls with an IPC/cache read.
 */

const { execFileSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')
const { cacheDir } = require('./config')

function run(args, cwd) {
  try {
    return execFileSync('git', args, {
      cwd,
      encoding: 'utf8',
      timeout: 3000,
      stdio: ['pipe', 'pipe', 'pipe'],
    }).trim()
  }
  catch {
    return null
  }
}

// Pure parser for `git status --porcelain` output.
// Exported so it can be unit-tested without touching the filesystem or git.
function parseGitStatus(output) {
  if (!output)
    return []
  const trimmed = output.trimEnd() // trimEnd only — leading spaces carry status codes
  if (!trimmed)
    return []
  return [...new Set(
    trimmed.split('\n')
      .filter(l => l && !l.startsWith('??'))
      .map((l) => {
        const part = l.slice(3).trim()
        // Rename lines: "R  old.js -> new.js" — keep destination only
        const arrowIdx = part.indexOf(' -> ')
        return arrowIdx >= 0 ? part.slice(arrowIdx + 4) : part
      })
      .filter(Boolean),
  )]
}

function readBranch(repoRoot) {
  if (!repoRoot)
    return null
  return run(['rev-parse', '--abbrev-ref', 'HEAD'], repoRoot)
}

function readModifiedFiles(repoRoot) {
  if (!repoRoot)
    return []
  try {
    const out = execFileSync('git', ['status', '--porcelain'], {
      cwd: repoRoot,
      encoding: 'utf8',
      timeout: 3000,
      stdio: ['pipe', 'pipe', 'pipe'],
    })
    return parseGitStatus(out)
  }
  catch {
    return []
  }
}

// Capture the stable git context for a session (repo root + remote) and write
// it to the cache. Call once at SessionStart.
function captureContext(sessionId, cwd) {
  const repoRoot = run(['rev-parse', '--show-toplevel'], cwd)
  const repo = repoRoot ? run(['remote', 'get-url', 'origin'], repoRoot) : null
  const ctx = { sessionId, repoRoot, repo, cwd }
  const dir = cacheDir()
  fs.mkdirSync(dir, { recursive: true })
  const tmp = path.join(dir, `git-context-${sessionId}.json.tmp`)
  const dest = path.join(dir, `git-context-${sessionId}.json`)
  fs.writeFileSync(tmp, JSON.stringify(ctx))
  fs.renameSync(tmp, dest) // atomic on POSIX
  return ctx
}

// Read the cached SessionContext (stable fields only). No git subprocess is run.
// Use when you only need repo metadata and want to avoid live git reads.
function getStableContext(sessionId) {
  try {
    return JSON.parse(
      fs.readFileSync(path.join(cacheDir(), `git-context-${sessionId}.json`), 'utf8'),
    )
  }
  catch {
    return null
  }
}

// Read the live git state (branch + modified files) for a session.
// Always runs git subprocesses — reflects the current working-tree state.
// Requires that captureContext() was called first so the repoRoot is cached.
function getLiveContext(sessionId) {
  const cached = getStableContext(sessionId)
  if (!cached)
    return null
  const { repoRoot } = cached
  return {
    branch: readBranch(repoRoot),
    modifiedFiles: readModifiedFiles(repoRoot),
  }
}

// Merge SessionContext and LiveContext into one object.
// Convenience wrapper — safe to call on every hook event.
// Prefer getStableContext() when only stable fields are needed.
function getContext(sessionId) {
  const cached = getStableContext(sessionId)
  if (!cached)
    return null
  return { ...cached, ...getLiveContext(sessionId) }
}

module.exports = { captureContext, getStableContext, getLiveContext, getContext, parseGitStatus }
