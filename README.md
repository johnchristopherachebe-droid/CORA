# CORA Cloud — Vercel deployment with Automatic AI Brain

This release preserves the Vercel FastAPI backend, dashboard, British/Deep/Calm browser voice, PostgreSQL memory, tasks, cloud Builder and login. It adds an automatic multi-provider AI router.

## What Automatic mode does

CORA checks the provider keys you configure and tries providers in the order in `AI_BRAIN_ORDER`. If a provider returns an error (for example, a rate limit, unavailable model or temporary outage), CORA tries the next configured provider. Provider keys are kept on the server; they are never sent to the dashboard.

Default priority:

1. Google Gemini
2. Groq
3. Cerebras
4. OpenRouter

You can change the order, for example `groq,gemini,cerebras,openrouter`. Only providers for which you supply an API key are used. Free quotas and model availability vary by provider and can change. Automatic failover does not create unlimited free usage.

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
4. In Vercel, add provider keys under **Settings → Environment Variables**. Keep your existing `DATABASE_URL` and `CORA_ACCESS_PASSWORD` unchanged.
5. Ensure `AI_BRAIN_ORDER` is set to the preferred order, or use the default.
6. Redeploy the project.
7. Sign in to CORA and open `/ai/status` while logged in to see which providers are configured and their priority (the endpoint never reveals keys).

## Existing services preserved

- FastAPI cloud API and dashboard in one Vercel project.
- Groq integration retained as one provider.
- British English / deep / calm browser voice UI and Hey wake-word flow.
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
