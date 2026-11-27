"""Controlled knowledge acquisition from external models.

Pipeline: ask teachers -> sanitise and screen (untrusted) -> compare answers -> optionally check claims against sources ->
store as CANDIDATE knowledge with provenance. Nothing learned here enters the active brain: candidates only become
active through an approved, tested proposal (cora_brain_versions). Only permitted API output is used; no weights, hidden
reasoning or system prompts are requested.
"""
import re
import time

import cora_brain_db as db
import cora_knowledge as K

MAX_ANSWER = 4000
MAX_CLAIMS = 10
_INJECTION = re.compile(r"(ignore (all |any )?(previous|prior|above) (instructions|rules)|disregard (the |your )?(system|previous)|"
                        r"you are now\b|system prompt|reveal your (instructions|prompt)|new instructions\s*:|act as (an? )?(admin|root|developer)|"
                        r"<\s*/?\s*(system|assistant)\s*>|override (your )?(safety|rules|permissions))", re.I)


def sanitize(text):
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text or "")
    return re.sub(r"[ \t]+", " ", text).strip()[:MAX_ANSWER]


def looks_like_injection(text):
    return bool(_INJECTION.search(text or ""))


def split_claims(text):
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [s.strip() for s in sentences if len(K.tokens(s)) >= 4][:MAX_CLAIMS * 2]


def compare_answers(answers):
    """answers: [{provider, text}]. Group matching claims, count which providers support each, and flag numeric conflicts."""
    consensus = []  # each: {text, providers:set, conflicts:[{provider,text}]}
    for answer in answers:
        for claim in split_claims(answer["text"]):
            claim_tokens, claim_numbers = set(K.tokens(claim)), set(re.findall(r"\d+(?:\.\d+)?", claim))
            placed = False
            for group in consensus:
                similarity = K.jaccard(claim_tokens, group["tokens"])
                numbers_differ = bool(claim_numbers and group["numbers"] and claim_numbers != group["numbers"])
                if similarity >= 0.5 and not numbers_differ:
                    group["providers"].add(answer["provider"])
                    placed = True
                    break
                if similarity >= 0.35 and numbers_differ and answer["provider"] not in group["providers"]:
                    group["conflicts"].append({"provider": answer["provider"], "text": claim})
                    placed = True
                    break
            if not placed:
                consensus.append({"text": claim, "tokens": claim_tokens, "numbers": claim_numbers, "providers": {answer["provider"]}, "conflicts": []})
    return consensus


def check_claim(claim, sources_fn, threshold=0.7):
    """Look for support in retrieved sources. Returns {verified: True|False|None, evidence}. None means it could not be checked."""
    if not sources_fn:
        return {"verified": None, "evidence": []}
    try:
        found = sources_fn(claim) or []
    except Exception:
        return {"verified": None, "evidence": []}
    wanted = set(K.tokens(claim))
    support = [{"url": s.get("url", ""), "title": s.get("title", "")} for s in found
               if wanted and len(wanted & set(K.tokens(s.get("text", "")))) / len(wanted) >= threshold]
    return {"verified": bool(support), "evidence": support[:3]}


def learn(get_connection, question, teachers, sources_fn=None, category="general", time_budget=40.0):
    """Ask the teachers, compare, optionally source-check, and store candidates. Returns a report."""
    question = (question or "").strip()[:500]
    if not question:
        raise ValueError("A learning question is required.")
    started, run_id = time.time(), db.new_id()
    with get_connection() as conn:
        conn.execute("INSERT INTO cora_learning_runs (id, question, status, created_at, finished_at, report_json) VALUES (?, ?, 'running', ?, NULL, NULL)", (run_id, question, db.now()))
    answers, errors, flagged = [], [], []
    for teacher in teachers:
        if time.time() - started > time_budget:
            errors.append({"provider": teacher.name, "error": "skipped: time budget used"})
            continue
        reply = teacher.ask(question)
        text = sanitize(reply.get("text", ""))
        bad = looks_like_injection(text)
        with get_connection() as conn:
            conn.execute("INSERT INTO cora_learning_answers (id, run_id, provider, ok, answer, error, latency_ms, flagged, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (db.new_id(), run_id, reply["provider"], int(bool(reply["ok"])), text if reply["ok"] else None, reply.get("error"), reply.get("latency_ms"), int(bad), db.now()))
        if not reply["ok"]:
            errors.append({"provider": reply["provider"], "error": reply.get("error")})
        elif bad:
            flagged.append(reply["provider"])  # kept on record but never used to form knowledge
        else:
            answers.append({"provider": reply["provider"], "text": text})
    report = {"run_id": run_id, "question": question, "providers_asked": len(teachers), "providers_answered": len(answers),
              "errors": errors, "flagged_responses": flagged, "stored": [], "duplicates": 0, "agreement": None, "status": "completed"}
    if not answers:
        report["status"] = "no_usable_answers"
    else:
        groups = compare_answers(answers)
        total = len(answers)
        supported = sum(1 for g in groups if len(g["providers"]) > 1)
        report["agreement"] = round(supported / len(groups), 2) if groups and total > 1 else None
        for group in groups[:MAX_CLAIMS]:
            providers = sorted(group["providers"])
            check = check_claim(group["text"], sources_fn)
            confidence = min(0.95, 0.3 + 0.2 * (len(providers) - 1) + (0.3 if check["verified"] else 0.0))
            status, note = "candidate", ("verified against: " + ", ".join(e["url"] for e in check["evidence"] if e["url"])) if check["verified"] else (
                "not found in the sources checked" if check["verified"] is False else "not checked against sources")
            if group["conflicts"]:
                status, confidence = "disputed", min(confidence, 0.3)
                note = "providers disagree: " + "; ".join(f"{c['provider']}: {c['text'][:120]}" for c in group["conflicts"])
            added = K.add(get_connection, question[:120], group["text"], category=category, source_kind="provider", source_ref=question,
                          provider=",".join(providers), confidence=confidence, status=status, actor="cora", reason="learning run " + run_id, note=note)
            report["duplicates"] += int(added["duplicate"])
            report["stored"].append({"id": added["id"], "status": added["status"], "confidence": round(confidence, 2), "providers": providers,
                                     "verification": "verified" if check["verified"] else ("unverified" if check["verified"] is None else "not_found"),
                                     "duplicate": added["duplicate"], "claim": group["text"][:200]})
        if report["stored"] and all(s["verification"] != "verified" for s in report["stored"]):
            report["note"] = "Nothing was confirmed against sources; every item remains an unverified candidate."
    with get_connection() as conn:
        conn.execute("UPDATE cora_learning_runs SET status = ?, finished_at = ?, report_json = ? WHERE id = ?", (report["status"], db.now(), db.dumps(report), run_id))
        db.audit(conn, "cora", "learning.run", run_id, f"{len(report['stored'])} stored, {len(flagged)} flagged")
    return report


def recent_runs(get_connection, limit=20):
    with get_connection() as conn:
        rows = conn.execute("SELECT id, question, status, created_at, finished_at, report_json FROM cora_learning_runs ORDER BY created_at DESC, id DESC LIMIT ?", (max(1, min(limit, 100)),)).fetchall()
    return [{"id": r[0], "question": r[1], "status": r[2], "created_at": r[3], "finished_at": r[4], "report": db.loads(r[5])} for r in rows]
