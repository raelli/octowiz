# octowiz

Claude Code plugin and engineering agent bridge for the GFE/IntegraHub ecosystem.

## Releasing & deploying

See [`DEPLOYING.md`](DEPLOYING.md) for the full release checklist and how the marketplace sync works.

Key rules:
- Bump **all three** `package.json`, `.claude-plugin/plugin.json`, and `pyproject.toml` together — mismatched versions break `/plugin update` and make Python upgrade diagnostics unreliable.
- Use `pnpm` everywhere (installs, CI, Dockerfiles). Never `npm`.
- Tag format: `v<semver>`. The `release.yml` workflow auto-syncs the marketplace on tag push.

## Commands

```bash
pnpm test          # run test suite
pnpm run lint      # lint
nr lint --fix      # lint with auto-fix (via ni)
```

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`raelli/octowiz`).
