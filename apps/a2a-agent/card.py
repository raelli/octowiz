import os

CAPABILITIES = [
    {"id": "octowiz.observe",           "name": "Observe",           "description": "Record session events without reacting.", "tags": ["monitoring"]},
    {"id": "octowiz.plan",              "name": "Plan",              "description": "Plan a coding task.", "tags": ["planning"]},
    {"id": "octowiz.review",            "name": "Review",            "description": "Review code changes.", "tags": ["review"]},
    {"id": "octowiz.dispatch",          "name": "Dispatch",          "description": "Start a new Claude Code background session. Operation: start (required fields: task, cwd; optional: name). Returns sessionId for use with manage_agents.", "tags": ["execution"]},
    {"id": "octowiz.manage_agents",     "name": "Manage Agents",     "description": "List, read logs, stop, remove, and respawn Claude Code background sessions via the claude agents CLI. Operations: list, logs, stop, rm, respawn.", "tags": ["agents"]},
    {"id": "octowiz.run_sandboxed",     "name": "Run Sandboxed",     "description": "Run a task in an isolated Sandcastle environment.", "tags": ["sandbox"]},
    {"id": "octowiz.load_memory",       "name": "Load Memory",       "description": "Fetch doctrine bundles from LiteLLM Memory.", "tags": ["memory"]},
    {"id": "octowiz.write_diary",       "name": "Write Diary",       "description": "Persist a Working or Long-Term Agent Diary entry.", "tags": ["diary", "experience"]},
    {"id": "octowiz.escalate_to_aelli", "name": "Escalate to ÆLLI",  "description": "Forward a strategic decision to ÆLLI via LiteLLM A2A.", "tags": ["escalation"]},
    {"id": "octowiz.marketplace_info",   "name": "Marketplace Info",  "description": "Resolve dependencies, discover skills, and check version compatibility via the IntegraHub Marketplace. Operations: discover, resolve, compat.", "tags": ["marketplace", "skills", "dependencies"]},
]

BASE_URL = os.environ.get("OCTOWIZ_BASE_URL", "http://octowiz:8000")

AGENT_CARD = {
    "name": "Octowiz Engineering Agent",
    "version": "0.9.0",
    "description": "ÆLLI's coding alter-ego. Orchestrates engineering sessions, monitors risks, and manages execution providers.",
    "url": f"{BASE_URL}/a2a/octowiz",
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
        "stateTransitionHistory": False,
    },
    "defaultInputModes": ["application/json"],
    "defaultOutputModes": ["application/json"],
    "skills": CAPABILITIES,
}
