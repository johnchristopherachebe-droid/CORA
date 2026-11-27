"""CORA brain storage helpers: portable migrations, ids, timestamps and the audit log.

No web framework imports. `get_connection` is main.py's context manager; its connections expose
`execute(sql, params)` with `?` placeholders (translated to `%s` on PostgreSQL). All DDL here is portable between
PostgreSQL and SQLite (TEXT / INTEGER / DOUBLE PRECISION only). New tables use text ids generated in Python, so they
do not depend on main.py's `RETURNING id` rewrite, which only covers four older tables.
"""
import json
import uuid
from datetime import datetime, timezone


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def new_id() -> str:
    return uuid.uuid4().hex


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def loads(text, default=None):
    try:
        return json.loads(text) if text else default
    except (TypeError, ValueError):
        return default


MIGRATIONS = [
    (1, [
        "CREATE TABLE IF NOT EXISTS cora_knowledge (id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL, "
        "content TEXT NOT NULL, status TEXT NOT NULL, confidence DOUBLE PRECISION NOT NULL, content_hash TEXT NOT NULL, "
        "version INTEGER NOT NULL, superseded_by TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)",
        "CREATE INDEX IF NOT EXISTS idx_cora_knowledge_status ON cora_knowledge (status)",
        "CREATE INDEX IF NOT EXISTS idx_cora_knowledge_hash ON cora_knowledge (content_hash)",
        "CREATE TABLE IF NOT EXISTS cora_knowledge_history (knowledge_id TEXT NOT NULL, version INTEGER NOT NULL, "
        "title TEXT NOT NULL, content TEXT NOT NULL, changed_at TEXT NOT NULL, changed_by TEXT NOT NULL, "
        "reason TEXT NOT NULL, PRIMARY KEY (knowledge_id, version))",
        "CREATE TABLE IF NOT EXISTS cora_knowledge_sources (id TEXT PRIMARY KEY, knowledge_id TEXT NOT NULL, "
        "source_kind TEXT NOT NULL, source_ref TEXT NOT NULL, provider TEXT, acquired_at TEXT NOT NULL, note TEXT NOT NULL)",
        "CREATE INDEX IF NOT EXISTS idx_cora_knowledge_sources_k ON cora_knowledge_sources (knowledge_id)",
        "CREATE TABLE IF NOT EXISTS cora_learning_runs (id TEXT PRIMARY KEY, question TEXT NOT NULL, status TEXT NOT NULL, "
        "created_at TEXT NOT NULL, finished_at TEXT, report_json TEXT)",
        "CREATE TABLE IF NOT EXISTS cora_learning_answers (id TEXT PRIMARY KEY, run_id TEXT NOT NULL, provider TEXT NOT NULL, "
        "ok INTEGER NOT NULL, answer TEXT, error TEXT, latency_ms INTEGER, flagged INTEGER NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS cora_brain_versions (id TEXT PRIMARY KEY, label TEXT NOT NULL, status TEXT NOT NULL, "
        "snapshot_json TEXT NOT NULL, parent_id TEXT, proposal_id TEXT, created_at TEXT NOT NULL, activated_at TEXT, note TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS cora_proposals (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL, "
        "kind TEXT NOT NULL, changes_json TEXT NOT NULL, status TEXT NOT NULL, test_report_json TEXT, created_at TEXT NOT NULL, "
        "updated_at TEXT NOT NULL, decided_at TEXT, decided_by TEXT, decision_note TEXT)",
        "CREATE TABLE IF NOT EXISTS cora_eval_questions (id TEXT PRIMARY KEY, question TEXT NOT NULL, reference TEXT NOT NULL, "
        "keywords_json TEXT NOT NULL, category TEXT NOT NULL, kind TEXT NOT NULL, active INTEGER NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS cora_eval_runs (id TEXT PRIMARY KEY, label TEXT NOT NULL, version_id TEXT, created_at TEXT NOT NULL, "
        "metrics_json TEXT NOT NULL, results_json TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS cora_audit (id TEXT PRIMARY KEY, ts TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, "
        "target TEXT NOT NULL, detail TEXT NOT NULL)",
    ]),
    (2, [
        # Database-level guard: there can be only one active brain snapshot.
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_cora_one_active_brain ON cora_brain_versions (status) WHERE status = 'active'",
    ]),
]


def ensure_schema(get_connection, postgres: bool = False):
    """Apply any migrations not yet recorded. Safe to run on every start."""
    with get_connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS cora_schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        done = {row[0] for row in conn.execute("SELECT version FROM cora_schema_migrations").fetchall()}
        for version, statements in MIGRATIONS:
            if version in done:
                continue
            for statement in statements:
                conn.execute(statement)
            conn.execute("INSERT INTO cora_schema_migrations (version, applied_at) VALUES (?, ?)", (version, now()))


def audit(conn, actor: str, action: str, target: str = "", detail: str = ""):
    """Append to the audit log using an open connection, so it commits or rolls back with the change it records."""
    conn.execute("INSERT INTO cora_audit (id, ts, actor, action, target, detail) VALUES (?, ?, ?, ?, ?, ?)",
                 (new_id(), now(), str(actor)[:80], str(action)[:80], str(target)[:120], str(detail)[:500]))


def recent_audit(get_connection, limit: int = 50):
    with get_connection() as conn:
        rows = conn.execute("SELECT ts, actor, action, target, detail FROM cora_audit ORDER BY ts DESC, id DESC LIMIT ?",
                            (max(1, min(int(limit), 500)),)).fetchall()
    return [{"ts": r[0], "actor": r[1], "action": r[2], "target": r[3], "detail": r[4]} for r in rows]
