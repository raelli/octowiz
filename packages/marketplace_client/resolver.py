"""marketplace_client.resolver — dependency resolution, version compatibility,
skill discovery, and artifact lifecycle.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ResolvedEntry:
    """A marketplace plugin entry resolved from a declared dependency."""
    name: str
    version: str
    source: dict
    category: Optional[str] = None
    description: Optional[str] = None


@dataclass
class ResolutionResult:
    """Result of resolve_dependencies()."""
    resolved: List[ResolvedEntry] = field(default_factory=list)
    unresolved: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Dependency resolution
# ---------------------------------------------------------------------------


def resolve_dependencies(dependencies: List[str], manifest: dict) -> ResolutionResult:
    """Resolve plugin names against marketplace manifest.

    Args:
        dependencies: list of plugin names declared in plugin.json
        manifest: parsed marketplace manifest (has "plugins" list)

    Returns:
        ResolutionResult with .resolved (ResolvedEntry list) and
        .unresolved (list of names not found in manifest).
    """
    index = {p["name"]: p for p in manifest.get("plugins", [])}

    resolved: List[ResolvedEntry] = []
    unresolved: List[str] = []

    for dep in dependencies:
        entry = index.get(dep)
        if entry is None:
            unresolved.append(dep)
        else:
            resolved.append(ResolvedEntry(
                name=entry["name"],
                version=entry.get("version", "unknown"),
                source=entry.get("source", {}),
                category=entry.get("category"),
                description=entry.get("description"),
            ))

    return ResolutionResult(resolved=resolved, unresolved=unresolved)


# ---------------------------------------------------------------------------
# Version compatibility
# ---------------------------------------------------------------------------


def _parse_version(v: str) -> tuple:
    """Parse a semver-like string into a comparable tuple."""
    parts = []
    for segment in v.strip().split(".")[:3]:
        try:
            parts.append(int(segment))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def check_version_compatibility(
    available: str,
    required: str,
    strict_major: bool = False,
) -> bool:
    """Check whether *available* version satisfies *required*.

    Simple rules:
    - available >= required (tuple compare) → compatible, unless strict_major
    - strict_major=True: additionally requires available.major == required.major
    """
    avail = _parse_version(available)
    req = _parse_version(required)

    if strict_major and avail[0] != req[0]:
        return False

    return avail >= req


# ---------------------------------------------------------------------------
# Skill discovery
# ---------------------------------------------------------------------------


def discover_skills(
    manifest: dict,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
) -> List[dict]:
    """Return plugins from manifest filtered by category and/or keyword.

    With no filters, returns all plugins.
    """
    plugins = list(manifest.get("plugins", []))

    if category is not None:
        plugins = [p for p in plugins if p.get("category") == category]

    if keyword is not None:
        kw = keyword.lower()
        plugins = [
            p for p in plugins
            if kw in p.get("name", "").lower()
            or kw in p.get("description", "").lower()
            or any(kw in k.lower() for k in p.get("keywords", []))
        ]

    return plugins


# ---------------------------------------------------------------------------
# Lifecycle state machine
# ---------------------------------------------------------------------------


class LifecycleState(str, enum.Enum):
    AVAILABLE = "available"
    INSTALLED = "installed"
    PINNED = "pinned"
    DISABLED = "disabled"


class ArtifactLifecycle:
    """Models the install lifecycle for a marketplace artifact.

    Valid transitions:
      AVAILABLE  → INSTALLED  (install)
      INSTALLED  → PINNED     (pin)
      INSTALLED  → DISABLED   (disable)
      INSTALLED  → AVAILABLE  (rollback)
    """

    def __init__(self, name: str, version: str) -> None:
        self.name = name
        self.version = version
        self.state: LifecycleState = LifecycleState.AVAILABLE

    def install(self) -> None:
        self.state = LifecycleState.INSTALLED

    def pin(self) -> None:
        if self.state != LifecycleState.INSTALLED:
            raise RuntimeError(
                f"Cannot pin '{self.name}': must be INSTALLED first (current: {self.state})"
            )
        self.state = LifecycleState.PINNED

    def disable(self) -> None:
        if self.state not in (LifecycleState.INSTALLED, LifecycleState.PINNED):
            raise RuntimeError(
                f"Cannot disable '{self.name}': must be INSTALLED or PINNED (current: {self.state})"
            )
        self.state = LifecycleState.DISABLED

    def rollback(self) -> None:
        if self.state not in (LifecycleState.INSTALLED, LifecycleState.PINNED, LifecycleState.DISABLED):
            raise RuntimeError(
                f"Cannot rollback '{self.name}': not currently installed (current: {self.state})"
            )
        self.state = LifecycleState.AVAILABLE

    def __repr__(self) -> str:
        return f"ArtifactLifecycle(name={self.name!r}, version={self.version!r}, state={self.state})"
