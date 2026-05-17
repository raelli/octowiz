import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from import_litellm_memories import load_memories, validate_memories, rewrite_namespace


class TestValidateMemories(unittest.TestCase):
    def test_valid_memories_pass(self):
        memories = [{"key": "k1", "value": "v1"}, {"key": "k2", "value": "v2"}]
        validate_memories(memories)  # must not raise or exit

    def test_missing_value_exits_1(self):
        memories = [{"key": "k1"}]
        with self.assertRaises(SystemExit) as ctx:
            validate_memories(memories)
        self.assertEqual(ctx.exception.code, 1)

    def test_missing_key_exits_1(self):
        memories = [{"value": "v1"}]
        with self.assertRaises(SystemExit) as ctx:
            validate_memories(memories)
        self.assertEqual(ctx.exception.code, 1)

    def test_empty_key_exits_1(self):
        memories = [{"key": "", "value": "v1"}]
        with self.assertRaises(SystemExit) as ctx:
            validate_memories(memories)
        self.assertEqual(ctx.exception.code, 1)

    def test_non_string_value_exits_1(self):
        memories = [{"key": "k1", "value": 42}]
        with self.assertRaises(SystemExit) as ctx:
            validate_memories(memories)
        self.assertEqual(ctx.exception.code, 1)


class TestRewriteNamespace(unittest.TestCase):
    def test_rewrites_team_namespace(self):
        memories = [{"key": "team:allspark:playbook:overview", "value": "v"}]
        result = rewrite_namespace(memories, "integrahub")
        self.assertEqual(result[0]["key"], "team:integrahub:playbook:overview")

    def test_rewrites_project_namespace(self):
        memories = [{"key": "project:allspark:config:setup", "value": "v"}]
        result = rewrite_namespace(memories, "myteam")
        self.assertEqual(result[0]["key"], "project:myteam:config:setup")

    def test_does_not_modify_agent_keys(self):
        memories = [{"key": "agent:planner:memory:workflow", "value": "v"}]
        result = rewrite_namespace(memories, "integrahub")
        self.assertEqual(result[0]["key"], "agent:planner:memory:workflow")

    def test_does_not_mutate_original(self):
        memories = [{"key": "team:allspark:test", "value": "v"}]
        rewrite_namespace(memories, "x")
        self.assertEqual(memories[0]["key"], "team:allspark:test")

    def test_rewrites_both_prefixes_in_one_call(self):
        memories = [
            {"key": "team:allspark:playbook:overview", "value": "v1"},
            {"key": "project:allspark:config:setup", "value": "v2"},
            {"key": "agent:planner:memory:workflow", "value": "v3"},
        ]
        result = rewrite_namespace(memories, "acme")
        self.assertEqual(result[0]["key"], "team:acme:playbook:overview")
        self.assertEqual(result[1]["key"], "project:acme:config:setup")
        self.assertEqual(result[2]["key"], "agent:planner:memory:workflow")


if __name__ == "__main__":
    unittest.main()
