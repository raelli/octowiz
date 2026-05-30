"""Tests for octowiz-cache check subcommand."""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from packages.memory_client.cli import cmd_check
from packages.memory_client.env import CheckResult


def _make_result(hard_gaps=None, advisory_gaps=None):
    return CheckResult(
        hard_gaps=hard_gaps or [],
        advisory_gaps=advisory_gaps or [],
        machine_state_absent=False,
        repo_state_absent=False,
    )


class FakeArgs:
    def __init__(self, cwd=None, namespace="test", cache_dir=None, ttl_seconds=None):
        self.cwd = cwd
        self.namespace = namespace
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds


class TestCmdCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd_str = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, args, mock_result=None):
        if mock_result is None:
            mock_result = _make_result()
        out = io.StringIO()
        with patch("packages.memory_client.env.run_live_check", return_value=mock_result):
            with redirect_stdout(out):
                code = cmd_check(args)
        return code, json.loads(out.getvalue())

    def test_clean_exits_zero(self):
        code, data = self._run(FakeArgs(cwd=self.cwd_str))
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "clean")
        self.assertEqual(data["hard_gaps"], [])
        self.assertEqual(data["advisory_gaps"], [])

    def test_has_gaps_exits_one(self):
        result = _make_result(
            hard_gaps=["plugin_superpowers", "litellm_env"],
            advisory_gaps=["agent_file"],
        )
        code, data = self._run(FakeArgs(cwd=self.cwd_str), mock_result=result)
        self.assertEqual(code, 1)
        self.assertEqual(data["status"], "has_gaps")
        self.assertIn("plugin_superpowers", data["hard_gaps"])
        self.assertIn("agent_file", data["advisory_gaps"])

    def test_advisory_only_still_exits_zero(self):
        """Advisory gaps alone do NOT cause a non-zero exit; only hard_gaps do."""
        result = _make_result(advisory_gaps=["agent_file"])
        code, data = self._run(FakeArgs(cwd=self.cwd_str), mock_result=result)
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "clean")

    def test_default_cwd_is_path_cwd(self):
        """When --cwd not provided, uses Path.cwd()."""
        captured = []

        def fake_check(cwd, *a, **kw):
            captured.append(cwd)
            return _make_result()

        out = io.StringIO()
        with patch("packages.memory_client.env.run_live_check", side_effect=fake_check):
            with redirect_stdout(out):
                cmd_check(FakeArgs(cwd=None))
        self.assertEqual(captured[0], Path.cwd())

    def test_explicit_cwd_passed_through(self):
        captured = []

        def fake_check(cwd, *a, **kw):
            captured.append(cwd)
            return _make_result()

        out = io.StringIO()
        with patch("packages.memory_client.env.run_live_check", side_effect=fake_check):
            with redirect_stdout(out):
                cmd_check(FakeArgs(cwd=self.cwd_str))
        self.assertEqual(captured[0], Path(self.cwd_str))

    def test_json_output_has_all_three_keys(self):
        code, data = self._run(FakeArgs(cwd=self.cwd_str))
        self.assertIn("status", data)
        self.assertIn("hard_gaps", data)
        self.assertIn("advisory_gaps", data)
