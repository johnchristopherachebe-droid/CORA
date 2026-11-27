import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cora_integrations
from research_workspace import ResearchWorkspace


def test_integration_status_never_discloses_secrets():
    env = {
        "GEMINI_API_KEY": "do-not-return-this",
        "TWILIO_ACCOUNT_SID": "sid",
        "TWILIO_AUTH_TOKEN": "auth-secret",
        "TWILIO_PHONE_NUMBER": "+10000000000",
        "TWILIO_WEBHOOK_BASE_URL": "https://cora.example",
        "DATABASE_URL": "postgresql://private:secret@example.invalid/db",
        "EMAIL_OAUTH_CLIENT_ID": "client-id",
        "EMAIL_OAUTH_CLIENT_SECRET": "mail-secret",
        "EMAIL_OAUTH_REFRESH_TOKEN": "refresh-secret",
    }
    result = cora_integrations.integration_status(env)
    rendered = repr(result)
    assert "do-not-return-this" not in rendered
    assert "auth-secret" not in rendered
    assert "private:secret" not in rendered
    by_id = {item["id"]: item for item in result["items"]}
    assert by_id["ai_models"]["status"] == "configured"
    assert by_id["telephony"]["status"] == "configured"
    assert by_id["persistent_cloud"]["status"] == "configured"
    assert by_id["email"]["status"] == "configured"
    assert "mail-secret" not in rendered and "refresh-secret" not in rendered
    assert "owner-confirmed" in by_id["whatsapp"]["capabilities"][0].lower()
    assert "gmail inbox metadata" in by_id["email"]["capabilities"][0].lower()


def test_research_workspace_persists_sessions_and_filters_unsafe_urls():
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "research.sqlite")
        search = lambda q: [
            {"title": "Good source", "url": "https://example.com/a", "snippet": "Useful"},
            {"title": "Local target", "url": "http://127.0.0.1/private"},
            {"title": "Credential URL", "url": "https://user:pass@example.com/"},
        ]
        workspace = ResearchWorkspace(db, search)
        created = workspace.create("test query")
        assert len(created["payload"]["sources"]) == 1
        workspace.set_overview(created["id"], "Saved overview")
        restarted = ResearchWorkspace(db, search)
        loaded = restarted.get(created["id"])
        assert loaded["payload"]["overview"] == "Saved overview"
        assert restarted.list()[0]["id"] == created["id"]


if __name__ == "__main__":
    test_integration_status_never_discloses_secrets()
    test_research_workspace_persists_sessions_and_filters_unsafe_urls()
    print("INTEGRATION + RESEARCH TESTS PASS")
