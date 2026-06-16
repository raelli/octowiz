# Releasing & Deploying octowiz

Octowiz ships as a Claude Code plugin via the IntegraHub Marketplace. There is no server to deploy — "deploying" means publishing a new GitHub release so the marketplace entry updates and users can run `/plugin update`.

Marketplace URL: `https://llm.integrahub.de/claude-code/marketplace.json`

---

## How it works

1. A new version is merged to `main` and tagged `v<semver>`.
2. The [`release.yml`](.github/workflows/release.yml) workflow fires on the tag push, builds the release, then upserts the new version directly into the LiteLLM marketplace database via the `POST /claude-code/plugins` endpoint.
3. The marketplace JSON reflects the new version immediately after the workflow completes.
4. Claude Code users update by running `/plugin update` — their local CLI checks the marketplace, downloads the new version, and restarts the hook runner.

The [`marketplace-sync.yml`](.github/workflows/marketplace-sync.yml) workflow is a safety net that fires on any manually pushed `v*` tag not covered by the release flow.

---

## Release checklist

Run through this before tagging. Every item must be green before the PR merges.

**Pre-merge**
- [ ] `package.json` version bumped (e.g. `0.9.10` → `0.9.11`)
- [ ] `.claude-plugin/plugin.json` version bumped to the same value
  — both files **must** match; missing `plugin.json` breaks `/plugin update`
- [ ] `pyproject.toml` `version =` bumped to the same value
  — mismatched Python metadata makes `pip show octowiz` and upgrade diagnostics unreliable
- [ ] `pnpm test` — all tests green locally
- [ ] `nr lint --fix` run; no lint errors
- [ ] PR opened, reviewed, squash-merged to main

**Tag & release**
- [ ] `git tag v<version>` on the merge commit, `git push origin v<version>`
- [ ] GitHub release created from the tag with a short changelog
- [ ] `release.yml` workflow completes without error

**Post-release verification**
- [ ] Marketplace reflects the new version:
  ```bash
  curl -s https://llm.integrahub.de/claude-code/marketplace.json \
    | python3 -c "import sys,json; [print(p['name'], p['version']) for p in json.load(sys.stdin) if p['name']=='octowiz']"
  ```
- [ ] `/plugin update` in Claude Code installs the new version without error
- [ ] Hook tags in the terminal show the expected `[--*] HH:MM:SS [octowiz - <action>]` format

---

## Version bump locations

| File | Field |
|---|---|
| `package.json` | `"version"` |
| `.claude-plugin/plugin.json` | `"version"` |
| `pyproject.toml` | `version =` |

All three must be identical. Verify before tagging:

```bash
node -e "console.log(require('./package.json').version)" && \
node -e "console.log(require('./.claude-plugin/plugin.json').version)" && \
python3 -c "
import re, pathlib
m = re.search(r'^version\s*=\s*\"(.+?)\"', pathlib.Path('pyproject.toml').read_text(), re.M)
print(m.group(1) if m else 'NOT FOUND')
"
```

All three lines must print the same value. The marketplace entry is written by the CI workflow from `package.json` at tag time.

---

## Marketplace credentials

The `release.yml` workflow reads `secrets.LITELLM_MASTER_KEY` (set in the repo's GitHub Actions secrets) to authenticate the marketplace upsert. If the workflow fails with a 401, the key needs rotation in the repo settings.

For a manual upsert:

```bash
curl -sX POST https://llm.integrahub.de/claude-code/plugins \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"octowiz","version":"<version>","url":"https://github.com/raelli/octowiz"}'
```
