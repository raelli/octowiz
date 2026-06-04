# Sandcastle sandbox image for octowiz.run_sandboxed
#
# Provides: git, Node.js, and the claude CLI (Anthropic Claude Code).
# The container is launched by providers/sandcastle/runner.py via:
#
#   docker run --rm --name=octowiz-{id} \
#     --volume={cwd}:{cwd}:rw --workdir {cwd} \
#     --env ANTHROPIC_API_KEY --env ANTHROPIC_BASE_URL --env AELLI_AUTH_TOKEN \
#     {IMAGE} claude --print -- {task}
#
# ANTHROPIC_API_KEY must be set in the host environment before launch.
# The image itself contains no credentials.

FROM node:22-bookworm-slim

# Install git and CA certificates (needed for HTTPS git operations and claude telemetry).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install claude CLI globally via pnpm (enabled through corepack).
# PNPM_HOME must be set before a global install or pnpm exits with ERR_PNPM_NO_GLOBAL_BIN_DIR.
# Installs the latest published version. For reproducible builds, pin by specifying
# @anthropic-ai/claude-code@VERSION (e.g. @2.1.162) and update on each release.
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME/bin:$PATH"
RUN corepack enable pnpm && pnpm install -g @anthropic-ai/claude-code

# Sanity-check: confirm the expected binaries are available.
RUN git --version && node --version && claude --version

# No ENTRYPOINT -- the runner supplies the full command (claude ... or sh -c ...).
# CMD is intentionally omitted to avoid interfering with the injected task command.
