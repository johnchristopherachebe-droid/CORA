"""CORA evaluation: benchmark questions, scoring, regression detection, improvement opportunities and reports.

Evaluation answers questions with the *independent* brain only (no external model), so a score measures what CORA herself
knows. An honest abstention ("I don't know") scores 0 but is tracked separately from a confident wrong answer, which is
the failure that matters most.
"""
import re

import cora_brain_db as db
import cora_knowledge as K

CORRECT, PARTIAL = 0.7, 0.3
CONFIDENT = 0.6


def add_question(get_connection, question, reference, keywords=None, category="general", kind="fact"):
    question, reference = (question or "").strip(), (reference or "").strip()
    if not question or not reference:
        raise ValueError("A benchmark needs a question and a reference answer.")
    if kind not in ("fact", "calc", "reasoning"):
        raise ValueError("kind must be fact, calc or reasoning.")
    qid = db.new_id()
    with get_connection() as conn:
        conn.execute("INSERT INTO cora_eval_questions (id, question, reference, keywords_json, category, kind, active, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                     (qid, question[:500], reference[:1500], db.dumps([str(k)[:80] for k in (keywords or [])][:12]), str(category)[:40], kind, db.now()))
        db.audit(conn, "owner", "eval.question.add", qid, question[:120])
    return qid


def list_questions(get_connection, active_only=True):
    sql = "SELECT id, question, reference, keywords_json, category, kind, active FROM cora_eval_questions"
    if active_only:
        sql += " WHERE active = 1"
    with get_connection() as conn:
        rows = conn.execute(sql + " ORDER BY created_at, id").fetchall()
    return [{"id": r[0], "question": r[1], "reference": r[2], "keywords": db.loads(r[3], []), "category": r[4], "kind": r[5], "active": bool(r[6])} for r in rows]


def _numbers(text):
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", (text or "").replace(",", ""))]


def score_answer(question, result):
    """Return (score 0..1, outcome). outcome: correct / partial / wrong / abstained."""
    if not result or not result.get("answered"):
        return 0.0, "abstained"
    answer, reference = result.get("answer") or "", question["reference"]
    if question["kind"] == "calc":
        want, got = _numbers(reference), _numbers(answer)
        score = 1.0 if want and got and any(abs(want[0] - g) < 1e-6 for g in got) else 0.0
    elif question["keywords"]:
        have = K.normalise(answer)
        score = sum(1 for k in question["keywords"] if K.normalise(k) in have) / len(question["keywords"])
    else:
        a, r = set(K.tokens(answer)), set(K.tokens(reference))
        if not a or not r:
            score = 0.0
        else:
            precision, recall = len(a & r) / len(a), len(a & r) / len(r)
            score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    outcome = "correct" if score >= CORRECT else ("partial" if score >= PARTIAL else "wrong")
    return round(score, 3), outcome


def _metrics(results):
    n = len(results)
    if not n:
        return {"questions": 0, "mean_score": None, "accuracy": None, "coverage": None, "abstain_rate": None, "confident_wrong_rate": None, "by_category": {}}
    answered = [r for r in results if r["answered"]]
    by_category = {}
    for r in results:
        by_category.setdefault(r["category"], []).append(r["score"])
    return {"questions": n,
            "mean_score": round(sum(r["score"] for r in results) / n, 3),
            "accuracy": round(sum(1 for r in results if r["outcome"] == "correct") / n, 3),
            "coverage": round(len(answered) / n, 3),
            "abstain_rate": round(1 - len(answered) / n, 3),
            "confident_wrong_rate": round(sum(1 for r in answered if r["confident_wrong"]) / n, 3),
            "by_category": {c: round(sum(v) / len(v), 3) for c, v in by_category.items()}}


def run_questions(questions, answer_fn):
    """Answer each question with answer_fn(question_text) -> {answered, answer, confidence}. Nothing is persisted here."""
    results = []
    for q in questions:
        try:
            out = answer_fn(q["question"]) or {}
        except Exception as error:  # a crash is a failed answer, not a crashed evaluation
            out = {"answered": False, "answer": "", "confidence": 0.0, "error": type(error).__name__}
        score, outcome = score_answer(q, out)
        confidence = float(out.get("confidence") or 0.0)
        results.append({"question_id": q["id"], "question": q["question"], "category": q["category"], "score": score, "outcome": outcome,
                        "answered": bool(out.get("answered")), "confidence": round(confidence, 2),
                        "confident_wrong": bool(out.get("answered")) and confidence >= CONFIDENT and score < PARTIAL,
                        "answer": (out.get("answer") or "")[:400]})
    return {"metrics": _metrics(results), "results": results}


def run(get_connection, answer_fn, label="manual", version_id=None):
    """Run every active benchmark and store the run."""
    outcome = run_questions(list_questions(get_connection), answer_fn)
    run_id = db.new_id()
    with get_connection() as conn:
        conn.execute("INSERT INTO cora_eval_runs (id, label, version_id, created_at, metrics_json, results_json) VALUES (?, ?, ?, ?, ?, ?)",
                     (run_id, str(label)[:80], version_id, db.now(), db.dumps(outcome["metrics"]), db.dumps(outcome["results"])))
        db.audit(conn, "cora", "eval.run", run_id, f"{label}: {outcome['metrics'].get('mean_score')}")
    return {"run_id": run_id, **outcome}


def compare(base, candidate, tolerance=0.2):
    """Per-question comparison of two result lists. A regression is a drop larger than `tolerance`, or a correct answer lost."""
    before = {r["question_id"]: r for r in base["results"]}
    regressions, improvements = [], []
    for r in candidate["results"]:
        b = before.get(r["question_id"])
        if not b:
            continue
        delta = round(r["score"] - b["score"], 3)
        item = {"question": r["question"], "before": b["score"], "after": r["score"], "delta": delta}
        if delta < -tolerance or (b["outcome"] == "correct" and r["outcome"] != "correct"):
            regressions.append(item)
        elif delta > tolerance:
            improvements.append(item)
    bm, cm = base["metrics"], candidate["metrics"]
    return {"regressions": regressions, "improvements": improvements,
            "mean_score_change": None if bm["mean_score"] is None or cm["mean_score"] is None else round(cm["mean_score"] - bm["mean_score"], 3)}


def find_opportunities(results, limit=10):
    """Improvement opportunities: questions CORA could not answer or got confidently wrong."""
    gaps = [{"question": r["question"], "category": r["category"], "reason": "confident wrong answer" if r["confident_wrong"] else ("no stored knowledge" if r["outcome"] == "abstained" else "weak answer")}
            for r in results if r["outcome"] in ("abstained", "wrong", "partial")]
    gaps.sort(key=lambda g: g["reason"] != "confident wrong answer")
    return gaps[:limit]


def recent_runs(get_connection, limit=10):
    with get_connection() as conn:
        rows = conn.execute("SELECT id, label, version_id, created_at, metrics_json FROM cora_eval_runs ORDER BY created_at DESC, id DESC LIMIT ?", (max(1, min(limit, 100)),)).fetchall()
    return [{"id": r[0], "label": r[1], "version_id": r[2], "created_at": r[3], "metrics": db.loads(r[4], {})} for r in rows]


def get_run(get_connection, run_id):
    with get_connection() as conn:
        r = conn.execute("SELECT id, label, version_id, created_at, metrics_json, results_json FROM cora_eval_runs WHERE id = ?", (run_id,)).fetchone()
    return None if not r else {"id": r[0], "label": r[1], "version_id": r[2], "created_at": r[3], "metrics": db.loads(r[4], {}), "results": db.loads(r[5], [])}


def improvement_report(get_connection):
    """A plain report built only from stored runs. It says so when there is nothing to report."""
    runs = recent_runs(get_connection, 5)
    questions = list_questions(get_connection)
    report = {"benchmark_questions": len(questions), "runs": runs, "trend": None, "weak_categories": [], "opportunities": [], "notes": []}
    if not questions:
        report["notes"].append("No benchmark questions exist yet, so nothing can be measured.")
    if not runs:
        report["notes"].append("No evaluation has been run yet.")
        return report
    latest = get_run(get_connection, runs[0]["id"])
    report["opportunities"] = find_opportunities(latest["results"])
    report["weak_categories"] = sorted([c for c, s in latest["metrics"].get("by_category", {}).items() if s < 0.5])
    if len(runs) > 1 and runs[0]["metrics"].get("mean_score") is not None and runs[1]["metrics"].get("mean_score") is not None:
        report["trend"] = round(runs[0]["metrics"]["mean_score"] - runs[1]["metrics"]["mean_score"], 3)
    return report
