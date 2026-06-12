"""octowiz.marketplace_info capability — marketplace manifest query, dependency
resolution, skill discovery, and version compatibility checks.

The marketplace source is never hardcoded: all configuration is read from
environment variables at call time.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

import httpx

from a2a import err
from marketplace_client import manifest as _manifest
from marketplace_client.resolver import (
    resolve_dependencies,
    check_version_compatibility,
    discover_skills,
)


async def handle_marketplace_info(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle the octowiz.marketplace_info A2A capability.

    Supported operations (event["operation"]):
      discover   — list/filter plugins from the marketplace manifest
      resolve    — resolve declared dependencies against the manifest
      compat     — check version compatibility for a list of {name, required, available} items
      (default)  — same as discover
    """
    url = os.environ.get("INTEGRAHUB_MARKETPLACE_URL", "")
    if not url:
        return {
            "status": "unavailable",
            "message": "INTEGRAHUB_MARKETPLACE_URL is not configured",
        }

    operation = event.get("operation", "discover")

    loop = asyncio.get_running_loop()

    try:
        if operation == "resolve":
            return await loop.run_in_executor(None, _handle_resolve, event)

        if operation == "compat":
            return _handle_compat(event)

        # Default: "discover"
        return await loop.run_in_executor(None, _handle_discover, event)

    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        return err(str(exc))


# ---------------------------------------------------------------------------
# Operation handlers (synchronous, run in executor)
# ---------------------------------------------------------------------------


def _handle_resolve(event: Dict[str, Any]) -> Dict[str, Any]:
    deps: List[str] = event.get("dependencies", [])
    manifest = _manifest.get_manifest()
    result = resolve_dependencies(deps, manifest)
    return {
        "status": "ok",
        "operation": "resolve",
        "resolved": [
            {
                "name": r.name,
                "version": r.version,
                "source": r.source,
                "category": r.category,
            }
            for r in result.resolved
        ],
        "unresolved": result.unresolved,
    }


def _handle_discover(event: Dict[str, Any]) -> Dict[str, Any]:
    category: Optional[str] = event.get("category")
    keyword: Optional[str] = event.get("keyword")
    manifest = _manifest.get_manifest()
    plugins = discover_skills(manifest, category=category, keyword=keyword)
    return {
        "status": "ok",
        "operation": "discover",
        "plugins": plugins,
    }


def _handle_compat(event: Dict[str, Any]) -> Dict[str, Any]:
    checks = event.get("checks", [])
    if not isinstance(checks, list):
        return err("checks must be a list")
    results = []
    for item in checks:
        if not isinstance(item, dict):
            return err(f"each check must be a dict, got {type(item).__name__}")
        name = item.get("name", "")
        required = item.get("required", "0.0.0")
        available = item.get("available", "0.0.0")
        strict_major = item.get("strict_major", False)
        compatible = check_version_compatibility(
            available=available,
            required=required,
            strict_major=strict_major,
        )
        results.append({
            "name": name,
            "required": required,
            "available": available,
            "compatible": compatible,
        })
    return {
        "status": "ok",
        "operation": "compat",
        "checks": results,
    }
