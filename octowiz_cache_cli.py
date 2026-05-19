"""
octowiz_cache_cli.py — thin argparse CLI over the octowiz_cache module.

Subcommands: get, build, status, refresh, clear
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

import octowiz_cache
from octowiz_cache import (
    DEFAULT_CACHE_DIR,
    DEFAULT_TTL_SECONDS,
    ROLE_MEMORY_KEYS,
    _read_manifest,
    get_bundle,
    manifest_is_fresh,
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
    if getattr(args, "all", False):
        roles = list(ROLE_MEMORY_KEYS)
    else:
        roles = [args.role]

    failures: list[tuple[str, str]] = []
    for role in roles:
        try:
            get_bundle(
                role=role,
                namespace=args.namespace,
                cache_dir=_cache_dir(args),
                ttl_seconds=_ttl(args),
                refresh=False,
            )
            print(f"[octowiz-cache] built: {role}", file=sys.stderr)
        except Exception as exc:
            failures.append((role, str(exc)))
            print(f"[octowiz-cache] FAILED: {role} — {exc}", file=sys.stderr)

    if failures:
        print(
            f"[octowiz-cache] {len(failures)} role(s) failed: "
            + ", ".join(r for r, _ in failures),
            file=sys.stderr,
        )
        return 1
    return 0


def cmd_status(args) -> int:
    cache_dir = _cache_dir(args)
    ttl = _ttl(args)
    namespace = args.namespace
    ns_dir = octowiz_cache._namespace_cache_dir(cache_dir, namespace)
    manifest = _read_manifest(ns_dir)

    for role in ROLE_MEMORY_KEYS:
        if manifest is None or role not in manifest.get("roles", {}):
            print(f"{role:15s} ✗ missing")
        else:
            role_entry = manifest["roles"][role]
            age = time.time() - role_entry["updated_at"]
            if age < 3600:
                age_str = f"{int(age) // 60}m ago"
            else:
                age_str = f"{int(age) // 3600}h ago"
            fresh = manifest_is_fresh(role_entry, ttl)
            if fresh:
                print(f"{role:15s} ✓ fresh ({age_str})")
            else:
                print(f"{role:15s} ✗ stale ({age_str})")
    return 0


def cmd_refresh(args) -> int:
    # Force-rebuild all roles (same as build --all)
    failures: list[tuple[str, str]] = []
    for role in ROLE_MEMORY_KEYS:
        try:
            get_bundle(
                role=role,
                namespace=args.namespace,
                cache_dir=_cache_dir(args),
                ttl_seconds=_ttl(args),
                refresh=True,
            )
            print(f"[octowiz-cache] built: {role}", file=sys.stderr)
        except Exception as exc:
            failures.append((role, str(exc)))
            print(f"[octowiz-cache] FAILED: {role} — {exc}", file=sys.stderr)

    if failures:
        print(
            f"[octowiz-cache] {len(failures)} role(s) failed: "
            + ", ".join(r for r, _ in failures),
            file=sys.stderr,
        )
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
