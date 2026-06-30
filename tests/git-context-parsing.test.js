// Tests for parseGitStatus — a pure function, no mocking needed.
const os = require('node:os')

process.env.AELLI_CACHE_DIR = os.tmpdir()

const { parseGitStatus } = require('../src/git-context')

describe('parseGitStatus', () => {
  it('extracts destination filename from rename lines', () => {
    expect(parseGitStatus('R  src/old.js -> src/new.js')).toEqual(['src/new.js'])
  })

  it('splits a rename whose old side ends in a literal backslash', () => {
    // git quotes "old\" as "old\\" — the closing quote follows an even (2) run
    // of backslashes, so it must still terminate the quoted segment.
    expect(parseGitStatus('R  "old\\\\" -> new')).toEqual(['new'])
  })

  it('excludes untracked files (lines starting with ??)', () => {
    expect(parseGitStatus('?? untracked.js\n M tracked.js')).toEqual(['tracked.js'])
  })

  it('deduplicates entries', () => {
    expect(parseGitStatus(' M foo.js\n M foo.js')).toEqual(['foo.js'])
  })

  it('returns empty array on empty string', () => {
    expect(parseGitStatus('')).toEqual([])
  })

  it('returns empty array on null / undefined', () => {
    expect(parseGitStatus(null)).toEqual([])
    expect(parseGitStatus(undefined)).toEqual([])
  })

  it('handles a mix of modified, added, and deleted statuses', () => {
    const out = ' M src/a.js\nA  src/b.js\nD  src/c.js\n?? ignored.js'
    expect(parseGitStatus(out)).toEqual(['src/a.js', 'src/b.js', 'src/c.js'])
  })
})
