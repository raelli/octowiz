"""Tests for octowiz-cache routing verification behavior."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from packages.memory_client.cli import cmd_get


class FakeGetArgs:
    def __init__(self, role="routing", namespace="allspark", refresh_memory=False):
        self.role = role
        self.namespace = namespace
        self.refresh_memory = refresh_memory
        self.cache_dir = None
        self.ttl_seconds = None


class TestCmdGetRoutingVerification(unittest.TestCase):
    def _run_cmd_get(self, args):
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cmd_get(args)
        return code, out.getvalue(), err.getvalue()

    @patch("packages.memory_client.cli.mark_routing_verified")
    @patch("packages.memory_client.cli.get_bundle", return_value="# routing bundle\n")
    def test_routing_get_marks_verification_timestamp(self, _mock_get_bundle, mock_mark_verified):
        code, out, err = self._run_cmd_get(FakeGetArgs(role="routing"))
        self.assertEqual(code, 0)
        self.assertIn("# routing bundle", out)
        self.assertEqual(err, "")
        mock_mark_verified.assert_called_once_with()

    @patch("packages.memory_client.cli.mark_routing_verified")
    @patch("packages.memory_client.cli.get_bundle", return_value="# planner bundle\n")
    def test_non_routing_get_does_not_mark_verification(self, _mock_get_bundle, mock_mark_verified):
        code, out, err = self._run_cmd_get(FakeGetArgs(role="planner"))
        self.assertEqual(code, 0)
        self.assertIn("# planner bundle", out)
        self.assertEqual(err, "")
        mock_mark_verified.assert_not_called()

    @patch("packages.memory_client.cli.mark_routing_verified", side_effect=OSError("disk full"))
    @patch("packages.memory_client.cli.get_bundle", return_value="# routing bundle\n")
    def test_routing_get_fails_if_timestamp_update_fails(self, _mock_get_bundle, _mock_mark_verified):
        code, out, err = self._run_cmd_get(FakeGetArgs(role="routing"))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("failed to update routing verification timestamp", err)

