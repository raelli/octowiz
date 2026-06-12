// Jest setupFiles — runs before every test file, in every worker.
//
// Redirect the plugin's cache directory (and with it config.logFile()) to a
// per-process temp dir so test runs never append to the user's real
// ~/.cache/aelli-cc/aelli-cc.log. src/config.js reads env at call time, so
// this override reaches every module without resetModules juggling.
// Individual tests that set or delete AELLI_CACHE_DIR themselves still work —
// they only ever compute paths and never write to the resolved default.
const fs = require("fs");
const os = require("os");
const path = require("path");

process.env.AELLI_CACHE_DIR = fs.mkdtempSync(path.join(os.tmpdir(), "octowiz-test-cache-"));
