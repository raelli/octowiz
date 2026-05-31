"""Tests for hooks/bridge.py — Octowiz Bridge event forwarding."""
import json
import os
import sys
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bridge import _build_event, _post_event, main


def _hook_data(hook="PostToolUse", tool="Write", tool_input=None, **extra):
    base = {
        "session_id": "sess-123",
        "cwd": "/repo",
        "hook_event_name": hook,
        "tool_name": tool,
        "tool_input": tool_input or {"file_path": "src/app.py"},
    }
    base.update(extra)
    return base


def _run_main(hook_data: dict, env: dict = None):
    """Run main() with controlled stdin and env, return (exit_code, stdout)."""
    import io
    from contextlib import redirect_stdout

    env = env or {}
    stdin_data = json.dumps(hook_data)
    buf = io.StringIO()

    with unittest.mock.patch.dict(os.environ, env, clear=False), \
         unittest.mock.patch("sys.stdin", io.StringIO(stdin_data)), \
         redirect_stdout(buf):
        code = main()

    return code, buf.getvalue()


# ---------------------------------------------------------------------------


class TestNoUrl(unittest.TestCase):
    def test_no_octowiz_a2a_url_makes_no_http_call(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True), \
             unittest.mock.patch("bridge._post_event") as mock_post:
            code, out = _run_main(_hook_data())
        mock_post.assert_not_called()
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")


class TestBuildEvent(unittest.TestCase):
    def _build(self, **kwargs):
        with unittest.mock.patch("bridge._git_context", return_value={"repoRoot": "/repo", "branch": "main"}):
            return _build_event(_hook_data(**kwargs))

    def test_write_tool_produces_file_write_event(self):
        event = self._build(tool="Write", tool_input={"file_path": "src/app.py"})
        self.assertEqual(event["type"], "file-write")
        self.assertIn("src/app.py", event["live_modified_files"])

    def test_edit_tool_produces_file_edit_event(self):
        event = self._build(tool="Edit", tool_input={"file_path": "src/models.py"})
        self.assertEqual(event["type"], "file-edit")
        self.assertIn("src/models.py", event["live_modified_files"])

    def test_notebook_edit_uses_notebook_path(self):
        event = self._build(tool="NotebookEdit", tool_input={"notebook_path": "analysis.ipynb"})
        self.assertEqual(event["type"], "file-edit")
        self.assertIn("analysis.ipynb", event["live_modified_files"])

    def test_bash_tool_produces_tool_used_event(self):
        event = self._build(tool="Bash", tool_input={"command": "pytest"})
        self.assertEqual(event["type"], "tool-used")
        self.assertNotIn("live_modified_files", event)

    def test_user_prompt_submit_produces_prompt_event(self):
        data = {
            "session_id": "sess-abc",
            "cwd": "/repo",
            "hook_event_name": "UserPromptSubmit",
            "prompt": "refactor the auth module",
        }
        with unittest.mock.patch("bridge._git_context", return_value={"repoRoot": "/repo", "branch": "feat/x"}):
            event = _build_event(data)
        self.assertEqual(event["type"], "prompt")
        self.assertIn("refactor", event["prompt_summary"])

    def test_session_start_produces_session_start_event(self):
        data = {
            "session_id": "sess-xyz",
            "cwd": "/repo",
            "hook_event_name": "SessionStart",
        }
        with unittest.mock.patch("bridge._git_context", return_value={"repoRoot": "/repo", "branch": "main"}):
            event = _build_event(data)
        self.assertEqual(event["type"], "session-start")
        self.assertEqual(event["sessionId"], "sess-xyz")
        self.assertEqual(event["capability"], "octowiz.advise")
        self.assertNotIn("prompt_summary", event)
        self.assertNotIn("live_modified_files", event)

    def test_unknown_hook_returns_none(self):
        data = {"hook_event_name": "Notification", "session_id": "x", "cwd": "/"}
        self.assertIsNone(_build_event(data))

    def test_notebook_edit_uses_notebook_path(self):
        event = self._build(tool="NotebookEdit", tool_input={"notebook_path": "analysis.ipynb"})
        self.assertEqual(event["type"], "file-edit")
        self.assertIn("analysis.ipynb", event["live_modified_files"])


class TestPostEvent(unittest.TestCase):
    def _make_response(self, artifact_text):
        import uuid
        return {
            "jsonrpc": "2.0", "id": 1,
            "result": {
                "kind": "task",
                "id": str(uuid.uuid4()),
                "contextId": str(uuid.uuid4()),
                "status": {"state": "completed"},
                "artifacts": [{"artifactId": str(uuid.uuid4()), "name": "advisory",
                               "parts": [{"kind": "text", "text": artifact_text}]}],
            },
        }

    def test_server_returns_advice_parsed_correctly(self):
        advice = {"type": "spec-deviation", "message": "payment.py not in prompt", "files": ["payment.py"]}
        mock_resp = unittest.mock.MagicMock()
        mock_resp.raise_for_status = unittest.mock.MagicMock()
        mock_resp.json.return_value = self._make_response(json.dumps(advice))

        with unittest.mock.patch("httpx.post", return_value=mock_resp):
            result = _post_event("http://octowiz:8000", {"type": "prompt"})

        self.assertEqual(result["type"], "spec-deviation")

    def test_server_returns_null_advice_returns_none(self):
        mock_resp = unittest.mock.MagicMock()
        mock_resp.raise_for_status = unittest.mock.MagicMock()
        mock_resp.json.return_value = self._make_response("{}")

        with unittest.mock.patch("httpx.post", return_value=mock_resp):
            result = _post_event("http://octowiz:8000", {"type": "prompt"})

        self.assertIsNone(result)

    def test_http_error_returns_none_never_raises(self):
        import httpx
        with unittest.mock.patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            result = _post_event("http://octowiz:8000", {"type": "prompt"})
        self.assertIsNone(result)


class TestMainOutput(unittest.TestCase):
    def test_advice_written_as_system_message_to_stdout(self):
        advice = {"type": "file-conflict", "message": "branch-b also modified auth.py", "files": ["auth.py"]}
        with unittest.mock.patch("bridge._git_context", return_value={"repoRoot": "/repo", "branch": "main"}), \
             unittest.mock.patch("bridge._post_event", return_value=advice):
            code, out = _run_main(
                _hook_data(tool="Write", tool_input={"file_path": "auth.py"}),
                env={"OCTOWIZ_A2A_URL": "http://octowiz:8000"},
            )
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertIn("file-conflict", parsed["systemMessage"])
        self.assertIn("auth.py", parsed["systemMessage"])

    def test_no_advice_produces_empty_stdout(self):
        with unittest.mock.patch("bridge._git_context", return_value={"repoRoot": "/repo", "branch": "main"}), \
             unittest.mock.patch("bridge._post_event", return_value=None):
            code, out = _run_main(
                _hook_data(tool="Write"),
                env={"OCTOWIZ_A2A_URL": "http://octowiz:8000"},
            )
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")
