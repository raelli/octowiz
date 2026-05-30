"""In-memory session store and conflict index."""
from typing import Dict, List, Optional


class Session:
    def __init__(self, session_id: str, branch: str = ""):
        self.session_id = session_id
        self.branch = branch
        self.events: List[Dict] = []


class ConflictIndex:
    def __init__(self):
        self._idx: Dict[str, Dict[str, set]] = {}  # repoRoot -> file -> {sessionIds}
        self._branches: Dict[str, str] = {}  # sessionId -> branch

    def track(self, session_id: str, branch: str, repo_root: str, files: List[str]):
        self._branches[session_id] = branch
        self.untrack(session_id, repo_root)
        if not files:
            return
        if repo_root not in self._idx:
            self._idx[repo_root] = {}
        for f in files:
            if not f:
                continue
            self._idx[repo_root].setdefault(f, set()).add(session_id)

    def untrack(self, session_id: str, repo_root: str):
        if repo_root not in self._idx:
            return
        for sessions in self._idx[repo_root].values():
            sessions.discard(session_id)

    def find_conflicts(self, repo_root: str, files: List[str], own_session_id: str) -> List[Dict]:
        result = []
        repo_idx = self._idx.get(repo_root, {})
        for f in files:
            for sid in repo_idx.get(f, set()):
                if sid != own_session_id:
                    result.append({
                        "file": f,
                        "otherSessionId": sid,
                        "otherBranch": self._branches.get(sid, ""),
                    })
        return result


class SessionStore:
    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._conflicts = ConflictIndex()

    def get_session(self, session_id: Optional[str]) -> Optional[Session]:
        if not session_id:
            return None
        return self._sessions.get(session_id)

    def record_event(self, event: Dict):
        sid = event.get("sessionId")
        if not sid:
            return
        if sid not in self._sessions:
            self._sessions[sid] = Session(sid, branch=event.get("branch", ""))
        session = self._sessions[sid]
        if event.get("branch"):
            session.branch = event["branch"]
        session.events.append(event)

        files = event.get("live_modified_files", [])
        repo = event.get("repoRoot", "")
        branch = session.branch
        if repo:
            self._conflicts.track(sid, branch, repo, files)

    def find_conflicts(self, repo_root: str, files: List[str], session_id: str) -> List[Dict]:
        return self._conflicts.find_conflicts(repo_root, files, session_id)


store = SessionStore()
