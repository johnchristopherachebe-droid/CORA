"""Safe code-upgrade proposals: inspect/diff/test/approve; never writes production files."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import difflib, hashlib, json, re, uuid, time

ALLOWED_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".md", ".sql", ".toml", ".txt", ".yml", ".yaml"}
BLOCKED_PARTS = {".git", ".env", "secrets", "credentials", "node_modules", ".vercel", "__pycache__"}

def _safe_relative(path: str) -> Path:
    p = Path(path)
    if p.is_absolute() or not p.parts or any(x in ("..", "") for x in p.parts):
        raise ValueError("Unsafe path")
    if any(part.lower() in BLOCKED_PARTS or part.lower().startswith(".env") for part in p.parts):
        raise ValueError("Protected path")
    if p.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError("File type is not permitted")
    return p

def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

@dataclass
class UpgradeProposal:
    proposal_id: str
    relative_path: str
    base_sha256: str
    proposed_content: str
    diff: str
    created_at: int
    status: str = "pending"
    test_report: dict | None = None

class UpgradeManager:
    def __init__(self, workspace: str | Path, proposal_dir: str | Path):
        self.workspace = Path(workspace).resolve()
        self.proposal_dir = Path(proposal_dir).resolve()
        self.proposal_dir.mkdir(parents=True, exist_ok=True)

    def propose(self, relative_path: str, proposed_content: str) -> UpgradeProposal:
        rel = _safe_relative(relative_path)
        target = (self.workspace / rel).resolve()
        if self.workspace not in target.parents:
            raise ValueError("Path escapes workspace")
        if not target.is_file():
            raise FileNotFoundError("Only existing files can be proposed for modification")
        before = target.read_text(encoding="utf-8")
        diff = "".join(difflib.unified_diff(before.splitlines(True), proposed_content.splitlines(True),
                                             fromfile=f"current/{rel}", tofile=f"proposed/{rel}"))
        item = UpgradeProposal(uuid.uuid4().hex, str(rel), _sha(before), proposed_content, diff, int(time.time()))
        self._save(item)
        return item

    def attach_test_report(self, proposal_id: str, report: dict) -> UpgradeProposal:
        item = self.get(proposal_id)
        if item.status != "pending":
            raise ValueError("Proposal is no longer pending")
        item.test_report = dict(report)
        self._save(item)
        return item

    def approve_and_apply(self, proposal_id: str, *, owner_authenticated: bool,
                          approval_valid: bool, test_report: dict | None = None) -> dict:
        if not owner_authenticated or not approval_valid:
            raise PermissionError("Authenticated owner approval is required")
        item = self.get(proposal_id)
        report = test_report or item.test_report
        if not isinstance(report, dict) or report.get("passed") is not True or not report.get("tests_run"):
            raise ValueError("A passing, non-empty test report is required")
        rel = _safe_relative(item.relative_path)
        target = (self.workspace / rel).resolve()
        if self.workspace not in target.parents or not target.is_file():
            raise ValueError("Target is unavailable")
        current = target.read_text(encoding="utf-8")
        if _sha(current) != item.base_sha256:
            raise RuntimeError("Stale proposal: the target changed after this proposal was created")
        # This manager only applies to an isolated workspace supplied by the host.
        target.write_text(item.proposed_content, encoding="utf-8")
        item.status = "applied_in_isolated_workspace"
        item.test_report = report
        self._save(item)
        return {"proposal_id": item.proposal_id, "status": item.status, "path": str(rel)}

    def reject(self, proposal_id: str, *, owner_authenticated: bool) -> dict:
        if not owner_authenticated:
            raise PermissionError("Authenticated owner approval is required")
        item = self.get(proposal_id)
        item.status = "rejected"
        self._save(item)
        return {"proposal_id": item.proposal_id, "status": item.status}

    def get(self, proposal_id: str) -> UpgradeProposal:
        path = self.proposal_dir / f"{proposal_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return UpgradeProposal(**data)

    def _save(self, item: UpgradeProposal):
        (self.proposal_dir / f"{item.proposal_id}.json").write_text(
            json.dumps(asdict(item), indent=2), encoding="utf-8")
