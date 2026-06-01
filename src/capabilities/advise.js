const BRANCH_DRIFT_THRESHOLD = 20;

// ─── SessionStore ────────────────────────────────────────────────────────────

class Session {
  constructor(sessionId, branch = "") {
    this.sessionId = sessionId;
    this.branch = branch;
    this.events = [];
  }
}

class ConflictIndex {
  constructor() {
    this._idx = {}; // repoRoot → file → Set<sessionId>
    this._branches = {}; // sessionId → branch
  }
  track(sessionId, branch, repoRoot, files) {
    this._branches[sessionId] = branch;
    this.untrack(sessionId, repoRoot);
    if (!files.length) return;
    if (!this._idx[repoRoot]) this._idx[repoRoot] = {};
    for (const f of files) {
      if (!f) continue;
      if (!this._idx[repoRoot][f]) this._idx[repoRoot][f] = new Set();
      this._idx[repoRoot][f].add(sessionId);
    }
  }
  untrack(sessionId, repoRoot) {
    if (!this._idx[repoRoot]) return;
    const toDelete = [];
    for (const [file, set] of Object.entries(this._idx[repoRoot])) {
      set.delete(sessionId);
      if (set.size === 0) toDelete.push(file);
    }
    for (const file of toDelete) delete this._idx[repoRoot][file];
  }
  /** Remove all traces of a session from the index (called on session-end). */
  dropSession(sessionId) {
    delete this._branches[sessionId];
    for (const repoFiles of Object.values(this._idx)) {
      const toDelete = [];
      for (const [file, set] of Object.entries(repoFiles)) {
        set.delete(sessionId);
        if (set.size === 0) toDelete.push(file);
      }
      for (const file of toDelete) delete repoFiles[file];
    }
  }
  findConflicts(repoRoot, files, ownSessionId) {
    const result = [];
    const idx = this._idx[repoRoot] || {};
    for (const f of files) {
      for (const sid of idx[f] || []) {
        if (sid !== ownSessionId) {
          result.push({ file: f, otherSessionId: sid, otherBranch: this._branches[sid] || "" });
        }
      }
    }
    return result;
  }
}

class SessionStore {
  /**
   * @param {ConflictIndex|null} conflicts - Shared ConflictIndex. If null, a
   *   private one is created (standalone usage or tests).
   */
  constructor(conflicts = null) {
    this._sessions = {};
    this._conflicts = conflicts !== null ? conflicts : new ConflictIndex();
  }
  getSession(sessionId) { return sessionId ? this._sessions[sessionId] : null; }
  recordEvent(event) {
    const sid = event.sessionId;
    if (!sid) return;
    if (!this._sessions[sid]) this._sessions[sid] = new Session(sid, event.branch || "");
    const s = this._sessions[sid];
    if (event.branch) s.branch = event.branch;
    s.events.push(event);
    const files = event.live_modified_files || [];
    const repo = event.repoRoot || "";
    if (repo) this._conflicts.track(sid, s.branch, repo, files);
  }
  findConflicts(repoRoot, files, sessionId) {
    return this._conflicts.findConflicts(repoRoot, files, sessionId);
  }
}

// ─── StoreRegistry ───────────────────────────────────────────────────────────

/**
 * Registry of per-session SessionStore instances sharing one ConflictIndex.
 *
 * The ConflictIndex must be shared so that cross-session file-conflict
 * detection works. Per-session event lists (BranchDrift, SpecDeviation)
 * are isolated inside each session's SessionStore.
 */
class StoreRegistry {
  constructor() {
    this._stores = {};
    this._conflicts = new ConflictIndex(); // shared across all sessions
  }

  /** Return the store for sessionId, creating one if needed. */
  get(sessionId) {
    if (!this._stores[sessionId]) {
      this._stores[sessionId] = new SessionStore(this._conflicts);
    }
    return this._stores[sessionId];
  }

  /** Remove the store for sessionId and purge it from the shared ConflictIndex. */
  drop(sessionId) {
    delete this._stores[sessionId];
    this._conflicts.dropSession(sessionId);
  }

  /** Drop all stores and reset the conflict index (for testing). */
  clear() {
    this._stores = {};
    this._conflicts = new ConflictIndex();
  }

  get size() { return Object.keys(this._stores).length; }
}

// ─── Rules ───────────────────────────────────────────────────────────────────

class FileConflictRule {
  async check(event, session, ctx) {
    if (event.type !== "prompt") return null;
    const files = event.live_modified_files || [];
    const repo = event.repoRoot || "";
    const sid = event.sessionId || "";
    const branch = event.branch || "";
    if (!files.length || !repo) return null;
    const conflicts = ctx.store.findConflicts(repo, files, sid).filter((c) => c.otherBranch !== branch);
    if (!conflicts.length) return null;
    const conflictFiles = [...new Set(conflicts.map((c) => c.file))];
    const conflictBranches = [...new Set(conflicts.map((c) => c.otherBranch))];
    return {
      type: "file-conflict",
      message: `Branch ${conflictBranches.join(", ")} also modified: ${conflictFiles.join(", ")}.`.slice(0, 500),
      files: conflictFiles,
    };
  }
}

class BranchDriftRule {
  async check(event, session, _ctx) {
    if (event.type !== "prompt" || !session) return null;
    const fileEvents = session.events.filter((e) => e.type === "file-write" || e.type === "file-edit");
    if (fileEvents.length < BRANCH_DRIFT_THRESHOLD) return null;
    return {
      type: "branch-drift",
      message: `${fileEvents.length} file changes on branch ${session.branch} without a restart checkpoint. Consider committing.`,
      files: [],
    };
  }
}

class SpecDeviationRule {
  async check(event, _session, _ctx) {
    if (event.type !== "prompt") return null;
    const files = event.live_modified_files || [];
    const summary = event.prompt_summary || "";
    if (!files.length || !summary) return null;
    const deviating = files.filter((f) => !summary.includes(f));
    if (!deviating.length) return null;
    return {
      type: "spec-deviation",
      message: `Modified files not mentioned in prompt: ${deviating.join(", ")}.`.slice(0, 500),
      files: deviating,
    };
  }
}

class RulesAdvisor {
  constructor() { this._rules = [new FileConflictRule(), new BranchDriftRule(), new SpecDeviationRule()]; }
  async adviseAll(event, session, ctx) {
    const results = [];
    for (const rule of this._rules) {
      const r = await rule.check(event, session, ctx);
      if (r !== null) results.push(r);
    }
    return results;
  }
}

// ─── Policy ──────────────────────────────────────────────────────────────────

const LEVEL_MAP = { "file-conflict": "intervene", "branch-drift": "advise", "spec-deviation": "advise" };

class InvocationPolicy {
  decide(results) {
    if (!results.length) return null;
    if (results.length >= 2) {
      return {
        level: "escalate", type: "multi-rule",
        message: results.map((r) => r.message).join("; "),
        reason: `Multiple concurrent risks: ${results.map((r) => r.type).join(", ")}.`,
        question: "Multiple risk signals fired simultaneously. Should I pause for human review or proceed?",
      };
    }
    const { type, message } = results[0];
    return { level: LEVEL_MAP[type] || "advise", type, message };
  }
}

// ─── Module-level registry (one per process; stores are per-session) ──────────

const _advisor = new RulesAdvisor();
const _policy = new InvocationPolicy();
const _registry = new StoreRegistry();

/**
 * Process an advise event.
 *
 * @param {object} event - The incoming event (must contain sessionId).
 * @param {StoreRegistry|null} registry - Optional registry for testing.
 *   Defaults to the module-level _registry.
 */
async function handleAdvise(event, registry = null) {
  const reg = registry !== null ? registry : _registry;
  const sessionId = event.sessionId || "";
  let store;
  if (sessionId) {
    store = reg.get(sessionId);
  } else {
    store = new SessionStore();
  }
  store.recordEvent(event);
  const session = store.getSession(sessionId);
  const results = await _advisor.adviseAll(event, session, { store });
  const decision = _policy.decide(results);
  if (!decision) return null;
  const files = results.flatMap((r) => r.files || []).filter((v, i, a) => a.indexOf(v) === i);
  return { level: decision.level, type: decision.type, message: decision.message,
           reason: decision.reason || "", question: decision.question || "", files };
}

/**
 * Drop the store for sessionId, freeing per-session state and purging the
 * session from the shared ConflictIndex to prevent memory leaks.
 *
 * @param {string} sessionId - The session that has ended.
 * @param {StoreRegistry|null} registry - Optional registry. Defaults to _registry.
 */
function handleSessionEnd(sessionId, registry = null) {
  const reg = registry !== null ? registry : _registry;
  reg.drop(sessionId);
}

module.exports = { handleAdvise, handleSessionEnd, StoreRegistry, SessionStore, RulesAdvisor, InvocationPolicy };
