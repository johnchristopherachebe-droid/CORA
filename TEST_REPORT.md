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

## Integrated upgrade verification — 27 November 2026

- `python -m py_compile main.py cora_*.py cora/*.py research_workspace.py` — PASS.
- `tests/test_phase1_modules.py` — PASS.
- `tests/test_phase1_integration.py` — PASS (74 routes discovered).
- `tests/test_brain_foundation.py` — PASS (20 check groups).
- `tests/test_extensions.py` — PASS (5 tests).
- `tests/test_brain_api.py` — PASS.
- `tests/test_integrations_research.py` — PASS (credential redaction, integration readiness metadata, SQLite research persistence and unsafe URL filtering).
- Inline JavaScript syntax checks for `public/index.html` and `public/brain.html` — PASS using Node.js.

Not verified in this environment: live PostgreSQL connectivity, Vercel deployment, real AI provider API calls, Twilio/WhatsApp/email/Smart Home connections, native iOS actions, and a separately installed desktop companion. Those integrations require provider accounts, credentials, platform permissions or a dedicated local application and are not represented as active features.


## Continued build verification — 27 November 2026

- Corrected the actual voice-listener regex and UI copy to recognise “CORA” and “Hey CORA”; tested both phrases and command-prefixed variants in Node.js — PASS.
- Main dashboard pink theme overrides and mobile PWA metadata — PASS (static UI checks).
- PWA manifest JSON and all referenced PNG icons — PASS.
- Research history UI listing, reopening and multi-session tab rendering — PASS (static UI checks); backend persistence tests are covered by `tests/test_integrations_research.py`.
- `tests/test_ui_upgrade.py` — PASS.
- Inline JavaScript syntax checks for `public/index.html` and `public/brain.html` — PASS.

The PWA is an installable web app shell, not a native iOS application. Browser wake phrase support is not an always-on operating-system wake-word service. The phone receptionist, live WhatsApp/email account access, installed desktop companion, native iPhone Shortcuts actions and live smart-home device control remain unimplemented provider/device integrations; the Integrations page is a readiness catalogue, not proof of live connectivity.


## Command-first research update — 27 November 2026

- Added `/web/unified-search`, which concurrently queries general web results, news results and YouTube video results — source-level checks PASS.
- Added URL filtering and strict 11-character YouTube video ID validation before generating privacy-enhanced embed URLs — source-level checks PASS.
- Replaced separate research action buttons with a command-first search field and tabbed Overview, Web, News and Videos result views — static UI checks PASS.
- Search requests phrased in ordinary chat (for example, “search the web for…”, “look up…”, “research…” and “find videos about…”) route directly to unified search — static UI checks PASS.
- Hidden the chat Send button; Enter submits typed requests. Voice and essential stop/session controls remain available.
- `python tests/test_command_first_research.py` — PASS.
- `python tests/test_ui_upgrade.py` — PASS.
- `python tests/test_phase1_integration.py` — PASS.
- `python tests/test_phase1_modules.py` — PASS.
- `python tests/test_brain_foundation.py` — PASS (20 check groups).
- `python tests/test_brain_api.py` — PASS.
- `python tests/test_extensions.py` — PASS (5 tests).
- `python tests/test_integrations_research.py` — PASS.
- Python compilation and inline JavaScript syntax check — PASS.

Live search quality, live YouTube availability and real network behaviour were not verified because this build environment does not have the project's third-party runtime dependencies and live provider credentials configured. Search results depend on the external DuckDuckGo HTML endpoint and may vary by region or provider response.

## Master update continuation — Groq correction and confirmed connectors — 27 November 2026

- Confirmed the existing primary provider integration is **Groq** (`groq` SDK, `GROQ_API_KEY`, `GROQ_MODEL`).
- Added `cora_connectors.py` with an HTTPS-only Home Assistant adapter. State reads are limited; write actions allow only light, switch and scene service calls with entity/domain validation.
- Added official WhatsApp Business Cloud API text sending. International recipient format, message length, API version and credentials are validated.
- Added protected owner-session endpoints for Home Assistant state reads, Home Assistant service actions, WhatsApp sends and action audit retrieval.
- Every external write requires an explicit `confirmed: true` field. A model-generated plan cannot invoke these connectors on its own.
- Added a persistent action audit table. WhatsApp message bodies are not stored and recipient numbers are masked in audit entries.
- Added Integrations dashboard controls for Home Assistant state inspection, reviewed WhatsApp sends and audit history.
- Added connector setup documentation and environment variable for WhatsApp Graph API version.
- Added connector safety tests (5 checks), owner confirmation/audit API tests, and dashboard integration checks.
- Python compilation — PASS.
- `tests/test_phase1_modules.py` — PASS.
- `tests/test_phase1_integration.py` — PASS.
- `tests/test_brain_foundation.py` — PASS (20 check groups).
- `tests/test_brain_api.py` — PASS, including unconfirmed-send rejection and action-audit check.
- `tests/test_extensions.py` — PASS (5 tests).
- `tests/test_integrations_research.py` — PASS.
- `tests/test_ui_upgrade.py` — PASS.
- `tests/test_command_first_research.py` — PASS.
- `tests/test_connectors.py` — PASS (5 checks).
- JavaScript syntax checks for the main dashboard and Brain dashboard — PASS.

- Added Gmail OAuth refresh-token support, recent inbox metadata/snippet retrieval and owner-confirmed email sending. Full message bodies and attachments are not fetched.
- Added signed Twilio inbound voice webhooks with explicit AI identity disclosure, short speech turns, bounded response length and no audio/transcript retention.
- Added Gmail compose/send and inbox review controls to the Brain Integrations dashboard.
- Twilio configuration now requires the account SID, auth token, phone number and a public HTTPS origin; webhook signatures are validated before processing.
- Expanded connector tests to 8 checks, including Gmail message encoding and Twilio signature validation — PASS.
- Updated integration readiness to describe implemented Gmail and Twilio capabilities without claiming credentials are live.
- Python compilation — PASS; main module import and 90 route registrations verified using a local Groq SDK stub because the `groq` package is not installed in this build environment.
- Browser JavaScript syntax checks — PASS.

### External setup and validation still required

Gmail OAuth consent and credentials, Twilio account/number/webhook configuration, WhatsApp Business credentials, Home Assistant HTTPS endpoint/token, production database, and AI provider keys must be supplied by the owner in private deployment settings. Live API delivery and live phone calls were not tested in this workspace. Native iOS Shortcuts actions still require Apple-side setup and permissions. A separately installed and paired desktop companion is not included, so this browser app cannot independently control an unpaired computer. Production Vercel deployment and GitHub pushes were not performed.
