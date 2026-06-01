const { GitHubIssueStore } = require("./github-issue-store");

function createHandoffStore() {
  const backend = process.env.HANDOFF_STORE || "github";
  if (backend === "mempalace") {
    const { MemPalaceStore } = require("./mempalace-store");
    return new MemPalaceStore();
  }
  return new GitHubIssueStore();
}

module.exports = { createHandoffStore };
