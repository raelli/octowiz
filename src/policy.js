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
