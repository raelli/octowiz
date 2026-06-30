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
 * @property {string|null} branch        - Current git branch, or null when detached HEAD / unavailable.
 * @property {string[]}    modifiedFiles - Tracked files with staged or unstaged changes
 *                                         (untracked `??` files are intentionally excluded).
 *                                         For renames/copies, the destination path (new side) is reported.
 *                                         Order is normalized (sorted) for deterministic output.
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
    const out = execFileSync('git', args, {
      cwd,
      encoding: 'utf8',
      timeout: 3000,
      stdio: ['pipe', 'pipe', 'pipe'],
    })
    return typeof out === 'string' ? out.trim() : null
  }
  catch {
    return null
  }
}

// Strips characters that are unsafe in filenames to prevent path traversal.
function safeSessionId(sessionId) {
  return String(sessionId).replace(/[^A-Za-z0-9._-]/g, '_')
}

function contextPath(sessionId) {
  return path.join(cacheDir(), `git-context-${safeSessionId(sessionId)}.json`)
}

// Handles git's C-style quoted paths (e.g. paths with spaces or special chars).
function unquoteGitPath(p) {
  if (typeof p !== 'string')
    return ''

  const s = p.trim()
  if (s.length < 2 || s[0] !== '"' || s[s.length - 1] !== '"')
    return s

  let out = ''
  for (let i = 1; i < s.length - 1; i++) {
    const ch = s[i]
    if (ch !== '\\') {
      out += ch
      continue
    }

    i++
    if (i >= s.length - 1)
      break

    const esc = s[i]
    switch (esc) {
      case '"': out += '"'; break
      case '\\': out += '\\'; break
      case 'n': out += '\n'; break
      case 't': out += '\t'; break
      case 'r': out += '\r'; break
      case 'b': out += '\b'; break
      case 'f': out += '\f'; break
      case 'v': out += '\v'; break
      default: out += esc; break
    }
  }

  return out
}

// Split "old -> new" in a rename/copy rawPath while respecting quoted segments.
// Returns null when no unquoted delimiter is found.
function splitRenamePath(rawPath) {
  let inQuotes = false
  for (let i = 0; i <= rawPath.length - 4; i++) {
    const ch = rawPath[i]
    if (ch === '"') {
      // A quote is escaped only when preceded by an ODD run of backslashes;
      // an even run (e.g. "old\\") is an escaped backslash + a real quote.
      let backslashes = 0
      for (let j = i - 1; j >= 0 && rawPath[j] === '\\'; j--)
        backslashes++
      if (backslashes % 2 === 0)
        inQuotes = !inQuotes
    }
    if (!inQuotes && rawPath.slice(i, i + 4) === ' -> ')
      return [rawPath.slice(0, i), rawPath.slice(i + 4)]
  }
  return null
}

// Pure parser for `git status --porcelain=v1` output.
// Exported so it can be unit-tested without touching the filesystem or git.
function parseGitStatus(output) {
  if (!output)
    return []

  const lines = output.replace(/\r\n/g, '\n').trimEnd().split('\n')
  const files = []
  const seen = new Set()

  for (const line of lines) {
    if (!line || line.length < 3)
      continue

    const x = line[0]
    const y = line[1]

    if (x === '?' && y === '?')
      continue

    const rawPath = line.slice(3).trim()
    if (!rawPath)
      continue

    let candidate = rawPath
    if (x === 'R' || y === 'R' || x === 'C' || y === 'C') {
      const split = splitRenamePath(rawPath)
      if (split && split[1])
        candidate = split[1].trim()
    }

    const normalizedPath = unquoteGitPath(candidate)

    if (!normalizedPath || seen.has(normalizedPath))
      continue

    seen.add(normalizedPath)
    files.push(normalizedPath)
  }

  // Deterministic ordering for stable serialization and testing.
  files.sort((a, b) => a.localeCompare(b))
  return files
}

function readBranch(repoRoot) {
  if (!repoRoot)
    return null

  const branch = run(['rev-parse', '--abbrev-ref', 'HEAD'], repoRoot)
  // "HEAD" means detached HEAD state — return null for semantic clarity.
  if (!branch || branch === 'HEAD')
    return null
  return branch
}

function readModifiedFiles(repoRoot) {
  if (!repoRoot)
    return []
  return parseGitStatus(run(['status', '--porcelain=v1'], repoRoot))
}

function isValidStableContext(value) {
  return !!value
    && typeof value === 'object'
    && !Array.isArray(value)
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

  const dest = contextPath(stableSessionId)
  const tmp = `${dest}.${process.pid}.${Date.now()}.tmp`

  try {
    fs.mkdirSync(path.dirname(dest), { recursive: true })
    fs.writeFileSync(tmp, JSON.stringify(ctx))
    fs.renameSync(tmp, dest)
  }
  catch {
    try {
      if (fs.existsSync(tmp))
        fs.unlinkSync(tmp)
    }
    catch {
      // ignore cleanup errors
    }
  }

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
  if (!cached || !cached.repoRoot)
    return null

  const { repoRoot } = cached
  return {
    branch: readBranch(repoRoot) ?? null,
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

  if (!stable.repoRoot) {
    return {
      ...stable,
      branch: null,
      modifiedFiles: [],
    }
  }

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
