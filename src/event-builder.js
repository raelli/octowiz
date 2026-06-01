const path = require("path");

const ALLOWED_ARTIFACT_TYPES = ["file-conflict", "branch-drift", "spec-deviation"];

function buildSessionStart(session) {
  return {
    sessionId: session.sessionId,
    branch: session.branch,
    repo: session.repo,
    repoRoot: session.repoRoot,
    cwd: session.cwd,
  };
}

function buildFileEvent(session, toolName, filePath) {
  const type = toolName === "Write" ? "file-write" : "file-edit";
  const repoRoot = session?.repoRoot || null;
  const relFile =
    repoRoot && filePath ? path.relative(repoRoot, filePath) : filePath;
  return {
    type,
    sessionId: session?.sessionId,
    file: relFile,
    repo: session?.repo,
    repoRoot,
  };
}

function buildPrompt(session, prompt) {
  return {
    sessionId: session?.sessionId,
    branch: session?.branch,
    repo: session?.repo,
    repoRoot: session?.repoRoot,
    prompt_summary: (prompt || "").slice(0, 1000),
    live_modified_files: session?.modifiedFiles ?? [],
  };
}

// Whitelist-validate a dev-advisor artifact before acting on it.
function parseArtifact(artifact) {
  if (!artifact) return null;
  if (!ALLOWED_ARTIFACT_TYPES.includes(artifact.type)) return null;
  if (typeof artifact.message !== "string") return null;
  return artifact;
}

module.exports = { buildSessionStart, buildFileEvent, buildPrompt, parseArtifact };
