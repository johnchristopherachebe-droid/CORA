"""Brain versions and the owner-approval workflow.

A brain version is an immutable snapshot of what CORA's active brain contains:
    {"knowledge": {entry_id: version}, "skills": {}, "config": {}}
Exactly one version is active. Retrieval only sees what the active snapshot pins, so learned (candidate) knowledge has no
effect until the owner approves a proposal that adds it. Code is never changed here: this governs knowledge and settings.

Workflow: create_proposal (draft) -> test_proposal (isolated evaluation, no writes to the active brain) -> pending_review
-> approve (promotes a NEW version, old one kept) or reject. rollback re-activates any earlier version.
"""
import cora_brain_db as db
import cora_evaluation as E

EMPTY = {"knowledge": {}, "skills": {}, "config": {}}
ADDABLE = ("candidate", "verified")


def _version_row(r):
    return {"id": r[0], "label": r[1], "status": r[2], "snapshot": db.loads(r[3], dict(EMPTY)), "parent_id": r[4],
            "proposal_id": r[5], "created_at": r[6], "activated_at": r[7], "note": r[8]}


_VCOLS = "id, label, status, snapshot_json, parent_id, proposal_id, created_at, activated_at, note"


def ensure_baseline(get_connection):
    """Create the empty starting version if the brain has none yet."""
    with get_connection() as conn:
        if conn.execute("SELECT id FROM cora_brain_versions LIMIT 1").fetchone():
            return False
        stamp = db.now()
        conn.execute(f"INSERT INTO cora_brain_versions ({_VCOLS}) VALUES (?, ?, 'active', ?, NULL, NULL, ?, ?, ?)",
                     (db.new_id(), "v0 baseline", db.dumps(EMPTY), stamp, stamp, "Empty starting brain."))
        db.audit(conn, "system", "brain.baseline", "", "baseline created")
    return True


def active(get_connection):
    with get_connection() as conn:
        row = conn.execute(f"SELECT {_VCOLS} FROM cora_brain_versions WHERE status = 'active' ORDER BY activated_at DESC LIMIT 1").fetchone()
    return _version_row(row) if row else None


def list_versions(get_connection):
    with get_connection() as conn:
        rows = conn.execute(f"SELECT {_VCOLS} FROM cora_brain_versions ORDER BY created_at DESC, id").fetchall()
    out = [_version_row(r) for r in rows]
    for v in out:
        v["knowledge_count"] = len(v["snapshot"].get("knowledge", {}))
    return out


def apply_changes(snapshot, changes):
    """Pure function: the snapshot that results from applying `changes` to `snapshot`."""
    new = {"knowledge": dict(snapshot.get("knowledge", {})), "skills": dict(snapshot.get("skills", {})), "config": dict(snapshot.get("config", {}))}
    for kid, version in (changes.get("add") or {}).items():
        new["knowledge"][kid] = int(version)
    for kid, version in (changes.get("update") or {}).items():
        if kid in new["knowledge"]:
            new["knowledge"][kid] = int(version)
    for kid in changes.get("remove") or []:
        new["knowledge"].pop(kid, None)
    return new


def _validate_changes(conn, changes):
    if not isinstance(changes, dict) or not any(changes.get(k) for k in ("add", "update", "remove")):
        raise ValueError("A proposal needs at least one change (add, update or remove).")
    clean = {"add": {}, "update": {}, "remove": list(changes.get("remove") or [])}
    for key in ("add", "update"):
        for kid, version in (changes.get(key) or {}).items():
            row = conn.execute("SELECT status FROM cora_knowledge WHERE id = ?", (kid,)).fetchone()
            if not row:
                raise ValueError(f"Unknown knowledge entry {kid}.")
            if row[0] not in ADDABLE:
                raise ValueError(f"Entry {kid} has status '{row[0]}' and cannot be proposed.")
            if not conn.execute("SELECT 1 FROM cora_knowledge_history WHERE knowledge_id = ? AND version = ?", (kid, int(version))).fetchone():
                raise ValueError(f"Entry {kid} has no version {version}.")
            clean[key][kid] = int(version)
    return clean


def create_proposal(get_connection, title, description, changes, kind="knowledge", actor="cora"):
    with get_connection() as conn:
        clean = _validate_changes(conn, changes)
        pid, stamp = db.new_id(), db.now()
        conn.execute("INSERT INTO cora_proposals (id, title, description, kind, changes_json, status, test_report_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'draft', NULL, ?, ?)",
                     (pid, str(title)[:200], str(description)[:2000], str(kind)[:40], db.dumps(clean), stamp, stamp))
        db.audit(conn, actor, "proposal.create", pid, str(title)[:200])
    return pid


def _proposal(r):
    return {"id": r[0], "title": r[1], "description": r[2], "kind": r[3], "changes": db.loads(r[4], {}), "status": r[5],
            "test_report": db.loads(r[6]), "created_at": r[7], "updated_at": r[8], "decided_at": r[9], "decided_by": r[10], "decision_note": r[11]}


_PCOLS = "id, title, description, kind, changes_json, status, test_report_json, created_at, updated_at, decided_at, decided_by, decision_note"


def get_proposal(get_connection, pid):
    with get_connection() as conn:
        row = conn.execute(f"SELECT {_PCOLS} FROM cora_proposals WHERE id = ?", (pid,)).fetchone()
    return _proposal(row) if row else None


def list_proposals(get_connection, status=None):
    sql, params = f"SELECT {_PCOLS} FROM cora_proposals", ()
    if status:
        sql, params = sql + " WHERE status = ?", (status,)
    with get_connection() as conn:
        return [_proposal(r) for r in conn.execute(sql + " ORDER BY created_at DESC, id", params).fetchall()]


def test_proposal(get_connection, pid, evaluator):
    """Evaluate the active snapshot and the proposed snapshot side by side. Writes only the report to the proposal."""
    proposal = get_proposal(get_connection, pid)
    if not proposal:
        raise ValueError("Unknown proposal.")
    if proposal["status"] not in ("draft", "pending_review"):
        raise ValueError(f"A proposal that is {proposal['status']} cannot be re-tested.")
    current = active(get_connection)
    candidate_snapshot = apply_changes(current["snapshot"], proposal["changes"])
    base, cand = evaluator(current["snapshot"]), evaluator(candidate_snapshot)
    comparison = E.compare(base, cand)
    if not base["metrics"]["questions"]:
        recommendation, why = "insufficient_evidence", "There are no benchmark questions, so this change could not be measured."
    elif comparison["regressions"]:
        recommendation, why = "do_not_approve", f"{len(comparison['regressions'])} benchmark(s) got worse."
    elif comparison["improvements"]:
        recommendation, why = "approve", f"{len(comparison['improvements'])} benchmark(s) improved and none regressed."
    else:
        recommendation, why = "no_measured_change", "The benchmarks show no measurable difference."
    report = {"tested_at": db.now(), "base_version": current["id"], "base": base["metrics"], "candidate": cand["metrics"],
              "regressions": comparison["regressions"], "improvements": comparison["improvements"],
              "mean_score_change": comparison["mean_score_change"], "recommendation": recommendation, "why": why,
              "isolation": "Evaluated on a temporary snapshot; the active brain was not modified."}
    with get_connection() as conn:
        conn.execute("UPDATE cora_proposals SET status = 'pending_review', test_report_json = ?, updated_at = ? WHERE id = ?", (db.dumps(report), db.now(), pid))
        db.audit(conn, "cora", "proposal.test", pid, recommendation)
    return report


def approve(get_connection, pid, approved_by, note="", accept_regressions=False, label=None):
    """Promote a tested proposal to a new active version. The previous version is kept for rollback."""
    approver = (approved_by or "").strip()
    if not approver:
        raise PermissionError("An approver is required.")
    with get_connection() as conn:
        row = conn.execute(f"SELECT {_PCOLS} FROM cora_proposals WHERE id = ?", (pid,)).fetchone()
        if not row:
            raise ValueError("Unknown proposal.")
        proposal = _proposal(row)
        if proposal["status"] != "pending_review" or not proposal["test_report"]:
            raise ValueError("Only a tested proposal awaiting review can be approved.")
        report = proposal["test_report"]
        if int((report.get("base") or {}).get("questions") or 0) < 1 or int((report.get("candidate") or {}).get("questions") or 0) < 1:
            raise ValueError("Approval requires at least one benchmark question and a completed before/after evaluation.")
        if report.get("regressions") and not accept_regressions:
            raise ValueError("This proposal made some benchmarks worse. Approve it only with accept_regressions=True.")
        current = conn.execute(f"SELECT {_VCOLS} FROM cora_brain_versions WHERE status = 'active' ORDER BY activated_at DESC LIMIT 1").fetchone()
        if not current:
            raise ValueError("There is no active brain version.")
        current = _version_row(current)
        if report.get("base_version") != current["id"]:
            raise ValueError("This proposal was tested against an older active version. Re-test it before approval.")
        new_snapshot = apply_changes(current["snapshot"], proposal["changes"])
        count = conn.execute("SELECT COUNT(*) FROM cora_brain_versions").fetchone()[0]
        version_id, stamp = db.new_id(), db.now()
        conn.execute("UPDATE cora_brain_versions SET status = 'archived' WHERE id = ?", (current["id"],))
        conn.execute(f"INSERT INTO cora_brain_versions ({_VCOLS}) VALUES (?, ?, 'active', ?, ?, ?, ?, ?, ?)",
                     (version_id, label or f"v{count} {proposal['title'][:60]}", db.dumps(new_snapshot), current["id"], pid, stamp, stamp, str(note)[:500]))
        for kid in list((proposal["changes"].get("add") or {}).keys()) + list((proposal["changes"].get("update") or {}).keys()):
            conn.execute("UPDATE cora_knowledge SET status = 'verified', updated_at = ? WHERE id = ? AND status = 'candidate'", (stamp, kid))
        conn.execute("UPDATE cora_proposals SET status = 'promoted', decided_at = ?, decided_by = ?, decision_note = ?, updated_at = ? WHERE id = ?", (stamp, approver[:80], str(note)[:500], stamp, pid))
        db.audit(conn, approver, "proposal.approve", pid, f"promoted to {version_id}")
    return version_id


def reject(get_connection, pid, decided_by, note=""):
    decider = (decided_by or "").strip()
    if not decider:
        raise PermissionError("A decision-maker is required.")
    with get_connection() as conn:
        row = conn.execute("SELECT status FROM cora_proposals WHERE id = ?", (pid,)).fetchone()
        if not row:
            raise ValueError("Unknown proposal.")
        if row[0] not in ("draft", "pending_review"):
            raise ValueError(f"A proposal that is {row[0]} cannot be rejected.")
        stamp = db.now()
        conn.execute("UPDATE cora_proposals SET status = 'rejected', decided_at = ?, decided_by = ?, decision_note = ?, updated_at = ? WHERE id = ?", (stamp, decider[:80], str(note)[:500], stamp, pid))
        db.audit(conn, decider, "proposal.reject", pid, str(note)[:200])
    return True


def rollback(get_connection, version_id, decided_by, note=""):
    """Make an earlier version active again. The version being left stays on record."""
    decider = (decided_by or "").strip()
    if not decider:
        raise PermissionError("An approver is required.")
    with get_connection() as conn:
        target = conn.execute("SELECT status FROM cora_brain_versions WHERE id = ?", (version_id,)).fetchone()
        if not target:
            raise ValueError("Unknown brain version.")
        if target[0] == "active":
            raise ValueError("That version is already active.")
        conn.execute("UPDATE cora_brain_versions SET status = 'rolled_back' WHERE status = 'active'")
        conn.execute("UPDATE cora_brain_versions SET status = 'active', activated_at = ? WHERE id = ?", (db.now(), version_id))
        db.audit(conn, decider, "brain.rollback", version_id, str(note)[:200])
    return True
