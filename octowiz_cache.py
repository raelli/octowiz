"""
octowiz_cache.py — memory bundle caching for the Octowiz AI coding workflow.

Fetches role-scoped doctrine bundles from LiteLLM memory and caches them
on disk as Markdown files with a manifest for TTL-based invalidation.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROLE_MEMORY_KEYS: Dict[str, List[str]] = {
    "planner": [
        "team:{namespace}:playbook:ai-coding-workflow:overview",
        "team:{namespace}:playbook:ai-coding-workflow:grill-me-alignment",
        "team:{namespace}:playbook:ai-coding-workflow:prd-destination-document",
        "team:{namespace}:playbook:ai-coding-workflow:kanban-tracer-bullets",
        "team:{namespace}:playbook:ai-coding-workflow:skill-sources",
        "agent:planner:memory:ai-coding-workflow",
    ],
    "implementer": [
        "team:{namespace}:playbook:ai-coding-workflow:context-smart-zone",
        "team:{namespace}:playbook:ai-coding-workflow:tdd-feedback-loops",
        "team:{namespace}:playbook:ai-coding-workflow:ralph-loop",
        "team:{namespace}:skills:matt-pocock:ai-engineering",
        "team:{namespace}:skills:obra-superpowers:agent-methodology",
        "agent:implementer:memory:ai-coding-workflow",
    ],
    "reviewer": [
        "team:{namespace}:playbook:ai-coding-workflow:fresh-context-review",
        "team:{namespace}:playbook:ai-coding-workflow:push-pull-standards",
        "team:{namespace}:skills:obra-superpowers:agent-methodology",
        "agent:reviewer:memory:ai-coding-workflow",
    ],
    "qa": [
        "team:{namespace}:playbook:ai-coding-workflow:manual-qa-taste",
        "team:{namespace}:playbook:ai-coding-workflow:frontend-prototypes",
        "agent:qa:memory:ai-coding-workflow",
    ],
    "routing": [
        "team:{namespace}:config:retrieval-contract",
        "team:{namespace}:skills:matt-pocock:ai-engineering",
        "team:{namespace}:skills:obra-superpowers:agent-methodology",
    ],
}

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "octowiz"
DEFAULT_TTL_SECONDS = 3600
CACHE_SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def hash_memory(memory: Dict[str, Any]) -> str:
    """SHA-256 of {key, value, metadata}, json.dumps sort_keys=True."""
    payload = {
        "key": memory.get("key", ""),
        "value": memory.get("value", ""),
        "metadata": memory.get("metadata", {}),
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def hash_bundle(role: str, memories: List[Dict[str, Any]]) -> str:
    """SHA-256 of {role, memory_hashes: [hash_memory(m) for m sorted by key]}."""
    sorted_memories = sorted(memories, key=lambda m: m.get("key", ""))
    payload = {
        "role": role,
        "memory_hashes": [hash_memory(m) for m in sorted_memories],
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_bundle(role: str, memories: List[Dict[str, Any]]) -> str:
    """Markdown bundle. Memories sorted by key. Values passed through as-is."""
    sorted_memories = sorted(memories, key=lambda m: m.get("key", ""))
    lines = [f"# Octowiz Doctrine Bundle: {role}\n"]
    for mem in sorted_memories:
        key = mem.get("key", "")
        value = mem.get("value", "")
        lines.append(f"## {key}\n\n{value}\n\n---\n")
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------


def manifest_is_fresh(manifest: Dict[str, Any], ttl_seconds: int) -> bool:
    """Return True if time.time() - manifest['updated_at'] < ttl_seconds."""
    updated_at = manifest.get("updated_at")
    if not isinstance(updated_at, (int, float)):
        return False
    return time.time() - updated_at < ttl_seconds


# ---------------------------------------------------------------------------
# LiteLLM client
# ---------------------------------------------------------------------------


def get_litellm_client() -> httpx.Client:
    """
    Build and return an httpx.Client configured for LiteLLM.

    Reads LITELLM_BASE_URL (default http://localhost:4000) and
    LITELLM_ADMIN_API_KEY (preferred) or LITELLM_API_KEY (fallback).

    Raises RuntimeError with a helpful message if no key is set.
    """
    base_url = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000").rstrip("/")
    api_key = os.environ.get("LITELLM_ADMIN_API_KEY") or os.environ.get("LITELLM_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No LiteLLM API key found. Set LITELLM_ADMIN_API_KEY (preferred) "
            "or LITELLM_API_KEY in your environment."
        )
    return httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    )


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def fetch_memory(client: httpx.Client, key: str) -> Dict[str, Any]:
    """
    GET /v1/memory/{url-encoded-key}.

    On 404: raise KeyError naming the key.
    Returns {"key": key, "value": str, "metadata": dict}.
    """
    encoded_key = urllib.parse.quote(key, safe="")
    url = f"/v1/memory/{encoded_key}"
    response = client.get(url)

    if response.status_code == 404:
        raise KeyError(f"Memory key not found in LiteLLM: {key!r}")

    response.raise_for_status()
    data = response.json()

    value = data.get("value") or data.get("memory") or ""
    if not isinstance(value, str):
        print(
            f"WARNING: Memory key {key!r} has non-string value, converting to JSON.",
            file=sys.stderr,
        )
        value = json.dumps(value)

    return {
        "key": key,
        "value": value,
        "metadata": data.get("metadata", {}),
    }


def fetch_role_memories(client: httpx.Client, role: str, namespace: str) -> List[Dict[str, Any]]:
    """
    Expand {namespace} in keys and fetch each memory in order.
    Any KeyError propagates immediately (fails the whole bundle).
    """
    if role not in ROLE_MEMORY_KEYS:
        raise ValueError(
            f"Unknown role {role!r}. Valid roles: {sorted(ROLE_MEMORY_KEYS)}"
        )
    raw_keys = ROLE_MEMORY_KEYS.get(role, [])
    expanded_keys = [k.replace("{namespace}", namespace) for k in raw_keys]
    return [fetch_memory(client, key) for key in expanded_keys]


# ---------------------------------------------------------------------------
# Private I/O helpers
# ---------------------------------------------------------------------------


def _namespace_cache_dir(cache_dir: Path, namespace: str) -> Path:
    return cache_dir / "namespaces" / namespace


def _read_manifest(ns_dir: Path) -> Optional[Dict[str, Any]]:
    manifest_path = ns_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_manifest(ns_dir: Path, manifest: Dict[str, Any]) -> None:
    """Write manifest atomically using os.replace()."""
    manifest = {**manifest, "schema_version": CACHE_SCHEMA_VERSION}
    ns_dir.mkdir(parents=True, exist_ok=True)
    target = ns_dir / "manifest.json"
    tmp = target.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    os.replace(tmp, target)


def _read_bundle(ns_dir: Path, role: str, bundle_hash: str) -> Optional[str]:
    bundle_path = ns_dir / "bundles" / role / f"{bundle_hash}.md"
    if not bundle_path.exists():
        return None
    try:
        return bundle_path.read_text(encoding="utf-8")
    except OSError:
        return None


def _write_bundle(ns_dir: Path, role: str, bundle_hash: str, content: str) -> Path:
    """Write bundle atomically using os.replace(). Returns the bundle path."""
    bundle_dir = ns_dir / "bundles" / role
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = bundle_dir / f"{bundle_hash}.md"
    tmp_path = bundle_path.with_suffix(".md.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(str(tmp_path), str(bundle_path))
    return bundle_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_bundle(
    role: str,
    namespace: str,
    cache_dir: Any = None,  # Path | str | None
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    refresh: bool = False,
) -> str:
    """
    Return the doctrine bundle (Markdown string) for *role* and *namespace*.

    Cache flow:
      1. If not refresh: check manifest freshness + bundle file on disk → serve if valid.
      2. Fetch from LiteLLM; if LiteLLM fails and stale cache exists: warn stderr + serve stale.
      3. Build bundle, write atomically, update manifest, return content.
    """
    if role not in ROLE_MEMORY_KEYS:
        raise ValueError(
            f"Unknown role {role!r}. Valid roles: {sorted(ROLE_MEMORY_KEYS)}"
        )
    # Resolve cache directory
    if cache_dir is None:
        cache_dir = Path(os.environ.get("OCTOWIZ_CACHE_DIR", str(DEFAULT_CACHE_DIR)))
    else:
        cache_dir = Path(cache_dir)

    ns_dir = _namespace_cache_dir(cache_dir, namespace)

    # Step 1: serve from cache if fresh and not forced refresh
    if not refresh:
        manifest = _read_manifest(ns_dir)
        if manifest and manifest.get("schema_version") != CACHE_SCHEMA_VERSION:
            manifest = None  # force rebuild — schema changed
        if manifest is not None:
            role_entry = manifest.get("roles", {}).get(role)
            if role_entry and manifest_is_fresh(role_entry, ttl_seconds):
                bundle_hash = role_entry.get("bundle_hash", "")
                cached_content = _read_bundle(ns_dir, role, bundle_hash)
                if cached_content is not None:
                    return cached_content

    # Step 2: Fetch from LiteLLM; fall back to stale cache on failure
    client = get_litellm_client()
    try:
        memories = fetch_role_memories(client, role, namespace)
    except Exception as exc:
        # Attempt stale fallback
        manifest = _read_manifest(ns_dir)
        if manifest is not None:
            role_entry = manifest.get("roles", {}).get(role)
            if role_entry:
                bundle_hash = role_entry.get("bundle_hash", "")
                cached_content = _read_bundle(ns_dir, role, bundle_hash)
                if cached_content is not None:
                    print(
                        f"WARNING: LiteLLM unavailable ({exc}); serving stale cache for "
                        f"role={role!r} namespace={namespace!r}.",
                        file=sys.stderr,
                    )
                    return cached_content
        raise
    finally:
        try:
            client.close()
        except Exception:
            pass

    # Step 3: Build bundle and write to disk
    content = render_bundle(role, memories)
    bundle_hash = hash_bundle(role, memories)

    bundle_path = _write_bundle(ns_dir, role, bundle_hash, content)

    # Build per-memory hash map (keyed by expanded key)
    memory_hashes = {m["key"]: hash_memory(m) for m in memories}

    # Update manifest
    manifest = _read_manifest(ns_dir) or {"namespace": namespace, "roles": {}}
    manifest["namespace"] = namespace
    manifest["updated_at"] = time.time()
    manifest["ttl_seconds"] = ttl_seconds
    manifest.setdefault("roles", {})[role] = {
        "bundle_hash": bundle_hash,
        "bundle_path": str(bundle_path.relative_to(ns_dir)),
        "memory_hashes": memory_hashes,
        "updated_at": time.time(),
    }
    _write_manifest(ns_dir, manifest)

    return content
