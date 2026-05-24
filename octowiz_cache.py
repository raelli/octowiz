"""
octowiz_cache.py — memory bundle caching for the Octowiz AI coding workflow.

Fetches role-scoped doctrine bundles from LiteLLM memory and caches them
on disk as Markdown files with a manifest for TTL-based invalidation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import httpx


# ---------------------------------------------------------------------------
# MemorySource Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class MemorySource(Protocol):
    def fetch(self, key: str) -> Dict[str, Any]:
        """Fetch one memory entry by key. Raises KeyError on 404."""
        ...


class LiteLLMMemorySource:
    """Concrete MemorySource adapter backed by an httpx.Client."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def fetch(self, key: str) -> Dict[str, Any]:
        """
        GET /v1/memory/{url-encoded-key}.

        On 404: raise KeyError naming the key.
        Returns {"key": key, "value": str, "metadata": dict}.
        """
        encoded_key = urllib.parse.quote(key, safe="")
        url = f"/v1/memory/{encoded_key}"
        response = self._client.get(url)

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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class RoleRegistry:
    """Single source of truth for roles and their LiteLLM memory keys."""

    def __init__(self, entries: Dict[str, List[str]]):
        self._entries = entries

    def has_role(self, role: str) -> bool:
        return role in self._entries

    def get_keys(self, role: str, namespace: str) -> List[str]:
        """Return memory keys for role with {namespace} expanded."""
        if role not in self._entries:
            raise ValueError(f"Unknown role {role!r}. Valid roles: {sorted(self._entries)}")
        return [k.replace("{namespace}", namespace) for k in self._entries[role]]

    def role_names(self) -> List[str]:
        return list(self._entries)

    def __contains__(self, role: str) -> bool:
        return self.has_role(role)

    def __iter__(self):
        return iter(self._entries)


ROLE_REGISTRY = RoleRegistry({
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
    # reserved — not yet wired to a coordinator workflow option
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
})

# Backward-compatibility alias so existing code using ROLE_MEMORY_KEYS still works
ROLE_MEMORY_KEYS = ROLE_REGISTRY._entries

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
    Module-level convenience: delegates to LiteLLMMemorySource(client).fetch(key).

    Kept for backward compatibility with existing callers.
    """
    return LiteLLMMemorySource(client).fetch(key)


def fetch_role_memories(source: MemorySource, role: str, namespace: str) -> List[Dict[str, Any]]:
    """
    Expand {namespace} in keys and fetch each memory in order via *source*.
    Any KeyError propagates immediately (fails the whole bundle).
    """
    if not ROLE_REGISTRY.has_role(role):
        raise ValueError(
            f"Unknown role {role!r}. Valid roles: {sorted(ROLE_REGISTRY)}"
        )
    expanded_keys = ROLE_REGISTRY.get_keys(role, namespace)
    return [source.fetch(key) for key in expanded_keys]


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
# CacheStore
# ---------------------------------------------------------------------------


class CacheStore:
    """Encapsulates all disk I/O and freshness logic for bundled caches."""

    def __init__(self, cache_dir: Path, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._cache_dir = cache_dir
        self._ttl = ttl_seconds

    def _ns_dir(self, namespace: str) -> Path:
        return _namespace_cache_dir(self._cache_dir, namespace)

    def get_fresh(self, role: str, namespace: str) -> Optional[str]:
        """Return cached bundle content if fresh and schema-valid, else None."""
        ns_dir = self._ns_dir(namespace)
        manifest = _read_manifest(ns_dir)
        if manifest is None:
            return None
        if manifest.get("schema_version") != CACHE_SCHEMA_VERSION:
            return None  # schema mismatch — force rebuild
        role_entry = manifest.get("roles", {}).get(role)
        if not role_entry:
            return None
        if not manifest_is_fresh(role_entry, self._ttl):
            return None
        bundle_hash = role_entry.get("bundle_hash", "")
        return _read_bundle(ns_dir, role, bundle_hash)

    def get_stale(self, role: str, namespace: str) -> Optional[str]:
        """Return any cached bundle regardless of freshness, else None."""
        ns_dir = self._ns_dir(namespace)
        manifest = _read_manifest(ns_dir)
        if manifest is None:
            return None
        role_entry = manifest.get("roles", {}).get(role)
        if not role_entry:
            return None
        bundle_hash = role_entry.get("bundle_hash", "")
        return _read_bundle(ns_dir, role, bundle_hash)

    def put(
        self,
        role: str,
        namespace: str,
        content: str,
        memories: List[Dict[str, Any]],
    ) -> None:
        """Write bundle to disk, update manifest, remove old bundle on hash change."""
        ns_dir = self._ns_dir(namespace)
        new_hash = hash_bundle(role, memories)

        # Remove old bundle file if the hash changed
        old_manifest = _read_manifest(ns_dir)
        if old_manifest is not None:
            old_entry = old_manifest.get("roles", {}).get(role)
            if old_entry:
                old_hash = old_entry.get("bundle_hash", "")
                if old_hash and old_hash != new_hash:
                    old_bundle_path = ns_dir / "bundles" / role / f"{old_hash}.md"
                    try:
                        old_bundle_path.unlink()
                    except OSError:
                        pass

        bundle_path = _write_bundle(ns_dir, role, new_hash, content)
        memory_hashes = {m["key"]: hash_memory(m) for m in memories}

        manifest = _read_manifest(ns_dir) or {"namespace": namespace, "roles": {}}
        manifest["namespace"] = namespace
        manifest["updated_at"] = time.time()
        manifest["ttl_seconds"] = self._ttl
        manifest.setdefault("roles", {})[role] = {
            "bundle_hash": new_hash,
            "bundle_path": str(bundle_path.relative_to(ns_dir)),
            "memory_hashes": memory_hashes,
            "updated_at": time.time(),
        }
        _write_manifest(ns_dir, manifest)


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
    if not ROLE_REGISTRY.has_role(role):
        raise ValueError(
            f"Unknown role {role!r}. Valid roles: {sorted(ROLE_REGISTRY)}"
        )
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", namespace):
        raise ValueError(
            f"Invalid namespace {namespace!r}. Use only letters, digits, hyphens, and underscores."
        )

    resolved_dir = Path(cache_dir) if cache_dir is not None else Path(
        os.environ.get("OCTOWIZ_CACHE_DIR", str(DEFAULT_CACHE_DIR))
    )
    store = CacheStore(resolved_dir, ttl_seconds)

    # Step 1: serve from cache if fresh and not forced refresh
    if not refresh:
        cached = store.get_fresh(role, namespace)
        if cached is not None:
            return cached

    # Step 2: Fetch from LiteLLM; fall back to stale cache on failure
    client = None
    try:
        client = get_litellm_client()
        source = LiteLLMMemorySource(client)
        memories = fetch_role_memories(source, role, namespace)
    except Exception as exc:
        stale = store.get_stale(role, namespace)
        if stale is not None:
            print(
                f"WARNING: LiteLLM unavailable ({exc}); serving stale cache for "
                f"role={role!r} namespace={namespace!r}.",
                file=sys.stderr,
            )
            return stale
        raise
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    # Step 3: Build bundle and write to disk
    content = render_bundle(role, memories)
    store.put(role, namespace, content, memories)
    return content


# ---------------------------------------------------------------------------
# cache_status() — public freshness query
# ---------------------------------------------------------------------------


@dataclass
class RoleStatus:
    role: str
    is_fresh: bool
    age_seconds: Optional[float]  # None if not cached
    updated_at: Optional[float]   # None if not cached


def cache_status(
    namespace: str,
    cache_dir: Any = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> List[RoleStatus]:
    """Return freshness status for all roles in the given namespace."""
    resolved_dir = Path(cache_dir or os.environ.get("OCTOWIZ_CACHE_DIR", str(DEFAULT_CACHE_DIR)))
    ns_dir = _namespace_cache_dir(resolved_dir, namespace)
    manifest = _read_manifest(ns_dir)
    results = []
    for role in ROLE_MEMORY_KEYS:
        if manifest is None or role not in manifest.get("roles", {}):
            results.append(RoleStatus(role=role, is_fresh=False, age_seconds=None, updated_at=None))
        else:
            entry = manifest["roles"][role]
            updated_at = entry.get("updated_at")
            age = (time.time() - updated_at) if isinstance(updated_at, (int, float)) else None
            fresh = manifest_is_fresh(entry, ttl_seconds)
            results.append(RoleStatus(role=role, is_fresh=fresh, age_seconds=age, updated_at=updated_at))
    return results


# ---------------------------------------------------------------------------
# build_bundles() — public build/refresh loop
# ---------------------------------------------------------------------------


class FailureKind(Enum):
    MISSING_KEY = auto()   # KeyError: memory key not found in LiteLLM
    NETWORK = auto()       # httpx connectivity / timeout error
    AUTH = auto()          # missing or invalid API key
    UNKNOWN = auto()       # anything else


@dataclass
class BuildFailure:
    role: str
    exception: Exception
    kind: FailureKind

    def __str__(self) -> str:
        return f"{self.role}: [{self.kind.name}] {self.exception}"


@dataclass
class BuildResult:
    built: List[str]
    failed: List[BuildFailure]


def _classify_failure(exc: Exception) -> FailureKind:
    if isinstance(exc, KeyError):
        return FailureKind.MISSING_KEY
    if isinstance(exc, RuntimeError) and "API key" in str(exc):
        return FailureKind.AUTH
    try:
        import httpx as _httpx
        if isinstance(exc, (_httpx.ConnectError, _httpx.TimeoutException,
                             _httpx.NetworkError, _httpx.RemoteProtocolError)):
            return FailureKind.NETWORK
    except ImportError:
        pass
    return FailureKind.UNKNOWN


def build_bundles(
    roles: List[str],
    namespace: str,
    cache_dir: Any = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    refresh: bool = False,
) -> BuildResult:
    """Build (or refresh) bundles for the given roles. Collects all failures."""
    built = []
    failed = []
    for role in roles:
        try:
            get_bundle(role=role, namespace=namespace, cache_dir=cache_dir,
                       ttl_seconds=ttl_seconds, refresh=refresh)
            built.append(role)
        except Exception as exc:
            failed.append(BuildFailure(role=role, exception=exc, kind=_classify_failure(exc)))
    return BuildResult(built=built, failed=failed)
