"""Organise and deduplicate learned knowledge.

Only candidate and disputed entries are merged here. Verified entries belong to an approved brain version and are never
changed by consolidation; if a verified entry duplicates a candidate, the candidate is retired instead.
"""
import cora_brain_db as db
import cora_knowledge as K

THRESHOLD = 0.8


def find_groups(get_connection, threshold=THRESHOLD):
    with get_connection() as conn:
        rows = conn.execute("SELECT id, content, status, confidence, created_at, category FROM cora_knowledge WHERE status IN ('candidate', 'disputed', 'verified') ORDER BY created_at, id").fetchall()
    entries = [{"id": r[0], "tokens": set(K.tokens(r[1])), "status": r[2], "confidence": r[3], "created_at": r[4], "category": r[5]} for r in rows]
    parent = {e["id"]: e["id"] for e in entries}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i, a in enumerate(entries):
        for b in entries[i + 1:]:
            if a["category"] == b["category"] and K.jaccard(a["tokens"], b["tokens"]) >= threshold:
                parent[find(a["id"])] = find(b["id"])
    clusters = {}
    for e in entries:
        clusters.setdefault(find(e["id"]), []).append(e)
    return [g for g in clusters.values() if len(g) > 1 and any(e["status"] != "verified" for e in g)]


def consolidate(get_connection, apply=False, actor="cora", threshold=THRESHOLD):
    """Plan (apply=False) or perform (apply=True) merges. Keeper: a verified entry if present, else the most confident, then the oldest."""
    plan = []
    for group in find_groups(get_connection, threshold):
        keeper = sorted(group, key=lambda e: (e["status"] != "verified", -e["confidence"], e["created_at"]))[0]
        retire = [e["id"] for e in group if e["id"] != keeper["id"] and e["status"] != "verified"]
        if retire:
            plan.append({"keeper": keeper["id"], "retire": retire})
    if apply:
        with get_connection() as conn:
            for item in plan:
                boosted = conn.execute("SELECT confidence, status FROM cora_knowledge WHERE id = ?", (item["keeper"],)).fetchone()
                for rid in item["retire"]:
                    for s in conn.execute("SELECT source_kind, source_ref, provider, acquired_at, note FROM cora_knowledge_sources WHERE knowledge_id = ?", (rid,)).fetchall():
                        K._add_source(conn, item["keeper"], s[0], s[1], s[2], s[3], (s[4] or "") + " (merged duplicate)")
                    conn.execute("UPDATE cora_knowledge SET status = 'superseded', superseded_by = ?, updated_at = ? WHERE id = ?", (item["keeper"], db.now(), rid))
                if boosted and boosted[1] != "verified":
                    conn.execute("UPDATE cora_knowledge SET confidence = ?, updated_at = ? WHERE id = ?", (min(0.95, boosted[0] + 0.05 * len(item["retire"])), db.now(), item["keeper"]))
                db.audit(conn, actor, "knowledge.consolidate", item["keeper"], f"retired {len(item['retire'])} duplicate(s)")
    return {"applied": bool(apply), "merges": plan, "entries_retired": sum(len(p["retire"]) for p in plan)}
