## Agent skills

### Issue tracker

Issues live in GitHub Issues for raelli/octowiz. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role label vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Path validation (dual-validator pattern)

`src/policy.js` is the canonical `OCTOWIZ_ALLOWED_ROOTS` enforcement point (runs in the Node daemon before any task is forwarded); `apps/a2a-agent/path_guard.py` is a secondary defence-in-depth check — both must be kept in sync when allowlist logic changes.
