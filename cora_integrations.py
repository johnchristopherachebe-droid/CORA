"""Honest integration readiness catalogue. Never returns credential values."""
from __future__ import annotations
import os
from typing import Mapping


def _configured(env: Mapping[str, str], *keys: str) -> bool:
    return all(bool((env.get(key) or "").strip()) for key in keys)


def integration_status(env: Mapping[str, str] | None = None) -> dict:
    """Describe readiness only; credentials being present does not prove provider access."""
    env = env or os.environ
    items = [
        {
            "id": "ai_models", "name": "AI model providers", "category": "intelligence",
            "status": "configured" if any(_configured(env, k) for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY")) else "needs_setup",
            "requirements": ["At least one supported model API key"],
            "capabilities": ["Chat", "Model routing", "Provider failover"],
        },
        {
            "id": "voice", "name": "Browser voice", "category": "voice",
            "status": "available_in_supported_browsers",
            "requirements": ["Browser speech recognition and microphone permission", "Browser speech synthesis"],
            "capabilities": ["Speech input", "Spoken replies", "Opt-in wake phrase"],
        },
        {
            "id": "fish_audio", "name": "Fish Audio", "category": "voice",
            "status": "configured" if _configured(env, "FISH_API_KEY", "FISH_VOICE_ID") else "needs_setup",
            "requirements": ["FISH_API_KEY", "FISH_VOICE_ID"],
            "capabilities": ["Optional hosted voice generation"],
        },
        {
            "id": "telephony", "name": "AI phone receptionist", "category": "communications",
            "status": "configured" if _configured(env, "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER", "TWILIO_WEBHOOK_BASE_URL") else "needs_setup",
            "requirements": ["Telephony provider account", "Verified phone number", "TWILIO_WEBHOOK_BASE_URL", "Public HTTPS webhook and consent configuration"],
            "capabilities": ["Signed Twilio voice webhooks", "Disclosure-first AI receptionist", "Short speech turns; no call audio or transcript retention"],
        },
        {
            "id": "whatsapp", "name": "WhatsApp Business", "category": "communications",
            "status": "configured" if _configured(env, "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID") else "needs_setup",
            "requirements": ["WhatsApp Business Cloud API access token", "Phone number ID", "Webhook verification"],
            "capabilities": ["Owner-confirmed text sending through the official WhatsApp Business Cloud API"],
        },
        {
            "id": "email", "name": "Email", "category": "communications",
            "status": "configured" if _configured(env, "EMAIL_OAUTH_CLIENT_ID", "EMAIL_OAUTH_CLIENT_SECRET", "EMAIL_OAUTH_REFRESH_TOKEN") else "needs_setup",
            "requirements": ["OAuth client credentials", "User-authorised refresh token", "Provider scopes"],
            "capabilities": ["Gmail inbox metadata and snippets", "Owner-confirmed email sending through Gmail API"],
        },
        {
            "id": "smart_home", "name": "Smart home", "category": "devices",
            "status": "configured" if _configured(env, "HOME_ASSISTANT_URL", "HOME_ASSISTANT_TOKEN") else "needs_setup",
            "requirements": ["Compatible home automation server", "Scoped access token", "Explicit device permissions"],
            "capabilities": ["Read device states and owner-confirmed light, switch and scene actions via HTTPS"],
        },
        {
            "id": "desktop_agent", "name": "Desktop companion", "category": "devices",
            "status": "not_installed",
            "requirements": ["Separately installed local companion", "Explicit device pairing", "Per-action permissions"],
            "capabilities": ["No remote desktop control is enabled"],
        },
        {
            "id": "ios", "name": "iPhone / Shortcuts", "category": "devices",
            "status": "platform_setup_required",
            "requirements": ["Apple Shortcuts configuration", "iOS permissions and supported app actions"],
            "capabilities": ["Web dashboard is mobile responsive; native device automation is not enabled"],
        },
        {
            "id": "persistent_cloud", "name": "Persistent cloud database", "category": "cloud",
            "status": "configured" if _configured(env, "DATABASE_URL") else "local_only",
            "requirements": ["DATABASE_URL pointing to a supported PostgreSQL database"],
            "capabilities": ["Persistent memories, tasks and research when configured"],
        },
    ]
    return {
        "items": items,
        "summary": {
            "configured": sum(x["status"] == "configured" for x in items),
            "needs_setup": sum(x["status"] == "needs_setup" for x in items),
            "not_activated": sum(x["status"] in {"not_installed", "platform_setup_required", "local_only"} for x in items),
        },
        "security_note": "Only readiness metadata is returned. Secret values are never exposed. Configured credentials do not prove that a provider connection has been tested. WhatsApp and Gmail sending and Home Assistant control require an authenticated owner session and explicit per-action confirmation; actions are audited. Twilio webhooks require a valid provider signature and disclose that CORA is an AI.",
    }
