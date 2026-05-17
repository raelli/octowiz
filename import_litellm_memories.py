#!/usr/bin/env python3
"""
Import prepared agent memories into LiteLLM Proxy /v1/memory.

Usage:
  export LITELLM_BASE_URL="http://localhost:4000"
  export LITELLM_ADMIN_API_KEY="sk-..."
  # Optional fallback if admin key is not set:
  export LITELLM_API_KEY="sk-..."
  python import_litellm_memories.py litellm_agent_memories_matt_pocock_ai_coding.json

Optional:
  --dry-run        Print what would be imported.
  --key-prefix X   Only import memories whose key starts with X.
  --namespace X    Rewrite 'allspark' namespace to X in all memory keys.

The script uses PUT /v1/memory/{key} for idempotent upsert.
"""

import argparse
import json
import os
import sys
import urllib.parse
from typing import Any, Dict, List

try:
    import httpx
except ImportError:
    print("Missing dependency: httpx. Install with: pip install httpx", file=sys.stderr)
    raise SystemExit(2)


def load_memories(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        if path.endswith(".jsonl"):
            return [json.loads(line) for line in f if line.strip()]
        data = json.load(f)
        if isinstance(data, dict) and "memories" in data:
            return data["memories"]
        if isinstance(data, list):
            return data
        raise ValueError("Expected JSON list, JSONL, or object with 'memories' key.")


def validate_memories(memories: List[Dict[str, Any]]) -> None:
    errors = []
    for i, m in enumerate(memories):
        if not isinstance(m.get("key"), str) or not m["key"]:
            errors.append(f"Entry {i}: 'key' must be a non-empty string")
        if not isinstance(m.get("value"), str):
            errors.append(f"Entry {i}: 'value' must be a string")
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)


def rewrite_namespace(memories: List[Dict[str, Any]], namespace: str) -> List[Dict[str, Any]]:
    result = []
    for m in memories:
        m = dict(m)
        m["key"] = (
            m["key"]
            .replace("team:allspark:", f"team:{namespace}:")
            .replace("project:allspark:", f"project:{namespace}:")
        )
        result.append(m)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("memory_file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--key-prefix", default="")
    parser.add_argument(
        "--namespace",
        default="",
        help="Rewrite 'allspark' namespace to this value in all memory keys.",
    )
    args = parser.parse_args()

    base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000").rstrip("/")
    admin_api_key = os.getenv("LITELLM_ADMIN_API_KEY")
    api_key = admin_api_key or os.getenv("LITELLM_API_KEY")

    if not api_key and not args.dry_run:
        print("Set LITELLM_ADMIN_API_KEY (preferred) or LITELLM_API_KEY, or use --dry-run.", file=sys.stderr)
        return 2

    memories = load_memories(args.memory_file)
    validate_memories(memories)
    if args.key_prefix:
        memories = [m for m in memories if m["key"].startswith(args.key_prefix)]
    if args.namespace:
        memories = rewrite_namespace(memories, args.namespace)

    print(f"Preparing to upsert {len(memories)} memories into {base_url}")

    if args.dry_run:
        for m in memories:
            print(f"DRY RUN: {m['key']} ({len(m.get('value', ''))} chars)")
        return 0

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(base_url=base_url, headers=headers, timeout=30.0) as client:
        for m in memories:
            key = m["key"]
            encoded_key = urllib.parse.quote(key, safe="")
            body = {
                "value": m["value"],
                "metadata": m.get("metadata", {}),
            }
            # Admins may add user_id/team_id here if desired:
            # body["team_id"] = "team-abc"
            r = client.put(f"/v1/memory/{encoded_key}", json=body)
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                print(f"ERROR upserting {key}: {e.response.status_code} {e.response.text}", file=sys.stderr)
                return 1
            print(f"OK: {key}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
