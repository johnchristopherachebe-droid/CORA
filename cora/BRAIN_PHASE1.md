# CORA Independent Brain: Stage 1a (foundation modules)

Status: **new files only. Nothing in `main.py`, the interface or production has been changed, and nothing is deployed.**
Existing Gemini, Groq, research, voice, memory, Builder and agent code is untouched.

## What this stage contains
| File | Role |
|---|---|
| `cora_brain.py` | Coordinator: operating mode, answer, learn, propose/test/approve/reject/rollback, overview for the interface |
| `cora_brain_db.py` | Portable migrations, ids, timestamps, audit log |
| `cora_knowledge.py` | Knowledge base: categories, statuses, provenance, duplicate detection, version history, corrections, search, export |
| `cora_reasoning.py` | Understand, split into steps, retrieve, pick skills, answer, self-check, state uncertainty, explain |
| `cora_skills.py` | Built-in deterministic skills (calculator, date/time); lists stored skills and marks them as needing a model |
| `cora_learning.py` | Ask teachers, screen untrusted text, compare answers, optional source check, store as *candidates* |
| `cora_consolidation.py` | Merge near-duplicate candidates; never touches approved knowledge |
| `cora_evaluation.py` | Benchmarks, scoring, regression detection, improvement opportunities, reports |
| `cora_brain_versions.py` | Brain snapshots, proposals, isolated testing, owner approval, rejection, rollback |
| `cora_model_adapters.py` | Optional teachers: Gemini/Groq/Cerebras/OpenRouter and a self-hosted open-weight model; safe status |
| `migrations/001_brain_foundation.sql` | Reference copy of the schema (applied automatically by `ensure_schema`) |
| `tests/test_brain_foundation.py` | 20 check groups, real SQLite, fake providers |

## How the safety rules are enforced
- **Learned knowledge is inert.** Learning stores *candidates*. The active brain is a version snapshot that pins specific entries; only an approved proposal adds to it.
- **Approval path:** `create_proposal` -> `test_proposal` (evaluates current vs proposed snapshot, writes only a report) -> owner `approve`/`reject`. Approval needs a named approver and a test report, and is blocked if benchmarks regressed unless `accept_regressions=True`. `rollback` re-activates any earlier version; every version is kept.
- **Untrusted input:** provider replies are sanitised and screened for instruction-like text; flagged replies are recorded but never used. Retrieved knowledge is passed to a model only in the *data* part of a prompt.
- **Honesty:** with no provider, CORA answers from skills and approved knowledge, otherwise says she doesn't know. Model answers are labelled external with confidence 0.5 and are never stored automatically.
- **Audit:** every state change writes to `cora_audit`.
- Keys are read from the environment at call time; status output contains only configured yes/no.

## Environment variables (new, all optional)
- `CORA_LOCAL_MODEL_URL`: base URL of an OpenAI-compatible server **you host** (vLLM, Ollama, llama.cpp). Vercel cannot run a model.
- `CORA_LOCAL_MODEL_NAME`, `CORA_LOCAL_MODEL_API_KEY`: model name and key for that server.
- Existing variables (`AI_BRAIN_ORDER`, `*_API_KEY`, `*_MODEL`, `DATABASE_URL`, `CORA_ACCESS_PASSWORD`, `SESSION_SECRET`) are reused unchanged.
- Planned for stage 1b: `CORA_BRAIN_ENABLED` (default off).

## Tests: what ran
`python tests/test_brain_foundation.py` -> **ALL 20 CHECK GROUPS PASSED** (SQLite, Python 3.12). Covers: operation with no providers, calculator safety, secret refusal, learning with agreement/conflict/injection/provider failure, source checking, consolidation, benchmarks and opportunities, proposal test/approve/reject, regression blocking, rollback, task decomposition, model-as-data prompts, restart persistence, export, audit, key non-disclosure.
One real bug was found and fixed by these tests: same-second timestamps made "latest run" ambiguous (now microsecond precision).

**Not tested (not possible in this environment):** PostgreSQL (psycopg not installed), real providers, FastAPI routing and authentication (no endpoints exist yet), the browser interface, Vercel limits.

## Deployment (when you approve)
Not yet applicable: nothing is wired in. Stage 1b adds `main.py` wiring behind `CORA_BRAIN_ENABLED` and `/brain/*` endpoints behind your existing login. Do not deploy before that review.

## Incomplete / limitations
- **Not built yet (stage 1b):** `/brain/*` API, `main.py` wiring, Brain Control Centre in `public/index.html`, API docs, password re-entry on approval.
- **No semantic/vector search.** Search is lexical (idf-weighted term coverage), so paraphrased questions can miss. pgvector is the planned upgrade; it needs a Postgres host that supports it and an embedding source.
- Retrieval loads the active snapshot into memory: fine for hundreds to low thousands of entries, not millions.
- Answers from knowledge are extractive (a stored entry is returned as is); the independent engine does not generate new prose.
- Reasoning rules (intent, splitting) are heuristic and English-only. Complex multi-step work still needs the existing agent and a model.
- Source checking needs a `sources_fn` wired to your research tools; until then learned items stay "unverified candidates".
- Anthropic is not yet a learning teacher (it is only in the main chat router). Knowledge import/restore from an export is not built (export only).
- Concurrent approvals from two browser tabs are not locked; single-owner use is assumed.
- Brain versions cover knowledge and settings. Code changes stay as normal GitHub changes, because a deployed function cannot safely rewrite itself.
