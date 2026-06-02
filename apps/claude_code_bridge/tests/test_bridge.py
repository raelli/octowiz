"""Tests for hooks/bridge.py — Octowiz Bridge event forwarding to AELLI."""
import json
import os
import sys
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bridge import _build_event, _post_event, _resolve_router_url, _route_event, main


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


def _run_main_with_stderr(hook_data: dict, env: dict = None):
    """Run main() capturing both stdout and stderr, return (exit_code, stdout, stderr)."""
    import io
    from contextlib import redirect_stdout, redirect_stderr

    env = env or {}
    stdin_data = json.dumps(hook_data)
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    with unittest.mock.patch.dict(os.environ, env, clear=False), \
         unittest.mock.patch("sys.stdin", io.StringIO(stdin_data)), \
         redirect_stdout(stdout_buf), \
         redirect_stderr(stderr_buf):
        code = main()

    return code, stdout_buf.getvalue(), stderr_buf.getvalue()


# ---------------------------------------------------------------------------


class TestDefaultUrl(unittest.TestCase):
    def test_no_env_set_uses_default_localhost_and_exits_cleanly(self):
        """Without AELLI_DEV_ADVISOR_URL set, bridge uses the localhost default and exits 0."""
        with unittest.mock.patch.dict(os.environ, {}, clear=True), \
             unittest.mock.patch("bridge._post_event", return_value=None) as mock_post:
            code, out = _run_main(_hook_data())
        # The bridge should call _post_event (with localhost default), not skip
        mock_post.assert_called_once()
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")

    def test_posts_to_aelli_dev_advisor_url(self):
        """bridge.py posts to AELLI_DEV_ADVISOR_URL when AELLI_LITELLM_BASE is absent."""
        captured_urls = []

        def fake_post(url, event):
            captured_urls.append(url)
            return None

        with unittest.mock.patch("bridge._git_context", return_value={"repoRoot": "/repo", "branch": "main"}), \
             unittest.mock.patch("bridge._post_event", side_effect=fake_post):
            _run_main(
                _hook_data(tool="Write", tool_input={"file_path": "auth.py"}),
                # Explicitly absent AELLI_LITELLM_BASE so AELLI_DEV_ADVISOR_URL is used
                env={"AELLI_DEV_ADVISOR_URL": "http://localhost:3456/a2a/dev-advisor",
                     "AELLI_LITELLM_BASE": ""},
            )

        self.assertEqual(len(captured_urls), 1)
        self.assertEqual(captured_urls[0], "http://localhost:3456/a2a/dev-advisor")

    def test_litellm_base_takes_priority_over_dev_advisor_url(self):
        """AELLI_LITELLM_BASE overrides AELLI_DEV_ADVISOR_URL, matching a2a-client.js behaviour."""
        captured_urls = []

        def fake_post(url, event):
            captured_urls.append(url)
            return None

        with unittest.mock.patch("bridge._git_context", return_value={"repoRoot": "/repo", "branch": "main"}), \
             unittest.mock.patch("bridge._post_event", side_effect=fake_post):
            _run_main(
                _hook_data(tool="Write", tool_input={"file_path": "auth.py"}),
                env={
                    "AELLI_LITELLM_BASE": "https://gateway.example.com",
                    "AELLI_DEV_ADVISOR_URL": "http://localhost:3456/a2a/dev-advisor",
                },
            )

        self.assertEqual(len(captured_urls), 1)
        self.assertEqual(captured_urls[0], "https://gateway.example.com/a2a/aelli-dev-advisor/message/send")

    def test_litellm_base_used_when_dev_advisor_url_absent(self):
        """AELLI_LITELLM_BASE works even without AELLI_DEV_ADVISOR_URL set."""
        captured_urls = []

        def fake_post(url, event):
            captured_urls.append(url)
            return None

        with unittest.mock.patch("bridge._git_context", return_value={"repoRoot": "/repo", "branch": "main"}), \
             unittest.mock.patch("bridge._post_event", side_effect=fake_post):
            _run_main(
                _hook_data(tool="Edit", tool_input={"file_path": "main.py"}),
                env={"AELLI_LITELLM_BASE": "https://gateway.example.com"},
            )

        self.assertEqual(len(captured_urls), 1)
        self.assertEqual(captured_urls[0], "https://gateway.example.com/a2a/aelli-dev-advisor/message/send")

    def test_post_event_sends_x_aelli_secret_header(self):
        """_post_event sends AELLI_AUTH_TOKEN as x-aelli-secret header."""
        captured_headers = {}

        mock_resp = unittest.mock.MagicMock()
        mock_resp.raise_for_status = unittest.mock.MagicMock()
        mock_resp.json.return_value = {
            "jsonrpc": "2.0", "id": 1,
            "result": {"artifacts": []},
        }

        def fake_httpx_post(url, json=None, headers=None, timeout=None):
            captured_headers.update(headers or {})
            return mock_resp

        with unittest.mock.patch.dict(os.environ, {"AELLI_AUTH_TOKEN": "my-token"}, clear=False), \
             unittest.mock.patch("httpx.post", side_effect=fake_httpx_post):
            _post_event("http://localhost:3456/a2a/dev-advisor", {"type": "prompt"})

        self.assertEqual(captured_headers.get("x-aelli-secret"), "my-token")
        self.assertNotIn("x-octowiz-secret", captured_headers)
        self.assertNotIn("Authorization", captured_headers)

    def test_post_event_sends_message_send_method(self):
        """_post_event uses method='message/send' (AELLI format), not 'octowiz/event'."""
        captured_bodies = []

        mock_resp = unittest.mock.MagicMock()
        mock_resp.raise_for_status = unittest.mock.MagicMock()
        mock_resp.json.return_value = {
            "jsonrpc": "2.0", "id": 1,
            "result": {"artifacts": []},
        }

        def fake_httpx_post(url, json=None, headers=None, timeout=None):
            captured_bodies.append(json)
            return mock_resp

        with unittest.mock.patch("httpx.post", side_effect=fake_httpx_post):
            _post_event("http://localhost:3456/a2a/dev-advisor", {"type": "prompt"})

        self.assertEqual(len(captured_bodies), 1)
        self.assertEqual(captured_bodies[0]["method"], "message/send")
        # Verify parts use 'kind' field (AELLI format)
        parts = captured_bodies[0]["params"]["message"]["parts"]
        self.assertEqual(parts[0]["kind"], "text")


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
        self.assertNotIn("prompt_summary", event)
        self.assertNotIn("live_modified_files", event)

    def test_unknown_hook_returns_none(self):
        data = {"hook_event_name": "Notification", "session_id": "x", "cwd": "/"}
        self.assertIsNone(_build_event(data))


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
            result = _post_event("http://localhost:3456/a2a/dev-advisor", {"type": "prompt"})

        self.assertEqual(result["type"], "spec-deviation")

    def test_server_returns_null_advice_returns_none(self):
        mock_resp = unittest.mock.MagicMock()
        mock_resp.raise_for_status = unittest.mock.MagicMock()
        mock_resp.json.return_value = self._make_response("{}")

        with unittest.mock.patch("httpx.post", return_value=mock_resp):
            result = _post_event("http://localhost:3456/a2a/dev-advisor", {"type": "prompt"})

        self.assertIsNone(result)

    def test_http_error_returns_none_never_raises(self):
        import httpx
        with unittest.mock.patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            result = _post_event("http://localhost:3456/a2a/dev-advisor", {"type": "prompt"})
        self.assertIsNone(result)


class TestMainOutput(unittest.TestCase):
    def test_advice_written_as_system_message_to_stdout(self):
        advice = {"type": "file-conflict", "message": "branch-b also modified auth.py", "files": ["auth.py"]}
        with unittest.mock.patch("bridge._git_context", return_value={"repoRoot": "/repo", "branch": "main"}), \
             unittest.mock.patch("bridge._post_event", return_value=advice):
            code, out = _run_main(
                _hook_data(tool="Write", tool_input={"file_path": "auth.py"}),
                env={"AELLI_DEV_ADVISOR_URL": "http://localhost:3456/a2a/dev-advisor"},
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
                env={"AELLI_DEV_ADVISOR_URL": "http://localhost:3456/a2a/dev-advisor"},
            )
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")


class TestVerboseLogging(unittest.TestCase):
    def test_network_error_logs_to_stderr_when_verbose(self):
        import httpx
        with unittest.mock.patch("bridge._git_context", return_value={"repoRoot": "/repo", "branch": "main"}), \
             unittest.mock.patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            code, out, err = _run_main_with_stderr(
                _hook_data(tool="Write", tool_input={"file_path": "auth.py"}),
                env={"AELLI_DEV_ADVISOR_URL": "http://localhost:3456/a2a/dev-advisor", "OCTOWIZ_VERBOSE": "1"},
            )
        self.assertEqual(code, 0)   # never blocks
        self.assertEqual(out.strip(), "")
        self.assertIn("advisory delivery failed", err)

    def test_network_error_silent_when_not_verbose(self):
        import httpx
        with unittest.mock.patch("bridge._git_context", return_value={"repoRoot": "/repo", "branch": "main"}), \
             unittest.mock.patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            code, out, err = _run_main_with_stderr(
                _hook_data(tool="Write", tool_input={"file_path": "auth.py"}),
                env={"AELLI_DEV_ADVISOR_URL": "http://octowiz-external:3456/a2a/dev-advisor"},
            )
        self.assertEqual(code, 0)
        # Advisory delivery error must NOT appear (URL is non-local http:// so the
        # cleartext-token warning may still fire, but that's a separate concern).
        self.assertNotIn("advisory delivery failed", err)

    def test_invalid_stdin_logs_to_stderr_when_verbose(self):
        import io as _io
        from contextlib import redirect_stdout, redirect_stderr
        stdout_buf = _io.StringIO()
        stderr_buf = _io.StringIO()
        # Use a local URL to suppress the unrelated cleartext-HTTP warning on stderr.
        with unittest.mock.patch.dict(
                os.environ,
                {"AELLI_DEV_ADVISOR_URL": "http://localhost:3456/a2a/dev-advisor", "OCTOWIZ_VERBOSE": "1"},
                clear=False), \
             unittest.mock.patch("sys.stdin", _io.StringIO("not json at all")), \
             redirect_stdout(stdout_buf), \
             redirect_stderr(stderr_buf):
            code = main()
        self.assertEqual(code, 0)
        self.assertIn("could not parse stdin", stderr_buf.getvalue())


class TestResolveRouterUrl(unittest.TestCase):
    def setUp(self):
        # Ensure a clean env for each test
        for key in ("AELLI_ROUTER_URL", "AELLI_LITELLM_BASE"):
            os.environ.pop(key, None)

    def tearDown(self):
        for key in ("AELLI_ROUTER_URL", "AELLI_LITELLM_BASE"):
            os.environ.pop(key, None)

    def test_returns_none_when_no_env_set(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            # Remove both keys explicitly
            env = {k: v for k, v in os.environ.items()
                   if k not in ("AELLI_ROUTER_URL", "AELLI_LITELLM_BASE")}
            with unittest.mock.patch.dict(os.environ, env, clear=True):
                result = _resolve_router_url()
        self.assertIsNone(result)

    def test_returns_aelli_router_url_directly_when_set(self):
        with unittest.mock.patch.dict(os.environ, {"AELLI_ROUTER_URL": "http://router:5000/route"}, clear=False):
            result = _resolve_router_url()
        self.assertEqual(result, "http://router:5000/route")

    def test_derives_router_url_from_litellm_base(self):
        with unittest.mock.patch.dict(
            os.environ,
            {"AELLI_LITELLM_BASE": "http://localhost:4000", "AELLI_ROUTER_URL": ""},
            clear=False,
        ):
            result = _resolve_router_url()
        self.assertEqual(result, "http://localhost:4000/a2a/aelli-router/message/send")

    def test_aelli_router_url_takes_precedence_over_litellm_base(self):
        with unittest.mock.patch.dict(
            os.environ,
            {"AELLI_ROUTER_URL": "http://explicit-router/route",
             "AELLI_LITELLM_BASE": "http://gateway:4000"},
            clear=False,
        ):
            result = _resolve_router_url()
        self.assertEqual(result, "http://explicit-router/route")


class TestRouteEvent(unittest.TestCase):
    def tearDown(self):
        for key in ("AELLI_ROUTER_URL", "AELLI_LITELLM_BASE", "AELLI_AUTH_TOKEN"):
            os.environ.pop(key, None)

    def test_does_nothing_when_router_url_not_set(self):
        """_route_event is a no-op when _resolve_router_url returns None — never raises."""
        with unittest.mock.patch("bridge._resolve_router_url", return_value=None), \
             unittest.mock.patch("httpx.post") as mock_post:
            _route_event("feature", {"content": "hello", "fileCount": 0})
        mock_post.assert_not_called()

    def test_posts_to_router_url_when_set(self):
        mock_resp = unittest.mock.MagicMock()
        mock_resp.raise_for_status = unittest.mock.MagicMock()
        mock_resp.text = 'data: {"router":"aelli","tier":"fast"}\n'

        with unittest.mock.patch(
            "bridge._resolve_router_url",
            return_value="http://localhost:4000/a2a/aelli-router/message/send",
        ), unittest.mock.patch("httpx.post", return_value=mock_resp) as mock_post:
            _route_event("feature", {"content": "fix auth", "fileCount": 2})

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        self.assertEqual(call_kwargs[0][0], "http://localhost:4000/a2a/aelli-router/message/send")

    def test_embeds_task_kind_and_data_in_payload(self):
        captured_bodies = []
        mock_resp = unittest.mock.MagicMock()
        mock_resp.raise_for_status = unittest.mock.MagicMock()
        mock_resp.text = 'data: {"tier":"standard"}\n'

        def fake_post(url, json=None, headers=None, timeout=None):
            captured_bodies.append(json)
            return mock_resp

        with unittest.mock.patch(
            "bridge._resolve_router_url",
            return_value="http://localhost:4000/a2a/aelli-router/message/send",
        ), unittest.mock.patch("httpx.post", side_effect=fake_post):
            _route_event("feature", {"content": "hello", "fileCount": 3})

        self.assertEqual(len(captured_bodies), 1)
        inner = json.loads(captured_bodies[0]["params"]["message"]["parts"][0]["text"])
        self.assertEqual(inner["type"], "route")
        self.assertEqual(inner["taskKind"], "feature")
        self.assertEqual(inner["content"], "hello")
        self.assertEqual(inner["fileCount"], 3)

    def test_fail_open_on_network_error(self):
        """_route_event never raises on connection failure."""
        import httpx
        with unittest.mock.patch(
            "bridge._resolve_router_url",
            return_value="http://localhost:4000/a2a/aelli-router/message/send",
        ), unittest.mock.patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            # Should not raise
            _route_event("feature", {"content": "test", "fileCount": 0})

    def test_route_called_for_user_prompt_submit_in_main(self):
        """main() calls _route_event for UserPromptSubmit hooks."""
        hook_data = {
            "session_id": "sess-abc",
            "cwd": "/repo",
            "hook_event_name": "UserPromptSubmit",
            "prompt": "refactor auth",
        }
        with unittest.mock.patch("bridge._git_context", return_value={"repoRoot": "/repo", "branch": "main"}), \
             unittest.mock.patch("bridge._git_modified_files", return_value=["auth.py"]), \
             unittest.mock.patch("bridge._post_event", return_value=None), \
             unittest.mock.patch("bridge._route_event") as mock_route:
            _run_main(hook_data, env={"AELLI_DEV_ADVISOR_URL": "http://localhost:3456/a2a/dev-advisor"})

        mock_route.assert_called_once()
        call_args = mock_route.call_args[0]
        self.assertEqual(call_args[0], "feature")
        self.assertIn("content", call_args[1])
        self.assertIn("fileCount", call_args[1])

    def test_route_not_called_for_post_tool_use_in_main(self):
        """_route_event is NOT called for PostToolUse hooks."""
        with unittest.mock.patch("bridge._git_context", return_value={"repoRoot": "/repo", "branch": "main"}), \
             unittest.mock.patch("bridge._post_event", return_value=None), \
             unittest.mock.patch("bridge._route_event") as mock_route:
            _run_main(
                _hook_data(tool="Write", tool_input={"file_path": "auth.py"}),
                env={"AELLI_DEV_ADVISOR_URL": "http://localhost:3456/a2a/dev-advisor"},
            )

        mock_route.assert_not_called()
