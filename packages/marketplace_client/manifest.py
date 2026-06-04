"""marketplace_client.manifest — fetch and cache the IntegraHub Marketplace manifest.

The marketplace URL is read from INTEGRAHUB_MARKETPLACE_URL at call time.
It is never hardcoded in this module.
"""
from __future__ import annotations

import os
import time
from typing import Dict, List, Optional, Tuple, Any

import httpx

# ---------------------------------------------------------------------------
# Module-level cache: {"manifest": (data, fetched_at_monotonic)}
# ---------------------------------------------------------------------------
_CACHE: Dict[str, Tuple[Any, float]] = {}

_DEFAULT_TTL = 3600  # seconds


def _marketplace_url() -> str:
    url = os.environ.get("INTEGRAHUB_MARKETPLACE_URL", "")
    if not url:
        raise ValueError(
            "INTEGRAHUB_MARKETPLACE_URL is not configured. "
            "Set this env var to the marketplace JSON endpoint."
        )
    return url


def fetch_manifest() -> dict:
    """Fetch the marketplace manifest from INTEGRAHUB_MARKETPLACE_URL.

    Raises ValueError if URL not configured.
    Raises httpx.RequestError / httpx.HTTPStatusError on network failure.
    """
    url = _marketplace_url()
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    try:
        return response.json()
    except ValueError as exc:
        raise ValueError(
            f"Marketplace returned non-JSON response from {url}: {exc}"
        ) from exc


def get_manifest(ttl_seconds: int = _DEFAULT_TTL) -> dict:
    """Return the marketplace manifest, using an in-memory cache.

    Fetches from the network only when the cache is absent or expired.
    """
    now = time.monotonic()
    cached = _CACHE.get("manifest")
    if cached is not None:
        data, fetched_at = cached
        if now - fetched_at < ttl_seconds:
            return data

    data = fetch_manifest()
    _CACHE["manifest"] = (data, now)
    return data


def list_plugins(ttl_seconds: int = _DEFAULT_TTL) -> List[dict]:
    """Return the flat list of plugin entries from the cached manifest."""
    manifest = get_manifest(ttl_seconds=ttl_seconds)
    return list(manifest.get("plugins", []))
