const path = require("path");

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
  const resolved = path.resolve(cwd);
  const raw = process.env.OCTOWIZ_ALLOWED_ROOTS || "";
  const roots = raw.split(":").map((r) => r.trim()).filter(Boolean);
  const allowed = roots.some((root) => {
    const resolvedRoot = path.resolve(root);
    return resolved === resolvedRoot || resolved.startsWith(resolvedRoot + path.sep);
  });
  if (!allowed) {
    throw new Error(`cwd "${cwd}" is not within an allowed root (OCTOWIZ_ALLOWED_ROOTS=${raw})`);
  }
  return resolved;
}

module.exports = { checkStartup, validateCwd };
