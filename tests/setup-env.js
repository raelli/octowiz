// Jest setupFiles — runs before every test file, in every worker.
//
// Redirect the plugin's cache directory (and with it config.logFile()) to a
// per-process temp dir so test runs never append to the user's real
// ~/.cache/aelli-cc/aelli-cc.log. src/config.js reads env at call time, so
// this override reaches every module without resetModules juggling.
// Individual tests that set or delete AELLI_CACHE_DIR themselves still work —
// they only ever compute paths and never write to the resolved default.
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

// setupFiles run once per test FILE; reuse one dir per worker process so a
// full run creates a handful of temp dirs, not one per suite. A test that
// deletes AELLI_CACHE_DIR mid-file gets a fresh dir before the next file.
if (!(process.env.AELLI_CACHE_DIR || '').includes('octowiz-test-cache-')) {
  process.env.AELLI_CACHE_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'octowiz-test-cache-'))
}
