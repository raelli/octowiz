"""Invocation policy layer — maps rule results to 4-level severity signals.

Sits between RulesAdvisor and the advise capability handler. Runs ALL rules
(not first-match-wins) and applies the following mapping:

  0 matches  →  observe   (no artifact returned)
  1 match    →  advise    (branch-drift, spec-deviation)
               intervene  (file-conflict)
  2+ matches →  escalate  (compounded risk Octowiz cannot resolve alone)

The escalate level returns a structured question for ÆLLI to resolve; it does
NOT proactively call ÆLLI (that is v2).
"""
from typing import Any, Dict, List, Optional

from .rules import FileConflictRule, BranchDriftRule, SpecDeviationRule

_LEVEL_MAP = {
    "file-conflict": "intervene",
    "branch-drift": "advise",
    "spec-deviation": "advise",
}


class PolicyAdvisor:
    def __init__(self):
        self._rules = [FileConflictRule(), BranchDriftRule(), SpecDeviationRule()]

    async def check(
        self, event: Dict, session: Any, ctx: Dict
    ) -> Optional[Dict]:
        """Run all rules and apply the invocation policy.

        Returns None when level is 'observe' (nothing actionable), or a dict
        artifact with a 'level' field added alongside the rule's keys.
        """
        hits: List[Dict] = []
        for rule in self._rules:
            result = await rule.check(event, session, ctx)
            if result is not None:
                hits.append(result)

        if not hits:
            return None

        if len(hits) >= 2:
            reasons = " / ".join(h["type"] for h in hits)
            files = list({f for h in hits for f in h.get("files", [])})
            return {
                "level": "escalate",
                "type": "multi-rule",
                "reason": f"Multiple risk signals detected: {reasons}.",
                "question": "Should I pause, commit the current work, or continue on this branch?",
                "files": files,
                "message": f"Escalating to ÆLLI: {reasons}.",
            }

        hit = hits[0]
        level = _LEVEL_MAP.get(hit["type"], "advise")
        return {**hit, "level": level}
