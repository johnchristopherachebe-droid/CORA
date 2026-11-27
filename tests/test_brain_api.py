"""Smoke tests for the integrated Brain API and owner-session guard."""
import os, tempfile, importlib, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

tmp = tempfile.NamedTemporaryFile(delete=False)
tmp.close()
os.environ["CORA_LOCAL_DATABASE"] = tmp.name
os.environ["CORA_ACCESS_PASSWORD"] = "test-password-that-is-long-enough"
os.environ["SESSION_SECRET"] = "s" * 48
os.environ.pop("DATABASE_URL", None)
os.environ.pop("VERCEL", None)

import sys, types
sys.modules.setdefault("groq", types.SimpleNamespace(Groq=lambda *a, **k: None))
import main
from fastapi import HTTPException
from types import SimpleNamespace

# Initialise the schema and baseline, then exercise the independent brain.
b = main._get_brain()
assert b.overview()["mode"] in ("independent", "assisted")
answer = b.answer("What is 2 plus 2?", allow_provider=False)
assert answer["answered"] and "4" in answer["answer"]

# A valid login token is required even in local mode for owner-only Brain routes.
token = main.auth_login(main.AuthLoginRequest(password=os.environ["CORA_ACCESS_PASSWORD"]))["token"]
request = SimpleNamespace(headers={"authorization": "Bearer " + token})
assert main._brain_require_owner(request) == "owner"
try:
    main._brain_require_owner(SimpleNamespace(headers={}))
    raise AssertionError("Unauthenticated owner request was accepted")
except HTTPException as exc:
    assert exc.status_code == 401


# Approval must require actual before/after benchmark evidence.
import cora_knowledge as K, cora_brain_versions as V, cora_evaluation as E
entry = K.add(main.get_connection, "Sun fact", "The Sun is a star.", category="science", source_kind="owner", source_ref="test", actor="owner")
item = K.get(main.get_connection, entry["id"])
pid = V.create_proposal(main.get_connection, "Sun fact", "Test proposal", {"add": {entry["id"]: item["version"]}}, actor="owner")
main._get_brain().test_proposal(pid)
try:
    main._get_brain().approve(pid, "owner")
    raise AssertionError("Proposal without benchmarks was approved")
except ValueError as exc:
    assert "benchmark" in str(exc).lower()
E.add_question(main.get_connection, "What is the Sun?", "A star", keywords=["star"], category="science")
main._get_brain().test_proposal(pid)
main._get_brain().approve(pid, "owner")

# Research endpoint separates web sources and YouTube video results.
main._cv_search = lambda query, limit=8: ([
    {"title": "Reference page", "url": "https://example.org/ref", "snippet": "Reference snippet", "domain": "example.org"},
    {"title": "Video result", "url": "https://www.youtube.com/watch?v=abc123", "snippet": "Video snippet", "domain": "youtube.com"},
] if "site:youtube.com" not in query else [
    {"title": "Video result", "url": "https://www.youtube.com/watch?v=abc123", "snippet": "Video snippet", "domain": "youtube.com"}
])
main._cv_fetch_page = lambda url, max_chars=3500: "Page text"
research = main.brain_research(main.BrainResearchRequest(query="test research"), "owner")
assert len(research["payload"]["sources"]) == 2
assert len(research["payload"]["videos"]) == 1

# Ensure the integrated endpoints are registered and the dashboard is served.
paths = {getattr(r, "path", "") for r in main.app.routes}
for path in ("/brain/overview", "/brain/answer", "/brain/learn", "/brain/knowledge", "/brain/proposals", "/brain/versions", "/brain/research", "/brain.html", "/connectors/whatsapp/send", "/connectors/home-assistant/service", "/operations/audit"):
    assert path in paths, path
# Connector actions require an explicit per-action confirmation and are audited.
from fastapi import HTTPException
try:
    main.connector_whatsapp_send(main.WhatsAppSendRequest(to="+2348012345678", message="Hello", confirmed=False), "owner")
    raise AssertionError("Unconfirmed WhatsApp send was accepted")
except HTTPException as exc:
    assert exc.status_code == 428
main.cora_connectors.whatsapp_send_text = lambda to, message: {"messages": [{"id": "test-id"}]}
sent = main.connector_whatsapp_send(main.WhatsAppSendRequest(to="+2348012345678", message="Hello", confirmed=True), "owner")
assert sent["success"] is True
audit = main.operations_audit(10, "owner")["items"]
assert audit and audit[0]["action"] == "whatsapp.send_text"
assert "Hello" not in repr(audit)

print("BRAIN API INTEGRATION PASS")
try: os.unlink(tmp.name)
except OSError: pass
