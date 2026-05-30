"""Advisor rules — ported from ÆLLI dev-advisor."""
from typing import Any, Dict, Optional

BRANCH_DRIFT_THRESHOLD = 20


class FileConflictRule:
    async def check(self, event: Dict, session: Any, ctx: Dict) -> Optional[Dict]:
        if event.get("type") != "prompt":
            return None
        files = event.get("live_modified_files", [])
        repo = event.get("repoRoot", "")
        sid = event.get("sessionId", "")
        branch = event.get("branch", "")
        if not files or not repo:
            return None
        conflicts = ctx["store"].find_conflicts(repo, files, sid)
        conflicts = [c for c in conflicts if c.get("otherBranch") != branch]
        if not conflicts:
            return None
        conflict_files = list({c["file"] for c in conflicts})
        conflict_branches = list({c["otherBranch"] for c in conflicts})
        return {
            "type": "file-conflict",
            "message": f"Branch {', '.join(conflict_branches)} also modified: {', '.join(conflict_files)}."[:500],
            "files": conflict_files,
        }


class BranchDriftRule:
    async def check(self, event: Dict, session: Any, ctx: Dict) -> Optional[Dict]:
        if event.get("type") != "prompt" or session is None:
            return None
        file_events = [
            e for e in session.events
            if e.get("type") in ("file-write", "file-edit")
        ]
        if len(file_events) < BRANCH_DRIFT_THRESHOLD:
            return None
        return {
            "type": "branch-drift",
            "message": f"{len(file_events)} file changes on branch {session.branch} without a restart checkpoint. Consider committing.",
            "files": [],
        }


class SpecDeviationRule:
    async def check(self, event: Dict, session: Any, ctx: Dict) -> Optional[Dict]:
        if event.get("type") != "prompt":
            return None
        files = event.get("live_modified_files", [])
        summary = event.get("prompt_summary", "")
        if not files or not summary:
            return None
        deviating = [f for f in files if f not in summary]
        if not deviating:
            return None
        return {
            "type": "spec-deviation",
            "message": f"Modified files not mentioned in prompt: {', '.join(deviating)}."[:500],
            "files": deviating,
        }


class RulesAdvisor:
    def __init__(self):
        self.rules = [FileConflictRule(), BranchDriftRule(), SpecDeviationRule()]

    async def advise(self, event: Dict, session: Any, ctx: Dict) -> Optional[Dict]:
        for rule in self.rules:
            result = await rule.check(event, session, ctx)
            if result is not None:
                return result
        return None

    async def advise_all(self, event: Dict, session: Any, ctx: Dict) -> list:
        """Run all rules and return every non-None result (not just the first)."""
        results = []
        for rule in self.rules:
            result = await rule.check(event, session, ctx)
            if result is not None:
                results.append(result)
        return results
