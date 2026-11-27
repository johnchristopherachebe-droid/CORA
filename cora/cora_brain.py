"""CORA's central intelligence coordinator. Wires the brain modules together and owns the operating mode.

`deps` (supplied by main.py): conn (get_connection), postgres (bool), llm (optional function(system, user) -> text),
teachers (function returning configured teacher objects), sources_fn (optional function(claim) -> [{url,title,text}]).
Independent mode = no model is available; the brain still answers from skills and approved knowledge and says when it can't.
"""
import cora_brain_db as db
import cora_brain_versions as V
import cora_consolidation as C
import cora_evaluation as E
import cora_knowledge as K
import cora_learning as L
import cora_model_adapters as M
import cora_reasoning as R
import cora_skills as S


class Brain:
    def __init__(self, deps):
        self.deps = deps
        self.conn = deps.conn

    # ---- setup
    def init(self):
        db.ensure_schema(self.conn, getattr(self.deps, "postgres", False))
        V.ensure_baseline(self.conn)
        return self

    def _llm(self):
        llm = getattr(self.deps, "llm", None)
        return llm if callable(llm) else None

    def teachers(self):
        fn = getattr(self.deps, "teachers", None)
        return list(fn()) if callable(fn) else []

    def mode(self):
        return "assisted" if (self._llm() or self.teachers()) else "independent"

    # ---- answering
    def _pinned(self, snapshot=None):
        return (snapshot or V.active(self.conn)["snapshot"]).get("knowledge", {})

    def answer(self, message, allow_provider=True):
        ctx = R.make_ctx(self.conn, pinned=self._pinned(), llm=self._llm() if allow_provider else None)
        out = R.reason(message, ctx, allow_provider=allow_provider)
        out["mode"] = self.mode()
        return out

    def independent_answer_fn(self, snapshot):
        """Answer function used by evaluation: the brain alone, pinned to a snapshot, never an external model."""
        ctx = R.make_ctx(self.conn, pinned=self._pinned(snapshot), llm=None)
        return lambda q: R.reason(q, ctx, allow_provider=False)

    # ---- learning and improvement workflow
    def learn(self, question, category="general", teachers=None):
        chosen = teachers if teachers is not None else self.teachers()
        if not chosen:
            return {"status": "no_teachers", "question": question, "message": "No external model is configured, so there is nothing to learn from. Add a provider key or a self-hosted model URL."}
        return L.learn(self.conn, question, chosen, sources_fn=getattr(self.deps, "sources_fn", None), category=category)

    def propose_from_candidates(self, entry_ids, title, description="", actor="cora"):
        changes = {"add": {}}
        for kid in entry_ids:
            entry = K.get(self.conn, kid)
            if not entry:
                raise ValueError(f"Unknown knowledge entry {kid}.")
            changes["add"][kid] = entry["version"]
        return V.create_proposal(self.conn, title, description or "Add reviewed candidate knowledge to the active brain.", changes, actor=actor)

    def evaluator(self):
        return lambda snapshot: E.run_questions(E.list_questions(self.conn), self.independent_answer_fn(snapshot))

    def test_proposal(self, pid):
        return V.test_proposal(self.conn, pid, self.evaluator())

    def approve(self, pid, approved_by, note="", accept_regressions=False):
        return V.approve(self.conn, pid, approved_by, note, accept_regressions)

    def reject(self, pid, decided_by, note=""):
        return V.reject(self.conn, pid, decided_by, note)

    def rollback(self, version_id, decided_by, note=""):
        return V.rollback(self.conn, version_id, decided_by, note)

    def owner_teach(self, title, content, owner, category="general", note=""):
        """The owner adds knowledge directly. It still goes through a proposal, test and approval so the version history is complete."""
        added = K.add(self.conn, title, content, category=category, source_kind="owner", source_ref="owner", confidence=1.0, actor=owner, reason="owner taught")
        entry = K.get(self.conn, added["id"])
        if entry["status"] == "candidate" or entry["status"] == "verified":
            pid = V.create_proposal(self.conn, "Owner-taught: " + title[:80], "Owner-taught knowledge awaiting benchmark testing and explicit approval.", {"add": {added["id"]: entry["version"]}}, kind="owner_edit", actor=owner)
            report = V.test_proposal(self.conn, pid, self.evaluator())
            return {"entry": added, "proposal_id": pid, "version_id": None,
                    "status": "pending_review", "test_report": report,
                    "message": "The knowledge is saved as a candidate. Add at least one benchmark, re-test the proposal, then approve it to activate it."}
        return {"entry": added, "proposal_id": None, "version_id": None}

    def consolidate(self, apply=False):
        return C.consolidate(self.conn, apply=apply)

    def run_evaluation(self, label="manual"):
        current = V.active(self.conn)
        return E.run(self.conn, self.independent_answer_fn(current["snapshot"]), label=label, version_id=current["id"])

    # ---- real status for the interface
    def overview(self):
        current = V.active(self.conn)
        runs = E.recent_runs(self.conn, 1)
        proposals = V.list_proposals(self.conn)
        return {"mode": self.mode(), "active_version": {"id": current["id"], "label": current["label"], "activated_at": current["activated_at"],
                                                        "knowledge_entries": len(current["snapshot"].get("knowledge", {}))},
                "knowledge": K.counts(self.conn), "skills": S.list_skills(self.conn), "providers": M.provider_status(),
                "latest_evaluation": runs[0] if runs else None,
                "pending_proposals": sum(1 for p in proposals if p["status"] == "pending_review"),
                "draft_proposals": sum(1 for p in proposals if p["status"] == "draft"),
                "learning_runs": len(L.recent_runs(self.conn, 100)), "audit_recent": db.recent_audit(self.conn, 10)}
