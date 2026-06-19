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

function contextPath(sessionId) {
  return path.join(cacheDir(), `git-context-${String(sessionId)}.json`)
}

// Pure parser for `git status --porcelain` output.
// Exported so it can be unit-tested without touching the filesystem or git.
function parseGitStatus(output) {
  if (!output)
    return []

  const lines = output.replace(/\r\n/g, '\n').trimEnd().split('\n')
  const files = []
  const seen = new Set()

  for (const line of lines) {
    if (!line)
      continue
    if (line.startsWith('??'))
      continue

    const rawPath = line.length >= 4 ? line.slice(3).trim() : ''
    if (!rawPath)
      continue

    const delim = ' -> '
    const idx = rawPath.indexOf(delim)
    const normalizedPath = idx >= 0 ? rawPath.slice(idx + delim.length) : rawPath
    if (!normalizedPath || seen.has(normalizedPath))
      continue

    seen.add(normalizedPath)
    files.push(normalizedPath)
  }

  return files
}

function readBranch(repoRoot) {
  if (!repoRoot)
    return null
  return run(['rev-parse', '--abbrev-ref', 'HEAD'], repoRoot)
}

function readModifiedFiles(repoRoot) {
  if (!repoRoot)
    return []
  return parseGitStatus(run(['status', '--porcelain'], repoRoot))
}

function isValidStableContext(value) {
  return !!value
    && typeof value === 'object'
    && typeof value.sessionId === 'string'
    && (value.repoRoot === null || typeof value.repoRoot === 'string')
    && (value.repo === null || typeof value.repo === 'string')
    && typeof value.cwd === 'string'
}

// Capture the stable git context for a session (repo root + remote) and write
// it to the cache. Call once at SessionStart.
function captureContext(sessionId, cwd) {
  const stableSessionId = String(sessionId)
  const stableCwd = String(cwd)
  const repoRoot = run(['rev-parse', '--show-toplevel'], stableCwd)
  const repo = repoRoot ? (run(['remote', 'get-url', 'origin'], repoRoot) || null) : null

  const ctx = {
    sessionId: stableSessionId,
    repoRoot,
    repo,
    cwd: stableCwd,
  }

  const dir = cacheDir()
  fs.mkdirSync(dir, { recursive: true })

  const dest = contextPath(stableSessionId)
  const tmp = `${dest}.tmp`

  fs.writeFileSync(tmp, JSON.stringify(ctx))
  fs.renameSync(tmp, dest)

  return ctx
}

// Read the cached SessionContext (stable fields only). No git subprocess is run.
// Use when you only need repo metadata and want to avoid live git reads.
function getStableContext(sessionId) {
  try {
    const parsed = JSON.parse(fs.readFileSync(contextPath(sessionId), 'utf8'))
    return isValidStableContext(parsed) ? parsed : null
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
  const stable = getStableContext(sessionId)
  if (!stable)
    return null

  const { repoRoot } = stable
  return {
    ...stable,
    branch: readBranch(repoRoot) ?? null,
    modifiedFiles: readModifiedFiles(repoRoot),
  }
}

module.exports = {
  captureContext,
  getStableContext,
  getLiveContext,
  getContext,
  parseGitStatus,
}
