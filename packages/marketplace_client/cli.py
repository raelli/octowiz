"""octowiz-marketplace CLI — query the IntegraHub Marketplace from the command line.

Subcommands: discover, resolve, compat
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List


def _require_url() -> str:
    url = os.environ.get("INTEGRAHUB_MARKETPLACE_URL", "")
    if not url:
        print(
            "Error: INTEGRAHUB_MARKETPLACE_URL is not set.",
            file=sys.stderr,
        )
        sys.exit(1)
    return url


def cmd_discover(args) -> int:
    _require_url()
    from marketplace_client.manifest import get_manifest
    from marketplace_client.resolver import discover_skills

    try:
        manifest = get_manifest()
        plugins = discover_skills(
            manifest,
            category=getattr(args, "category", None),
            keyword=getattr(args, "keyword", None),
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(plugins, indent=2))
    return 0


def cmd_resolve(args) -> int:
    _require_url()
    from marketplace_client.manifest import get_manifest
    from marketplace_client.resolver import resolve_dependencies

    deps: List[str] = args.deps
    try:
        manifest = get_manifest()
        result = resolve_dependencies(deps, manifest)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output = {
        "resolved": [
            {"name": r.name, "version": r.version, "source": r.source}
            for r in result.resolved
        ],
        "unresolved": result.unresolved,
    }
    print(json.dumps(output, indent=2))
    return 0 if not result.unresolved else 1


def cmd_compat(args) -> int:
    from marketplace_client.resolver import check_version_compatibility

    checks = []
    for pair in args.checks:
        parts = pair.split("@")
        if len(parts) != 3:
            print(
                f"Error: expected format name@required@available, got {pair!r}",
                file=sys.stderr,
            )
            return 1
        name, required, available = parts
        compatible = check_version_compatibility(available=available, required=required)
        checks.append({"name": name, "required": required, "available": available,
                        "compatible": compatible})

    all_ok = all(c["compatible"] for c in checks)
    print(json.dumps(checks, indent=2))
    return 0 if all_ok else 1


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="octowiz-marketplace",
        description="Query the IntegraHub Marketplace for Octowiz.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # discover
    p_discover = sub.add_parser("discover", help="List available plugins")
    p_discover.add_argument("--category", default=None, help="Filter by category")
    p_discover.add_argument("--keyword", default=None, help="Filter by keyword")
    p_discover.set_defaults(func=cmd_discover)

    # resolve
    p_resolve = sub.add_parser("resolve", help="Resolve dependency names to marketplace entries")
    p_resolve.add_argument("deps", nargs="+", help="Dependency names to resolve")
    p_resolve.set_defaults(func=cmd_resolve)

    # compat
    p_compat = sub.add_parser("compat", help="Check version compatibility (name@required@available)")
    p_compat.add_argument("checks", nargs="+", help="Checks in format name@required@available")
    p_compat.set_defaults(func=cmd_compat)

    return parser


def main() -> int:
    parser = _make_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
