#!/bin/bash
# Auto-upgrade octowiz CLI when the plugin has been updated to a newer version.
# Runs at every SessionStart but exits immediately once the CLI is current.

# Nothing to do if octowiz-cache isn't installed yet
if ! command -v octowiz-cache &>/dev/null; then
    exit 0
fi

# 'init' subcommand was added in v0.0.4 — use its presence as the version gate
if octowiz-cache init --help &>/dev/null; then
    exit 0  # Already current
fi

# Find the Python that owns this octowiz-cache installation so we upgrade
# the right environment (handles venv, pipx, uv, system pip, etc.)
OCTOWIZ_BIN=$(dirname "$(command -v octowiz-cache)")
PYTHON=""
for candidate in "$OCTOWIZ_BIN/python" "$OCTOWIZ_BIN/python3" python3 python; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[octowiz] CLI is outdated but no Python found to upgrade. Run: pip install --upgrade git+https://github.com/raelli/octowiz.git" >&2
    exit 0
fi

echo "[octowiz] CLI is outdated — upgrading to match plugin version..." >&2
if "$PYTHON" -m pip install --upgrade --quiet "git+https://github.com/raelli/octowiz.git" 2>&1; then
    echo "[octowiz] CLI upgraded successfully." >&2
else
    echo "[octowiz] Auto-upgrade failed. Run manually: pip install --upgrade git+https://github.com/raelli/octowiz.git" >&2
fi

exit 0
