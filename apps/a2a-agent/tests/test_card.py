"""Tests for the Octowiz A2A agent card endpoint."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from fastapi.testclient import TestClient

from main import app

EXPECTED_CAPABILITIES = {
    "octowiz.observe",
    "octowiz.plan",
    "octowiz.review",
    "octowiz.dispatch",
    "octowiz.manage_agents",
    "octowiz.run_sandboxed",
    "octowiz.load_memory",
    "octowiz.write_diary",
    "octowiz.escalate_to_aelli",
    "octowiz.marketplace_info",
}


class TestAgentCard(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_agent_card_returns_200(self):
        resp = self.client.get("/a2a/octowiz/.well-known/agent.json")
        self.assertEqual(resp.status_code, 200)

    def test_agent_card_lists_all_10_capabilities(self):
        resp = self.client.get("/a2a/octowiz/.well-known/agent.json")
        card = resp.json()
        skill_ids = {s["id"] for s in card["skills"]}
        self.assertEqual(skill_ids, EXPECTED_CAPABILITIES)

    def test_agent_card_has_required_fields(self):
        resp = self.client.get("/a2a/octowiz/.well-known/agent.json")
        card = resp.json()
        for field in ("name", "version", "description", "url", "skills"):
            self.assertIn(field, card)
