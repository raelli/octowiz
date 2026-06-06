#!/bin/bash
# Auto-upgrade octowiz CLI when the plugin has been updated to a newer version.
# Runs at every SessionStart but exits immediately once the CLI is current.

_BADGE="\033[1m\033[38;5;135m--*\033[0m"
_DIM="\033[2m"
_RESET="\033[0m"
_log() { printf "${_BADGE} ${_DIM}%s${_RESET} %s\n" "$(date +%H:%M:%S)" "$1" >&2; }

# Nothing to do if octowiz-cache isn't installed yet
if ! command -v octowiz-cache &>/dev/null; then
    exit 0
fi

# v0.1.0+ supports --version flag — use it as the version gate
if octowiz-cache --version &>/dev/null; then
    exit 0  # v0.1.0+ already installed
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
    _log "[octowiz --* upgrade] CLI is outdated but no Python found. Run: pip install --upgrade git+https://github.com/raelli/octowiz.git"
    exit 0
fi

_log "[octowiz --* upgrade] CLI is outdated — upgrading to match plugin version..."
if "$PYTHON" -m pip install --upgrade --quiet "git+https://github.com/raelli/octowiz.git" 2>&1; then
    _log "[octowiz --* upgrade] CLI upgraded successfully."
else
    _log "[octowiz --* upgrade] Auto-upgrade failed. Run manually: pip install --upgrade git+https://github.com/raelli/octowiz.git"
fi

exit 0
