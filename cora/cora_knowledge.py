"""CORA's own knowledge base (structured, attributed, versioned). Kept separate from personal memories and chat history.

Statuses: candidate (learned, not yet trusted), verified (approved into a brain version), disputed (sources conflict),
quarantined (suspicious content, never used), rejected, superseded (merged into another entry).
Nothing here makes an entry part of the *active brain*: that only happens through cora_brain_versions (owner approval).
Search is lexical (idf-weighted term coverage). Semantic/vector search is a later stage; see limitations.
"""
import hashlib
import math
import re

import cora_brain_db as db
from cora_memory import looks_like_secret

CATEGORIES = ("general", "science", "technology", "mathematics", "history", "geography", "language", "business", "culture")
STATUSES = ("candidate", "verified", "disputed", "quarantined", "rejected", "superseded")
MAX_CONTENT = 4000
NEAR_DUPLICATE = 0.85

_STOP = set("a an the is are was were be been being of to in on at for and or but with by from as that this it its into than then so "
            "do does did you your i me my we our they their what which who whom how when where why not no can could should would will "
            "shall may might have has had about tell please".split())


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def tokens(text: str):
    found = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", (text or "").lower())
    return [_stem(t) for t in found if t not in _STOP and (len(t) > 1 or t.isdigit())]


def normalise(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").lower()))


def content_hash(text: str) -> str:
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()


def jaccard(a, b) -> float:
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a and b else 0.0


def normalise_category(value) -> str:
    value = str(value or "").strip().lower()
    return value if value in CATEGORIES else "general"


def _clamp(value, low=0.0, high=1.0):
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return low


def _add_source(conn, knowledge_id, source_kind, source_ref, provider, acquired_at, note=""):
    existing = conn.execute("SELECT id FROM cora_knowledge_sources WHERE knowledge_id = ? AND source_kind = ? AND source_ref = ? AND COALESCE(provider, '') = ?",
                            (knowledge_id, source_kind, str(source_ref)[:500], provider or "")).fetchone()
    if existing:
        return existing[0]
    source_id = db.new_id()
    conn.execute("INSERT INTO cora_knowledge_sources (id, knowledge_id, source_kind, source_ref, provider, acquired_at, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (source_id, knowledge_id, str(source_kind)[:40], str(source_ref)[:500], provider, acquired_at or db.now(), str(note)[:300]))
    return source_id


def add(get_connection, title, content, category="general", source_kind="unknown", source_ref="", provider=None,
        confidence=0.5, status="candidate", actor="system", reason="created", acquired_at=None, note=""):
    """Add an entry, or corroborate an existing duplicate. Returns {"id", "duplicate", "status"}."""
    content = (content or "").strip()[:MAX_CONTENT]
    if not content:
        raise ValueError("Knowledge content cannot be empty.")
    if looks_like_secret(content):
        raise ValueError("Content looks like a password, key or card number and was refused.")
    if status not in STATUSES:
        raise ValueError("Unknown status.")
    title = (title or content[:80]).strip()[:200]
    category = normalise_category(category)
    confidence = _clamp(confidence)
    digest, toks = content_hash(content), set(tokens(content))
    with get_connection() as conn:
        same = conn.execute("SELECT id, status FROM cora_knowledge WHERE content_hash = ? AND status NOT IN ('rejected', 'superseded')", (digest,)).fetchone()
        duplicate_of = same[0] if same else None
        if not duplicate_of:
            for row_id, row_content in conn.execute("SELECT id, content FROM cora_knowledge WHERE category = ? AND status NOT IN ('rejected', 'superseded')", (category,)).fetchall():
                if jaccard(toks, tokens(row_content)) >= NEAR_DUPLICATE:
                    duplicate_of = row_id
                    break
        if duplicate_of:
            _add_source(conn, duplicate_of, source_kind, source_ref, provider, acquired_at, note or "corroborating source")
            current = conn.execute("SELECT status FROM cora_knowledge WHERE id = ?", (duplicate_of,)).fetchone()
            return {"id": duplicate_of, "duplicate": True, "status": current[0] if current else status}
        knowledge_id, stamp = db.new_id(), db.now()
        conn.execute("INSERT INTO cora_knowledge (id, title, category, content, status, confidence, content_hash, version, superseded_by, created_at, updated_at) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, 1, NULL, ?, ?)", (knowledge_id, title, category, content, status, confidence, digest, stamp, stamp))
        conn.execute("INSERT INTO cora_knowledge_history (knowledge_id, version, title, content, changed_at, changed_by, reason) VALUES (?, 1, ?, ?, ?, ?, ?)",
                     (knowledge_id, title, content, stamp, str(actor)[:80], str(reason)[:200]))
        _add_source(conn, knowledge_id, source_kind, source_ref, provider, acquired_at, note)
        db.audit(conn, actor, "knowledge.add", knowledge_id, f"{status} via {source_kind}")
    return {"id": knowledge_id, "duplicate": False, "status": status}


def _row(r):
    return {"id": r[0], "title": r[1], "category": r[2], "content": r[3], "status": r[4], "confidence": r[5],
            "version": r[6], "superseded_by": r[7], "created_at": r[8], "updated_at": r[9]}


_COLS = "id, title, category, content, status, confidence, version, superseded_by, created_at, updated_at"


def sources_for(get_connection, knowledge_id):
    with get_connection() as conn:
        rows = conn.execute("SELECT source_kind, source_ref, provider, acquired_at, note FROM cora_knowledge_sources WHERE knowledge_id = ? ORDER BY acquired_at", (knowledge_id,)).fetchall()
    return [{"source_kind": r[0], "source_ref": r[1], "provider": r[2], "acquired_at": r[3], "note": r[4]} for r in rows]


def get(get_connection, knowledge_id):
    with get_connection() as conn:
        row = conn.execute(f"SELECT {_COLS} FROM cora_knowledge WHERE id = ?", (knowledge_id,)).fetchone()
    if not row:
        return None
    entry = _row(row)
    entry["sources"] = sources_for(get_connection, knowledge_id)
    return entry


def list_entries(get_connection, status=None, category=None, limit=200):
    sql, params = f"SELECT {_COLS} FROM cora_knowledge", []
    where = []
    if status:
        where.append("status = ?")
        params.append(status)
    if category:
        where.append("category = ?")
        params.append(normalise_category(category))
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY updated_at DESC, id LIMIT ?"
    params.append(max(1, min(int(limit), 1000)))
    with get_connection() as conn:
        return [_row(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def set_status(get_connection, knowledge_id, status, actor="system", reason=""):
    if status not in STATUSES:
        raise ValueError("Unknown status.")
    with get_connection() as conn:
        cur = conn.execute("UPDATE cora_knowledge SET status = ?, updated_at = ? WHERE id = ?", (status, db.now(), knowledge_id))
        if not cur.rowcount:
            return False
        db.audit(conn, actor, "knowledge.status", knowledge_id, f"{status}: {reason}")
    return True


def update(get_connection, knowledge_id, content=None, title=None, actor="owner", reason="edited"):
    """Write a new version of an entry. The active brain stays pinned to its old version until a proposal is approved."""
    with get_connection() as conn:
        row = conn.execute("SELECT title, content, version FROM cora_knowledge WHERE id = ?", (knowledge_id,)).fetchone()
        if not row:
            return None
        new_title = (title if title is not None else row[0]).strip()[:200]
        new_content = (content if content is not None else row[1]).strip()[:MAX_CONTENT]
        if not new_content:
            raise ValueError("Knowledge content cannot be empty.")
        if looks_like_secret(new_content):
            raise ValueError("Content looks like a password, key or card number and was refused.")
        version, stamp = row[2] + 1, db.now()
        conn.execute("UPDATE cora_knowledge SET title = ?, content = ?, content_hash = ?, version = ?, updated_at = ? WHERE id = ?",
                     (new_title, new_content, content_hash(new_content), version, stamp, knowledge_id))
        conn.execute("INSERT INTO cora_knowledge_history (knowledge_id, version, title, content, changed_at, changed_by, reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (knowledge_id, version, new_title, new_content, stamp, str(actor)[:80], str(reason)[:200]))
        db.audit(conn, actor, "knowledge.update", knowledge_id, f"v{version}: {reason}")
    return version


def correct(get_connection, knowledge_id, new_content, actor="owner", note=""):
    """A user correction: a new version, recorded as such. It still needs a brain-version proposal to take effect."""
    return update(get_connection, knowledge_id, content=new_content, actor=actor, reason="owner correction" + (": " + note if note else ""))


def history(get_connection, knowledge_id):
    with get_connection() as conn:
        rows = conn.execute("SELECT version, title, content, changed_at, changed_by, reason FROM cora_knowledge_history WHERE knowledge_id = ? ORDER BY version", (knowledge_id,)).fetchall()
    return [{"version": r[0], "title": r[1], "content": r[2], "changed_at": r[3], "changed_by": r[4], "reason": r[5]} for r in rows]


def entries_at(get_connection, pinned):
    """The entries exactly as they were at the pinned versions ({id: version}). This is what the active brain knows."""
    if not pinned:
        return []
    with get_connection() as conn:
        rows = conn.execute("SELECT h.knowledge_id, h.version, h.title, h.content, k.category, k.confidence, k.status "
                            "FROM cora_knowledge_history h JOIN cora_knowledge k ON k.id = h.knowledge_id").fetchall()
    return [{"id": r[0], "version": r[1], "title": r[2], "content": r[3], "category": r[4], "confidence": r[5], "status": r[6]}
            for r in rows if pinned.get(r[0]) == r[1]]


def search(get_connection, query, limit=5, pinned=None, statuses=("verified",)):
    """Rank entries by idf-weighted coverage of the query's terms (0..1). `pinned` restricts to a brain snapshot;
    without it, heads with one of `statuses` are searched (used for reviewing candidates)."""
    q = list(dict.fromkeys(tokens(query)))
    if not q:
        return []
    if pinned is not None:
        entries = entries_at(get_connection, pinned)
    else:
        marks = ", ".join("?" for _ in statuses)
        with get_connection() as conn:
            rows = conn.execute(f"SELECT id, version, title, content, category, confidence, status FROM cora_knowledge WHERE status IN ({marks})", tuple(statuses)).fetchall()
        entries = [{"id": r[0], "version": r[1], "title": r[2], "content": r[3], "category": r[4], "confidence": r[5], "status": r[6]} for r in rows]
    if not entries:
        return []
    docs = [(set(tokens(e["title"])) | set(tokens(e["content"])), set(tokens(e["title"]))) for e in entries]
    total = len(entries)
    df = {t: sum(1 for d, _ in docs if t in d) for t in q}
    idf = {t: math.log(1 + total / (1 + df[t])) for t in q}
    denominator = sum(idf.values()) or 1.0
    scored = []
    for entry, (doc, title_terms) in zip(entries, docs):
        got = sum(idf[t] * (1.15 if t in title_terms else 1.0) for t in q if t in doc)
        score = min(1.0, got / denominator)
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda pair: (-pair[0], -pair[1]["confidence"], pair[1]["id"]))
    hits = []
    for score, entry in scored[:limit]:
        hit = dict(entry)
        hit["score"] = round(score, 3)
        hit["sources"] = sources_for(get_connection, entry["id"])
        hits.append(hit)
    return hits


def counts(get_connection):
    with get_connection() as conn:
        by_status = dict(conn.execute("SELECT status, COUNT(*) FROM cora_knowledge GROUP BY status").fetchall())
        by_category = dict(conn.execute("SELECT category, COUNT(*) FROM cora_knowledge GROUP BY category").fetchall())
    return {"by_status": {k: int(v) for k, v in by_status.items()}, "by_category": {k: int(v) for k, v in by_category.items()},
            "total": int(sum(by_status.values()))}


def export_all(get_connection):
    """Full backup as plain JSON-able data: entries, every version, and every source."""
    with get_connection() as conn:
        entries = [_row(r) for r in conn.execute(f"SELECT {_COLS} FROM cora_knowledge ORDER BY created_at, id").fetchall()]
        hist = conn.execute("SELECT knowledge_id, version, title, content, changed_at, changed_by, reason FROM cora_knowledge_history ORDER BY knowledge_id, version").fetchall()
        srcs = conn.execute("SELECT knowledge_id, source_kind, source_ref, provider, acquired_at, note FROM cora_knowledge_sources ORDER BY knowledge_id, acquired_at").fetchall()
    return {"format": "cora-knowledge-export", "format_version": 1, "exported_at": db.now(), "entries": entries,
            "history": [dict(zip(("knowledge_id", "version", "title", "content", "changed_at", "changed_by", "reason"), h)) for h in hist],
            "sources": [dict(zip(("knowledge_id", "source_kind", "source_ref", "provider", "acquired_at", "note"), s)) for s in srcs]}
