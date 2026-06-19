// CANONICAL ENFORCEMENT POINT — OCTOWIZ_ALLOWED_ROOTS
//
// This file is the authoritative validator for cwd against OCTOWIZ_ALLOWED_ROOTS.
// All cwd validation MUST pass validateCwd() here before a task is forwarded to
// any downstream process (A2A agent, Python capability, etc.).
//
// daemon.js calls validateCwd() immediately on receipt of every task payload so
// that bad paths are rejected inside the trusted Node.js process before they can
// reach Python or any shell command.
//
// apps/a2a-agent/path_guard.py contains a secondary defence-in-depth check.
// Those two validators MUST stay in sync.  If the logic here changes (separator
// handling, realpath resolution, allowlist semantics), update path_guard.py as well.
//
// path_guard.py (Python side) is kept in sync:
//   - Roots resolved via os.path.realpath() before comparison (matches realpathSync here).
//   - Empty/unset OCTOWIZ_ALLOWED_ROOTS raises ValueError (deny-all, matches checkStartup).

const fs = require('node:fs')
const path = require('node:path')
const logger = require('./logger')

function parseRoots() {
  const raw = process.env.OCTOWIZ_ALLOWED_ROOTS || ''
  return { raw, roots: raw.split(':').map(r => r.trim()).filter(Boolean) }
}

function checkStartup() {
  const { roots } = parseRoots()
  if (roots.length === 0) {
    logger.error(
      '[policy] Fatal: OCTOWIZ_ALLOWED_ROOTS is not set or empty.\n'
      + '  Set it to a colon-separated list of absolute paths the daemon is allowed to operate in.\n'
      + '  Example: export OCTOWIZ_ALLOWED_ROOTS=/Users/me/Documents/myproject',
    )
    process.exit(1)
  }
}

function validateCwd(cwd) {
  if (!cwd || typeof cwd !== 'string')
    throw new Error('cwd is required')
  let resolved
  try {
    resolved = fs.realpathSync(cwd)
  }
  catch {
    throw new Error(`cwd "${cwd}" does not exist`)
  }
  const { raw, roots } = parseRoots()
  if (roots.length === 0)
    throw new Error('OCTOWIZ_ALLOWED_ROOTS is not set or empty — no paths are allowed')
  const allowed = roots.some((root) => {
    let resolvedRoot
    try {
      resolvedRoot = fs.realpathSync(root)
    }
    catch (err) {
      logger.warn(`[policy] Root "${root}" could not be resolved and will be ignored. (${err.message || 'unknown error'})`)
      return false
    }
    return resolved === resolvedRoot || resolved.startsWith(resolvedRoot + path.sep)
  })
  if (!allowed) {
    throw new Error(`cwd "${cwd}" is not within an allowed root (OCTOWIZ_ALLOWED_ROOTS=${raw})`)
  }
  return resolved
}

module.exports = { checkStartup, validateCwd }
