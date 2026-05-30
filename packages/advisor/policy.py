"""Invocation policy — maps advisor rule results to severity levels."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

_LEVEL_MAP: Dict[str, str] = {
    "file-conflict": "intervene",
    "branch-drift":  "advise",
    "spec-deviation": "advise",
}


@dataclass
class PolicyDecision:
    level: str    # "advise" | "intervene" | "escalate"
    type: str
    message: str
    reason: str = field(default="")
    question: str = field(default="")


class InvocationPolicy:
    """Maps a list of rule results to a single PolicyDecision (or None for observe)."""

    def decide(self, results: List[Dict]) -> Optional[PolicyDecision]:
        if not results:
            return None  # observe path — no artifact returned

        if len(results) >= 2:
            types = [r.get("type", "") for r in results]
            messages = "; ".join(r.get("message", "") for r in results)
            return PolicyDecision(
                level="escalate",
                type="multi-rule",
                message=messages,
                reason=f"Multiple concurrent risks: {', '.join(types)}.",
                question=(
                    "Multiple risk signals fired simultaneously. "
                    "Should I pause for human review or proceed?"
                ),
            )

        result = results[0]
        rule_type = result.get("type", "")
        return PolicyDecision(
            level=_LEVEL_MAP.get(rule_type, "advise"),
            type=rule_type,
            message=result.get("message", ""),
        )
