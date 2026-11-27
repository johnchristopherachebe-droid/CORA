# CORA Cloud — Vercel deployment with Automatic AI Brain

This release preserves the Vercel FastAPI backend, dashboard, British/Deep/Calm browser voice, PostgreSQL memory, tasks, cloud Builder and login. It adds an automatic multi-provider AI router.

## What Automatic mode does

CORA checks the provider keys you configure and tries providers in the order in `AI_BRAIN_ORDER`. If a provider returns an error (for example, a rate limit, unavailable model or temporary outage), CORA tries the next configured provider. Provider keys are kept on the server; they are never sent to the dashboard.

**If `AI_BRAIN_ORDER` is not set, only Groq is used.** To get failover, set it, for example `gemini,groq,cerebras,openrouter`. Providers without a key are skipped. Free quotas and model availability vary by provider and can change. Automatic failover does not create unlimited free usage.

### Add provider keys in Vercel

Open **Vercel → CORA project → Settings → Environment Variables**. Add whichever keys you have:

- `GEMINI_API_KEY` — Google AI Studio: https://aistudio.google.com/app/apikey
- `GROQ_API_KEY` — Groq: https://console.groq.com/keys
- `CEREBRAS_API_KEY` — Cerebras: https://cloud.cerebras.ai/
- `OPENROUTER_API_KEY` — OpenRouter: https://openrouter.ai/keys

At least one provider key is required. To get automatic failover, configure two or more providers.

Optional routing settings:

- `AI_BRAIN_ORDER=gemini,groq,cerebras,openrouter`
- `GEMINI_CHAT_MODEL=gemini-2.5-flash`
- `GEMINI_BUILDER_MODEL=gemini-2.5-flash`
- `GEMINI_VISION_MODEL=gemini-2.5-flash`
- `GROQ_MODEL=openai/gpt-oss-120b`
- `GROQ_BUILDER_MODEL=openai/gpt-oss-120b`
- `GROQ_VISION_MODEL=qwen/qwen3.8-27b`
- `CEREBRAS_MODEL=gpt-oss-120b`
- `OPENROUTER_MODEL=openai/gpt-oss-120b:free`

Model IDs are defaults, not guarantees. Check each provider's current model catalogue and your account's access. You can override task-specific models with variables such as `CEREBRAS_BUILDER_MODEL` or `OPENROUTER_VISION_MODEL`.

**Research note:** the existing web-research feature uses Groq's provider-specific browser-search tool. It therefore routes that particular task to Groq only. If no Groq key is configured, that research feature reports that no compatible provider is configured; ordinary chat, document analysis and Builder can use the other providers.

## Deploy or update on Vercel

1. Extract this ZIP.
2. Replace the files in your existing private GitHub repository with these files. Keep the directory structure intact.
3. Do not upload `.env`, `jarvis_memory.db`, database backups or API keys.
4. In Vercel, add provider keys under **Settings → Environment Variables**. Keep your existing `DATABASE_URL` and `CORA_ACCESS_PASSWORD` unchanged, and **add a new `SESSION_SECRET`** (32+ random characters, see `.env.example`).
5. Set `AI_BRAIN_ORDER` to your preferred order (see above).
6. Redeploy the project.
7. Sign in to CORA and open `/ai/status` while logged in to see which providers are configured and their priority (the endpoint never reveals keys).


## Phase 1 upgrade: intelligence foundation

**Personality.** CORA speaks in the first person in natural British English, never calls you "Sir", is honest about what she cannot do yet, and applies this everywhere (chat, research, morning briefing, skills).

**Structured memory.** Memories now have categories: project, preference, decision, person, fact, general. Existing memories are kept (they become "general").
- Chat: `remember project: ...`, `remember that I prefer ...` (category is guessed if you do not give one), `what do you remember`, `what should you remember` (she suggests; you decide), `forget memory 12`.
- API: `GET /memories?category=project`, `POST /memories`, `PATCH /memories/{id}`, `GET /memories/suggest`, `DELETE /memories/{id}`.
- Passwords, API keys and card numbers are refused. Nothing is saved without you asking.

**Plan, act, verify, report.** Ask in plain language, for example *"Research five AI companies, compare their services and prepare a report."* CORA plans up to 8 steps, runs them with her tools, checks each result, tries one different approach if a step fails, and reports honestly.
- Tools: web research (cited), web search, read a public page, recall memory, list/add tasks, save a note, draft text. She cannot send messages, spend money, delete anything or touch a device.
- Verification: tasks and notes are checked by reading them back from the database; research and drafts get a second model check, and are marked "unchecked" if that check is unavailable.
- Safety: the plan is made once from your request only. Text found on web pages or documents is treated as data and can never add steps.
- Say `how's my task going`, `continue my task`, or `stop` in chat. API: `POST /agent/tasks`, `GET /agent/tasks`, `GET /agent/tasks/{id}`, `POST /agent/tasks/{id}/run|resume|cancel`, and `POST /agent/stop-all` (emergency stop).
- Vercel stops a request after about 60 seconds, so a long job pauses and carries on when you say "continue". True background running arrives in Phase 4.

**Security.** Login tokens are signed with `SESSION_SECRET`. Until you set it, the old password-based signing stays active so nothing breaks; `/ai/status` shows `session_secret_configured`. Once you set it, existing sessions end and you sign in again.

**Code layout.** New logic lives in `cora_persona.py`, `cora_memory.py` and `cora_agent.py`. `main.py` is unchanged except for wiring. Splitting the older sections out of `main.py` is still to do.

**Tests.** `python tests/test_phase1_modules.py` and `python tests/test_phase1_integration.py` (see `TEST_REPORT.md` for what they do and do not prove).

## Existing services preserved

- FastAPI cloud API and dashboard in one Vercel project.
- Groq integration retained as one provider.
- British English / deep / calm browser voice UI and CORA / Hey CORA wake-word flow.
- PostgreSQL persistence for chat history, memories, tasks, notes and Builder files.
- Private password login and expiring session token.
- Builder preview/apply/test/fix workflows.
- Document analysis, vision and existing research route.

## Important limitations

- Browser voice depends on the browser and device. iOS may suspend listening when Safari is backgrounded or the phone is locked.
- Vercel functions are request-based, not a permanently running desktop process.
- CORA cannot directly control a laptop that is switched off. Local device control requires a separately running, explicitly paired local agent.
- AI provider quotas, model names, feature support and free tiers can change. A provider may be skipped for a task it does not support.

## Local testing

Install Python 3.12 and dependencies:

```bash
py -m pip install -r requirements.txt
```

Create a private `.env` from `.env.example`, add at least one API key and your database settings, then run:

```bash
py -m uvicorn main:app --reload --port 8001
```

Open `http://127.0.0.1:8001/`.

Do not commit `.env` to GitHub.

## Brain Control Centre (integrated)

Open `/brain.html` after signing in to the main dashboard. It provides the integrated Brain overview, independent-answer mode, source/video research tabs, knowledge review, learning runs, proposal testing/approval, version history/rollback and evaluation.

The Brain API is protected by the same signed CORA session and requires `CORA_ACCESS_PASSWORD` (16+ characters) and `SESSION_SECRET` (32+ characters):

- `GET /brain/overview`, `POST /brain/answer`
- `POST /brain/learn`, `POST /brain/teach`
- `GET /brain/knowledge`, `GET /brain/knowledge/{id}`
- `GET /brain/proposals`, `POST /brain/proposals/{id}/test|approve|reject`
- `GET /brain/versions`, `POST /brain/versions/{id}/rollback`
- `GET|POST /brain/evaluation/questions`, `POST /brain/evaluation/run`
- `GET /brain/audit`, `POST /brain/consolidate/preview|apply`
- `GET|POST /brain/research`, `GET /brain/research/{session_id}`

The Brain Foundation is a versioned knowledge system, not a trained replacement language model. It can use configured providers as teachers, but their responses remain untrusted candidates until reviewed and promoted. Its independent reasoning and benchmark scoring are heuristic/lexical, not equivalent to a frontier model. Research sessions use the configured PostgreSQL database when `DATABASE_URL` is set; local installs use SQLite. Without a cloud database, a Vercel deployment falls back to ephemeral `/tmp` storage and history is not durable across serverless instance replacement. The Research tab lists saved sessions and lets you reopen them; each session separates overview, sources and videos. Video discovery is a YouTube-filtered public search result, not a guaranteed video transcript or quality check.

### Self-upgrade safety

The `upgrade_manager.py` module is included as an isolated-workspace proposal framework. It is deliberately **not connected to a production-code apply endpoint**. CORA can be extended to prepare diffs and run sandboxed tests, but production code must not be overwritten by a model response or by a client-supplied `approved=true` flag. This release does not claim autonomous self-modification or deployment.

### Tests

Run from the project root:

```bash
python -m py_compile main.py cora_*.py research_workspace.py
python tests/test_phase1_modules.py
python tests/test_phase1_integration.py
python tests/test_brain_foundation.py
python tests/test_extensions.py
python tests/test_brain_api.py
```


## Integrated upgrade additions (November 2026)

- **Voice wake phrase:** the browser voice standby now activates on “CORA” (and accepts “Hey CORA”). Listening remains opt-in; browser/device support and microphone permission are required.
- **First-person UI copy:** user-facing dashboard responses and confirmation prompts no longer address the user as “Sir”; CORA's visible status copy uses first-person language.
- **Research persistence:** research sessions use the configured PostgreSQL database when `DATABASE_URL` is present. Local installs continue to use a local SQLite file. A Vercel deployment without `DATABASE_URL` still falls back to ephemeral `/tmp` storage and is not durable.
- **Integration readiness centre:** `/brain.html` now includes an Integrations tab and the authenticated `GET /integrations/status` endpoint. It reports setup requirements without exposing secrets. Telephony, WhatsApp, email, smart-home, desktop and native iPhone entries are readiness scaffolds only; they are not live integrations in this release.
- **Security:** readiness reporting never returns credential values. Existing approval boundaries for Builder actions and brain knowledge changes remain in place.

Optional integration environment-variable names are listed in `.env.example`. Adding credentials alone does not activate an integration or prove that a provider connection works. Do not add secrets to source control.

### Tests added

Run `python tests/test_integrations_research.py` to check credential redaction, readiness status, research-session persistence across workspace restart, and filtering of unsafe source URLs.


## Mobile app shell and CORA voice wake phrase

The main dashboard now uses CORA's dark pink visual identity and includes a Progressive Web App manifest, icons and a conservative service worker for the static app shell. On supported browsers, use the browser's install/add-to-home-screen option. On iPhone, use Safari's Share → Add to Home Screen. This does not grant native iOS access to messages, contacts, calendar, microphone in the background, or other private app data.

Voice standby is opt-in. With microphone permission and a supported browser, the listener recognises “CORA” and “Hey CORA” to begin a session. Browser speech recognition is not a dedicated offline wake-word engine and may stop when the browser is backgrounded or the device is locked. The user can stop the session from the dashboard.


## Command-first research workspace

CORA can now start a combined search directly from ordinary chat text or the search field. Phrases such as “search the web for…”, “look up…”, “research…”, “google…” and “find videos about…” are routed to a unified search endpoint without requiring a separate Search or Research button. The endpoint requests web pages, news and YouTube results concurrently. CORA presents them in Overview, Web, News and Videos tabs; supported YouTube links are embedded using the privacy-enhanced youtube-nocookie player, with an external link retained.

The main chat form can be submitted by pressing Enter, and the separate search action buttons are removed from the research panel. Essential controls remain for sign-in, voice permissions/session management and stopping speech. This is an in-app tabbed research workspace; it does not silently open uncontrolled browser tabs or bypass browser popup protections.

Run `python tests/test_command_first_research.py` for static checks covering the concurrent endpoint wiring, automatic search intent routing, tabbed result views and video embedding.

## Owner-confirmed connectors and action audit

The latest update adds two live, explicitly confirmed connector adapters:

- **WhatsApp Business Cloud API:** `POST /connectors/whatsapp/send` sends a text message only when the authenticated owner supplies `confirmed: true`. Configure `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, and optionally `WHATSAPP_GRAPH_API_VERSION`.
- **Home Assistant:** `GET /connectors/home-assistant/states` reads a limited list of entity states. `POST /connectors/home-assistant/service` supports only `light`, `switch`, and `scene` services on matching entity IDs, and requires `confirmed: true`. Configure `HOME_ASSISTANT_URL` (HTTPS) and `HOME_ASSISTANT_TOKEN`.
- **Action audit:** `GET /operations/audit` shows recent connector actions. WhatsApp message bodies are deliberately not stored; phone numbers are masked in the audit.

These endpoints require an authenticated CORA owner session, including local deployments. A model response or natural-language plan cannot trigger these external actions by itself. Each action needs an explicit owner confirmation. Credentials must be stored in deployment environment variables, never in source code or chat. The integration status endpoint reports configuration, not verified connectivity.

## Provider naming

CORA uses **Groq** (`GROQ_API_KEY`, `GROQ_MODEL`) and Gemini. The provider router, SDK import and documentation consistently use Groq.

## Remaining external setup

Twilio receptionist webhooks, email OAuth mailbox operations, native iOS Shortcuts actions, and a separately paired desktop companion still require additional provider-specific implementation and/or installation. The web app cannot independently access private iPhone data or control a desktop that has not installed and paired a local companion.


## Gmail and Twilio receptionist connectors

### Gmail

Configure `EMAIL_OAUTH_CLIENT_ID`, `EMAIL_OAUTH_CLIENT_SECRET`, and `EMAIL_OAUTH_REFRESH_TOKEN` from a Google OAuth client authorised by the mailbox owner. Grant only the Gmail scopes required for the selected operations (`gmail.readonly` for recent inbox metadata and `gmail.send` for sending). The refresh token must be stored in private environment settings, never committed.

- `GET /connectors/email/recent?limit=10` returns sender, subject, date, unread state and a short provider snippet. It does not fetch full message bodies or attachments.
- `POST /connectors/email/send` requires an authenticated owner session and JSON `{"to":"person@example.com","subject":"...","body":"...","confirmed":true}`. Without `confirmed: true`, it returns HTTP 428.

### Twilio AI receptionist

Configure `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, and `TWILIO_WEBHOOK_BASE_URL` (the public HTTPS origin, without a trailing slash). Set the Twilio phone number's Voice webhook to `POST https://your-domain/webhooks/twilio/voice`. CORA validates `X-Twilio-Signature` on both webhook routes. The first message clearly identifies CORA as an AI receptionist; speech turns are limited, responses are short, and call audio/transcripts are not retained. The flow does not make bookings, send messages, or perform transactions. It is a basic conversational receptionist, not a replacement for a staffed emergency or support line.

Twilio webhook signatures are validated against the configured public URL. If the public hostname or path differs from `TWILIO_WEBHOOK_BASE_URL`, the provider request is rejected. Test with a Twilio test number before forwarding a production number. Calls and speech processing may incur provider charges.

### What still needs external setup

The code does not grant CORA native iOS permissions or remote desktop control. iPhone actions still require Apple Shortcuts and user-granted permissions. Desktop control requires a separately installed and paired local companion; no always-on remote desktop daemon is included. No external service can be live-tested without the owner's provider credentials, consent and endpoint configuration. Do not paste API secrets into chat or commit them to Git.
