-- CORA brain foundation: reference copy of migration 1 (generated from cora_brain_db.MIGRATIONS).
-- CORA applies this automatically on start-up and records it in cora_schema_migrations. Portable: PostgreSQL and SQLite.
CREATE TABLE IF NOT EXISTS cora_schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
-- migration 1
CREATE TABLE IF NOT EXISTS cora_knowledge (id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL, confidence DOUBLE PRECISION NOT NULL, content_hash TEXT NOT NULL, version INTEGER NOT NULL, superseded_by TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_cora_knowledge_status ON cora_knowledge (status);
CREATE INDEX IF NOT EXISTS idx_cora_knowledge_hash ON cora_knowledge (content_hash);
CREATE TABLE IF NOT EXISTS cora_knowledge_history (knowledge_id TEXT NOT NULL, version INTEGER NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL, changed_at TEXT NOT NULL, changed_by TEXT NOT NULL, reason TEXT NOT NULL, PRIMARY KEY (knowledge_id, version));
CREATE TABLE IF NOT EXISTS cora_knowledge_sources (id TEXT PRIMARY KEY, knowledge_id TEXT NOT NULL, source_kind TEXT NOT NULL, source_ref TEXT NOT NULL, provider TEXT, acquired_at TEXT NOT NULL, note TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_cora_knowledge_sources_k ON cora_knowledge_sources (knowledge_id);
CREATE TABLE IF NOT EXISTS cora_learning_runs (id TEXT PRIMARY KEY, question TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, finished_at TEXT, report_json TEXT);
CREATE TABLE IF NOT EXISTS cora_learning_answers (id TEXT PRIMARY KEY, run_id TEXT NOT NULL, provider TEXT NOT NULL, ok INTEGER NOT NULL, answer TEXT, error TEXT, latency_ms INTEGER, flagged INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cora_brain_versions (id TEXT PRIMARY KEY, label TEXT NOT NULL, status TEXT NOT NULL, snapshot_json TEXT NOT NULL, parent_id TEXT, proposal_id TEXT, created_at TEXT NOT NULL, activated_at TEXT, note TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cora_proposals (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL, kind TEXT NOT NULL, changes_json TEXT NOT NULL, status TEXT NOT NULL, test_report_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, decided_at TEXT, decided_by TEXT, decision_note TEXT);
CREATE TABLE IF NOT EXISTS cora_eval_questions (id TEXT PRIMARY KEY, question TEXT NOT NULL, reference TEXT NOT NULL, keywords_json TEXT NOT NULL, category TEXT NOT NULL, kind TEXT NOT NULL, active INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cora_eval_runs (id TEXT PRIMARY KEY, label TEXT NOT NULL, version_id TEXT, created_at TEXT NOT NULL, metrics_json TEXT NOT NULL, results_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cora_audit (id TEXT PRIMARY KEY, ts TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, detail TEXT NOT NULL);
