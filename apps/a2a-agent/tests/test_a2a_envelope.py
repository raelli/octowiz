"""Tests for the capability error-envelope contract owned by a2a.py.

The Node daemon maps artifact status == "error" to the task queue's error
state (src/daemon.js). err() and require() are the only place that shape
is built — these tests pin the contract both sides depend on.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from a2a import err, require


class TestErr:
    def test_minimal_error_artifact(self):
        assert err("task is required") == {"status": "error", "message": "task is required"}

    def test_extra_fields_pass_through(self):
        artifact = err("dispatch timed out (orphaned)", session_id="s1")
        assert artifact == {
            "status": "error",
            "message": "dispatch timed out (orphaned)",
            "session_id": "s1",
        }

    def test_message_is_optional(self):
        artifact = err(session_id="s1", output="logs")
        assert artifact == {"status": "error", "session_id": "s1", "output": "logs"}
        assert "message" not in artifact

    def test_status_is_exactly_the_string_the_daemon_matches(self):
        # daemon.js: normalized.status === "error" ? "error" : "completed"
        assert err("x")["status"] == "error"


class TestRequire:
    def test_returns_none_when_all_fields_present(self):
        assert require({"task": "t", "cwd": "/repo"}, "task", "cwd") is None

    def test_first_missing_field_wins(self):
        artifact = require({"cwd": "/repo"}, "task", "cwd")
        assert artifact == {"status": "error", "message": "task is required"}

    def test_empty_string_counts_as_missing(self):
        artifact = require({"task": ""}, "task")
        assert artifact == {"status": "error", "message": "task is required"}

    def test_no_fields_is_a_no_op(self):
        assert require({}) is None
