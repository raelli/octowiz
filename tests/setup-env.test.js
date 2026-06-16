const os = require('node:os')
const path = require('node:path')

// Guards the setupFiles contract: every jest worker must start with the cache
// dir pointed at a temp location, so nothing a test triggers (appendLog,
// git-context writes, pid files) can land in the user's real ~/.cache/aelli-cc.
describe('test environment', () => {
  it('redirects AELLI_CACHE_DIR away from the real cache', () => {
    const dir = process.env.AELLI_CACHE_DIR
    expect(dir).toBeDefined()
    expect(dir).toContain('octowiz-test-cache-')
    expect(dir.startsWith(path.join(os.homedir(), '.cache'))).toBe(false)
  })
})
