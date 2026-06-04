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
// Known divergences vs. path_guard.py (2026-06-04):
//   1. Symlink resolution: path_guard.py does NOT call os.path.realpath() on the
//      individual roots, only on cwd. Symlinked roots work here but bypass Python.
//   2. Empty-allowlist semantics (security-relevant): an empty / unset
//      OCTOWIZ_ALLOWED_ROOTS causes checkStartup() to exit the process (deny-all).
//      path_guard.py treats the same condition as allow-all. If Python is ever
//      invoked standalone without the Node daemon having validated ALLOWED_ROOTS,
//      an unset env var will permit all paths.
// Both divergences are tracked for reconciliation.

const path = require("path");
const fs = require("fs");

function checkStartup() {
  const raw = process.env.OCTOWIZ_ALLOWED_ROOTS || "";
  const roots = raw.split(":").map((r) => r.trim()).filter(Boolean);
  if (roots.length === 0) {
    console.error(
      "[policy] Fatal: OCTOWIZ_ALLOWED_ROOTS is not set or empty.\n" +
      "  Set it to a colon-separated list of absolute paths the daemon is allowed to operate in.\n" +
      "  Example: export OCTOWIZ_ALLOWED_ROOTS=/Users/me/Documents/myproject"
    );
    process.exit(1);
  }
}

function validateCwd(cwd) {
  if (!cwd || typeof cwd !== "string") throw new Error("cwd is required");
  let resolved;
  try {
    resolved = fs.realpathSync(cwd);
  } catch {
    throw new Error(`cwd "${cwd}" does not exist`);
  }
  const raw = process.env.OCTOWIZ_ALLOWED_ROOTS || "";
  const roots = raw.split(":").map((r) => r.trim()).filter(Boolean);
  const allowed = roots.some((root) => {
    let resolvedRoot;
    try {
      resolvedRoot = fs.realpathSync(root);
    } catch {
      return false;
    }
    return resolved === resolvedRoot || resolved.startsWith(resolvedRoot + path.sep);
  });
  if (!allowed) {
    throw new Error(`cwd "${cwd}" is not within an allowed root (OCTOWIZ_ALLOWED_ROOTS=${raw})`);
  }
  return resolved;
}

module.exports = { checkStartup, validateCwd };
