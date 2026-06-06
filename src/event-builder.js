function buildSessionStart(session) {
  return {
    sessionId: session.sessionId,
    branch: session.branch,
    repo: session.repo,
    repoRoot: session.repoRoot,
    cwd: session.cwd,
  };
}

module.exports = { buildSessionStart };
