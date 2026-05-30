"""Tests for ADR writer — writes ADR entries to LiteLLM Memory."""
import unittest
from unittest.mock import MagicMock, patch
import httpx


class TestWriteAdr(unittest.TestCase):

    def test_memory_key_format(self):
        """write_adr posts to the correct namespaced key."""
        with patch("packages.memory_client.adr.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_httpx.put.return_value = mock_response

            from packages.memory_client.adr import write_adr
            write_adr(
                base_url="http://localhost:4000",
                api_key="sk-test",
                project_id="proj-abc",
                slug="use-packages-layout",
                content="We restructured to packages/ for clean imports.",
                date="2026-05-30",
            )

            call_args = mock_httpx.put.call_args
            url = call_args[0][0]
            self.assertIn("project:proj-abc:octowiz:adr:2026-05-30-use-packages-layout", url)

    def test_raises_on_http_error(self):
        """write_adr propagates HTTP errors to the caller."""
        with patch("packages.memory_client.adr.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock()
            )
            mock_httpx.put.return_value = mock_response
            mock_httpx.HTTPStatusError = httpx.HTTPStatusError

            from packages.memory_client.adr import write_adr
            with self.assertRaises(httpx.HTTPStatusError):
                write_adr(
                    base_url="http://localhost:4000",
                    api_key="sk-test",
                    project_id="proj-abc",
                    slug="test-error",
                    content="test",
                )

    def test_authorization_header_sent(self):
        """write_adr includes the API key as Bearer token."""
        with patch("packages.memory_client.adr.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_httpx.put.return_value = mock_response

            from packages.memory_client.adr import write_adr
            write_adr(
                base_url="http://localhost:4000",
                api_key="sk-test-key",
                project_id="proj-abc",
                slug="test",
                content="content",
            )

            _, kwargs = mock_httpx.put.call_args
            headers = kwargs.get("headers", {})
            self.assertIn("Authorization", headers)
            self.assertEqual(headers["Authorization"], "Bearer sk-test-key")


if __name__ == "__main__":
    unittest.main()
