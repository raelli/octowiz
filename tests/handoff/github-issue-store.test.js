const { GitHubIssueStore } = require('../../src/handoff/github-issue-store')

describe('gitHubIssueStore', () => {
  it('calls gh issue create with correct label and returns URL', async () => {
    const calls = []
    const store = new GitHubIssueStore((args) => {
      calls.push(args)
      return 'https://github.com/raelli/octowiz/issues/123\n'
    })
    const ref = await store.store('handoff', '## Context\nStuff here', { repo: 'raelli/octowiz' })
    expect(ref).toBe('https://github.com/raelli/octowiz/issues/123')
    expect(calls[0]).toContain('issue')
    expect(calls[0]).toContain('create')
    expect(calls[0]).toContain('--label')
    expect(calls[0]).toContain('aelli-handoff')
  })

  it('uses aelli-summary label for summary type', async () => {
    const calls = []
    const store = new GitHubIssueStore((args) => { calls.push(args); return 'https://github.com/r/r/issues/1\n' })
    await store.store('summary', 'content', {})
    expect(calls[0]).toContain('aelli-summary')
  })

  it('fetch retrieves issue body via gh issue view', async () => {
    const store = new GitHubIssueStore((args) => {
      if (args.includes('view'))
        return '# Handoff content\nHello'
      return 'https://github.com/r/r/issues/1\n'
    })
    const content = await store.fetch('https://github.com/raelli/octowiz/issues/123')
    expect(content).toContain('Handoff content')
  })

  it('throws when gh runner throws', async () => {
    const store = new GitHubIssueStore(() => { throw new Error('gh not found') })
    await expect(store.store('handoff', 'content', {})).rejects.toThrow('gh not found')
  })
})
