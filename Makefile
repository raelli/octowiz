# Octowiz — top-level Makefile
#
# All targets run from the repo root. PYTHONPATH is set explicitly so that
# the providers/ and packages/ packages always resolve to this directory,
# not to any .claude/worktrees/* checkout that may share the Python process.

PYTHON      := python3
UVICORN     := $(PYTHON) -m uvicorn
A2A_DIR     := apps/a2a-agent
HOST        ?= 127.0.0.1
PORT        ?= 8000
RELOAD_FLAG :=

# Pass RELOAD=1 to enable auto-reload: make serve RELOAD=1
ifeq ($(RELOAD),1)
RELOAD_FLAG := --reload
endif

# Ensure providers/ and packages/ always resolve from the repo root.
export PYTHONPATH := $(CURDIR)

.PHONY: help install serve dev test test-a2a test-packages test-providers clean

help:
	@echo ""
	@echo "  make install          Install the package in editable mode"
	@echo "  make serve            Start the A2A agent server (port $(PORT))"
	@echo "  make serve PORT=9000  Start on a custom port"
	@echo "  make dev              Start with auto-reload"
	@echo "  make test             Run all tests"
	@echo "  make test-a2a         Run apps/a2a-agent tests only"
	@echo "  make test-packages    Run packages/ tests only"
	@echo "  make test-providers   Run providers/ tests only"
	@echo "  make clean            Remove __pycache__ and .pyc files"
	@echo ""

# ── Installation ─────────────────────────────────────────────────────────────

install:
	$(PYTHON) -m pip install -e .

# ── Server ───────────────────────────────────────────────────────────────────

serve:
	$(UVICORN) main:app \
		--app-dir $(A2A_DIR) \
		--host $(HOST) \
		--port $(PORT) \
		$(RELOAD_FLAG)

dev: RELOAD_FLAG=--reload
dev: serve

# ── Tests ────────────────────────────────────────────────────────────────────

test:
	$(PYTHON) -m pytest tests/ packages/ providers/ -q
	$(PYTHON) -m pytest $(A2A_DIR)/tests/ -q

test-a2a:
	$(PYTHON) -m pytest $(A2A_DIR)/tests/ -v

test-packages:
	$(PYTHON) -m pytest packages/ -v

test-providers:
	$(PYTHON) -m pytest providers/ -v

# ── Housekeeping ──────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -not -path './.claude/*' -exec rm -rf {} + 2>/dev/null; true
	find . -name '*.pyc' -not -path './.claude/*' -delete 2>/dev/null; true
