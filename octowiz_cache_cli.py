"""
octowiz_cache_cli.py — thin argparse CLI over the octowiz_cache module.

Subcommands: get, build, status, refresh, clear
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

import octowiz_cache
from octowiz_cache import (
    DEFAULT_CACHE_DIR,
    DEFAULT_TTL_SECONDS,
    ROLE_MEMORY_KEYS,
    BuildResult,
    RoleStatus,
    build_bundles,
    cache_status,
    get_bundle,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cache_dir(args) -> Path:
    return Path(
        getattr(args, "cache_dir", None)
        or os.getenv("OCTOWIZ_CACHE_DIR", str(octowiz_cache.DEFAULT_CACHE_DIR))
    )


def _ttl(args) -> int:
    return getattr(args, "ttl_seconds", None) or int(
        os.getenv("OCTOWIZ_CACHE_TTL_SECONDS", octowiz_cache.DEFAULT_TTL_SECONDS)
    )


def _format_age(seconds: float) -> str:
    if seconds < 3600:
        return f"{int(seconds) // 60}m ago"
    return f"{int(seconds) // 3600}h ago"


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_get(args) -> int:
    bypass = (
        args.refresh_memory
        or os.getenv("OCTOWIZ_CACHE_BYPASS") == "1"
        or os.getenv("OCTOWIZ_CACHE_REFRESH") == "1"
    )
    try:
        content = get_bundle(
            role=args.role,
            namespace=args.namespace,
            cache_dir=_cache_dir(args),
            ttl_seconds=_ttl(args),
            refresh=bypass,
        )
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    sys.stdout.write(content)
    return 0


def cmd_build(args) -> int:
    roles = list(ROLE_MEMORY_KEYS) if getattr(args, "all", False) else [args.role]
    result = build_bundles(roles=roles, namespace=args.namespace,
                           cache_dir=_cache_dir(args), ttl_seconds=_ttl(args), refresh=False)
    for role in result.built:
        print(f"[octowiz-cache] built: {role}", file=sys.stderr)
    for role, err in result.failed:
        print(f"[octowiz-cache] FAILED: {role} — {err}", file=sys.stderr)
    if result.failed:
        print(f"[octowiz-cache] {len(result.failed)} role(s) failed: " +
              ", ".join(r for r, _ in result.failed), file=sys.stderr)
        return 1
    return 0


def cmd_status(args) -> int:
    statuses = cache_status(
        namespace=args.namespace,
        cache_dir=_cache_dir(args),
        ttl_seconds=_ttl(args),
    )
    for s in statuses:
        if s.age_seconds is None:
            print(f"{s.role:15s} ✗ missing")
        elif s.is_fresh:
            age_str = _format_age(s.age_seconds)
            print(f"{s.role:15s} ✓ fresh ({age_str})")
        else:
            age_str = _format_age(s.age_seconds)
            print(f"{s.role:15s} ✗ stale ({age_str})")
    return 0


def cmd_refresh(args) -> int:
    result = build_bundles(roles=list(ROLE_MEMORY_KEYS), namespace=args.namespace,
                           cache_dir=_cache_dir(args), ttl_seconds=_ttl(args), refresh=True)
    for role in result.built:
        print(f"[octowiz-cache] built: {role}", file=sys.stderr)
    for role, err in result.failed:
        print(f"[octowiz-cache] FAILED: {role} — {err}", file=sys.stderr)
    if result.failed:
        print(f"[octowiz-cache] {len(result.failed)} role(s) failed: " +
              ", ".join(r for r, _ in result.failed), file=sys.stderr)
        return 1
    return 0


def cmd_clear(args) -> int:
    cache_dir = _cache_dir(args)
    if getattr(args, "all_namespaces", False):
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        print(f"[octowiz-cache] cleared entire cache dir: {cache_dir}", file=sys.stderr)
    else:
        ns_path = cache_dir / "namespaces" / args.namespace
        if ns_path.exists():
            shutil.rmtree(ns_path)
        print(
            f"[octowiz-cache] cleared namespace '{args.namespace}': {ns_path}",
            file=sys.stderr,
        )
    return 0


# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------


def _make_parser() -> argparse.ArgumentParser:
    # Parent parser carries common flags so they work after the subcommand too
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--namespace",
        default=os.getenv("OCTOWIZ_NAMESPACE", "allspark"),
        help="Memory namespace (default: $OCTOWIZ_NAMESPACE or 'allspark')",
    )
    common.add_argument(
        "--ttl-seconds",
        type=int,
        dest="ttl_seconds",
        default=None,
        help="Cache TTL in seconds (default: $OCTOWIZ_CACHE_TTL_SECONDS or 3600)",
    )
    common.add_argument(
        "--cache-dir",
        dest="cache_dir",
        default=None,
        help="Cache directory (default: $OCTOWIZ_CACHE_DIR or ~/.cache/octowiz)",
    )

    parser = argparse.ArgumentParser(
        prog="octowiz-cache",
        description="Manage Octowiz doctrine bundle cache.",
        parents=[common],
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # -- get --
    p_get = sub.add_parser("get", parents=[common], help="Fetch a role bundle (from cache or LiteLLM)")
    p_get.add_argument(
        "--role",
        required=True,
        choices=list(ROLE_MEMORY_KEYS),
        help="Role to fetch",
    )
    p_get.add_argument(
        "--refresh-memory",
        action="store_true",
        dest="refresh_memory",
        help="Bypass cache and force a fresh fetch",
    )
    p_get.set_defaults(func=cmd_get)

    # -- build --
    p_build = sub.add_parser("build", parents=[common], help="Build (cache) role bundles")
    build_group = p_build.add_mutually_exclusive_group(required=True)
    build_group.add_argument(
        "--role",
        choices=list(ROLE_MEMORY_KEYS),
        help="Build a specific role",
    )
    build_group.add_argument(
        "--all",
        action="store_true",
        help="Build all roles",
    )
    p_build.set_defaults(func=cmd_build)

    # -- status --
    p_status = sub.add_parser("status", parents=[common], help="Show cache status (no network calls)")
    p_status.set_defaults(func=cmd_status)

    # -- refresh --
    p_refresh = sub.add_parser("refresh", parents=[common], help="Force-rebuild all roles")
    p_refresh.set_defaults(func=cmd_refresh)

    # -- clear --
    p_clear = sub.add_parser("clear", parents=[common], help="Clear cached data")
    p_clear.add_argument(
        "--all-namespaces",
        action="store_true",
        dest="all_namespaces",
        help="Clear entire cache dir (not just the current namespace)",
    )
    p_clear.set_defaults(func=cmd_clear)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = _make_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
