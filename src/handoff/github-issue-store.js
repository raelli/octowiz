// Sole handoff store. Re-introduce a factory (store.js) when a second adapter
// (e.g. MemPalace) ships with a real implementation.
const { execFileSync } = require('node:child_process')

function defaultRunner(args) {
  return execFileSync('gh', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
}

class GitHubIssueStore {
  constructor(runner) { this._run = runner || defaultRunner }

  async store(type, content, metadata = {}) {
    const label = type === 'summary' ? 'aelli-summary' : 'aelli-handoff'
    const title = metadata.title || `aelli ${type} — ${new Date().toISOString().slice(0, 10)}`
    const args = ['issue', 'create', '--label', label, '--title', title, '--body', content]
    if (metadata.repo)
      args.push('--repo', metadata.repo)
    const out = this._run(args)
    return out.trim()
  }

  async fetch(ref) {
    // ref is a GitHub issue URL: https://github.com/owner/repo/issues/123
    const match = ref.match(/github\.com\/([^/]+\/[^/]+)\/issues\/(\d+)/)
    if (!match)
      throw new Error(`Cannot parse GitHub issue URL: ${ref}`)
    const [, repo, number] = match
    return this._run(['issue', 'view', number, '--repo', repo, '--json', 'body', '--jq', '.body'])
  }
}

module.exports = { GitHubIssueStore }
