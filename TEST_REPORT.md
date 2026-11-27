# CORA Phase 1 validation report

## What was run
- `python -m py_compile` on `main.py` and the three new modules: PASS.
- `tests/test_phase1_modules.py` (real SQLite, fake AI): memory categories, migration of an old table, duplicate and secret refusal, persona prompt, plan -> act -> verify -> report, unknown tools dropped from plans, error recovery (retry with a changed input), failure -> needs_attention -> resume, sticky cancel and emergency stop, time-budget pause/resume, double-start protection, chat-intent heuristics: PASS.
- `tests/test_phase1_integration.py` (the real `main.py` imported with stand-ins for FastAPI/pydantic and a fake AI): old database upgraded without losing memories, chat memory commands, persona and grouped memory in the chat prompt, multi-step request through `/chat`, task REST handlers, memory REST handlers, `SESSION_SECRET` token signing and rejection of password-signed tokens: PASS.
- Search for the word "Sir" in replies and prompts: only "never call the user 'Sir'" instructions remain.

## Not tested (needs your accounts or real services)
- Real FastAPI HTTP routing and request validation (stand-ins were used, so pydantic length limits were not exercised).
- Real PostgreSQL (the migration uses `ADD COLUMN IF NOT EXISTS` and `RETURNING id`; both are standard but unrun here).
- Real AI providers: the planner and verifier depend on the model returning valid JSON. Weak models may plan poorly; failures fall back to a single "draft" step.
- Live web research, Vercel's 60-second limit under real latency, and the dashboard (not changed in this phase).
