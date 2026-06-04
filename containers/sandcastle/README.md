# Sandcastle Sandbox Image

Docker/Podman image used by `octowiz.run_sandboxed` (Gap 5) to execute coding
tasks in an isolated container. Provides `git`, Node.js, and the `claude` CLI.

## What is inside

| Component | Version |
|-----------|---------|
| Base      | node:22-bookworm-slim |
| git       | 2.39.x (Debian bookworm) |
| Node.js   | 22.x |
| claude    | @anthropic-ai/claude-code (latest at build time) |

## Required environment variables

The image itself contains no credentials. Set these on the host (the octowiz
server process) before launching containers:

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Yes | Authenticates `claude` CLI calls to Anthropic |
| `ANTHROPIC_BASE_URL` | No | Override API endpoint (e.g. LiteLLM proxy) |
| `AELLI_AUTH_TOKEN` | No | Forward-looking: used by AELLI advisory hooks if installed inside the container |

Variables are forwarded name-only via `--env VAR` (not `--env VAR=value`), so
their values are read from the host environment by Docker/Podman at runtime and
never appear in the container's argv. Unset variables are silently skipped.

**Important:** The octowiz server process (uvicorn/Node daemon) must itself
have `ANTHROPIC_API_KEY` exported. The env var passthrough mechanism reads from
the server process's inherited environment — if the server was not started with
the key set, passthrough is a silent no-op and claude will fail with an auth
error inside the container.

## Build

```bash
# From the repo root:
make build-sandbox-image

# Or directly:
docker build -t ghcr.io/raelli/octowiz-sandbox:latest containers/sandcastle/
```

## Push to GHCR

Requires `ghcr.io` credentials (GitHub Actions handles this automatically via
the `build-sandbox-image` workflow).

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
docker push ghcr.io/raelli/octowiz-sandbox:latest
```

## Usage

Set `SANDCASTLE_IMAGE` in the octowiz server environment:

```bash
export SANDCASTLE_IMAGE=ghcr.io/raelli/octowiz-sandbox:latest
export ANTHROPIC_API_KEY=sk-ant-...
```

The runner launches containers automatically. You can also invoke manually for
testing:

```bash
# No-branch task
docker run --rm \
  --volume=/path/to/repo:/path/to/repo:rw \
  --workdir=/path/to/repo \
  --env ANTHROPIC_API_KEY \
  ghcr.io/raelli/octowiz-sandbox:latest \
  claude --print -- "describe the project structure"

# With branch checkout
docker run --rm \
  --volume=/path/to/repo:/path/to/repo:rw \
  --workdir=/path/to/repo \
  --env ANTHROPIC_API_KEY \
  ghcr.io/raelli/octowiz-sandbox:latest \
  sh -c 'git checkout "$1" && claude --print -- "$2"' \
  -- feat/my-branch "fix the failing tests"
```

## Known limitations

- The container runs as root (UID 0). This is acceptable for v1 because the
  bind-mounted working directory belongs to the host user; running non-root
  would cause volume permission mismatches on most host configurations.
- `claude --print` non-interactive execution was verified to work without
  prompts for `--version` and `--help` inside the image. End-to-end task
  execution (which requires a valid `ANTHROPIC_API_KEY` and network access to
  the Anthropic API) was not verified at image build time.
- `AELLI_AUTH_TOKEN` passthrough is forward-looking. The v1 image does not
  include the octowiz hooks or bridge, so nothing inside the container reads
  this token today. It is included so operators can opt in by installing hooks
  in their task scripts.
