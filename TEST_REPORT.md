# CORA integration validation report — 27 November 2026

## Tests run in the build workspace

- Python compilation of `main.py`, root Brain modules, package modules, and test files: PASS.
- `tests/test_phase1_modules.py`: PASS — structured memory, persona, agent plan/act/verify/report, recovery, pause/resume and cancellation checks.
- `tests/test_phase1_integration.py`: PASS — existing API integration harness, database migration, chat/memory/agent routes and signed session checks.
- `tests/test_brain_foundation.py`: PASS — all 20 Brain Foundation check groups, including independent skills, candidate learning, provenance, injection screening, versioned approval, rollback, evaluation and audit.
- `tests/test_extensions.py`: PASS — owner approval primitives, isolated upgrade proposal safeguards, research URL filtering and local model URL checks.
- `tests/test_brain_api.py`: PASS — integrated Brain initialisation, owner-session guard, benchmark-required approval, research source/video separation and route registration.

## What this validates

The Brain Foundation modules are wired into `main.py`; first use applies the Brain database migrations and creates a baseline brain version. The `/brain.html` control centre calls the protected `/brain/*` routes. Existing Phase 1 functionality remains present and its regression checks pass.

## Not validated in this workspace

- A real PostgreSQL database or a live Vercel deployment.
- Live provider API keys, provider quotas, real-time search quality, YouTube result quality, or real network latency.
- Cross-instance persistence of research sessions on Vercel (the current research session store uses ephemeral `/tmp`).
- A trained standalone language model or extraction of private model weights/system prompts (not implemented and not part of this design).
- Production code self-modification or automatic deployment. `upgrade_manager.py` is an isolated-workspace proposal framework only; it is not wired to overwrite the live app.
- Phone, laptop, TV or smart-home control integrations.

Before deploying, back up the production database, configure `CORA_ACCESS_PASSWORD` and a 32+ character `SESSION_SECRET`, add the AI provider keys you intend to use, and test the update on a staging deployment first.
