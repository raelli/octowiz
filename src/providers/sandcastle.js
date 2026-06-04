const path = require("path");

// Lazy-load sandcastle so tests that don't need Docker don't trigger it
let _sandcastle = null;
function getSandcastle() {
  if (!_sandcastle) {
    try {
      _sandcastle = require("@ai-hero/sandcastle");
    } catch {
      throw new Error("@ai-hero/sandcastle not installed — run pnpm install");
    }
  }
  return _sandcastle;
}

function defaultRun({ task, cwd, branch }) {
  const { run } = getSandcastle();
  return run({ task, cwd, branch: branch || "aelli-sandcastle" });
}

class SandcastleProvider {
  constructor(runFn) {
    this._run = runFn || defaultRun;
  }

  async run({ task, cwd, branch }) {
    if (!task) throw new Error("task is required");
    if (!cwd) throw new Error("cwd is required");
    return this._run({ task, cwd: path.resolve(cwd), branch });
  }
}

module.exports = { SandcastleProvider };
