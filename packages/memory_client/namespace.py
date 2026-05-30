"""Namespace and project-rules loader — fetches doctrine bundles from LiteLLM Memory."""
from __future__ import annotations

import json
from urllib.parse import quote

import httpx


def load_project_rules(base_url: str, api_key: str, project_id: str) -> dict:
    """Fetch project rules from LiteLLM Memory: project:{id}:octowiz:rules."""
    key = f"project:{project_id}:octowiz:rules"
    return _fetch(base_url, api_key, key)


def load_role_bundle(base_url: str, api_key: str, role: str, namespace: str) -> dict:
    """Fetch a role bundle: team:{namespace}:octowiz:roles:{role}."""
    key = f"team:{namespace}:octowiz:roles:{role}"
    return _fetch(base_url, api_key, key)


def _fetch(base_url: str, api_key: str, key: str) -> dict:
    url = f"{base_url.rstrip('/')}/v1/memory/{quote(key, safe=':')}"
    response = httpx.get(url, headers={"Authorization": f"Bearer {api_key}"})
    response.raise_for_status()
    data = response.json()
    content = data.get("content", "{}")
    if isinstance(content, str):
        return json.loads(content)
    return content
