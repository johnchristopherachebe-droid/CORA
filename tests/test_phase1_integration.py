import sys, types, os, json, sqlite3, asyncio, hmac, hashlib, time

# ---------- stub the third-party packages that are not installed in this sandbox ----------
class _Any:
    def __init__(self, *a, **k): self.args, self.kwargs = a, k
def _mod(name, **attrs):
    m = types.ModuleType(name)
    m.__getattr__ = lambda n: type(n, (_Any,), {})
    for k, v in attrs.items(): setattr(m, k, v)
    sys.modules[name] = m; return m

class HTTPException(Exception):
    def __init__(self, status_code=500, detail=""): self.status_code, self.detail = status_code, detail; super().__init__(detail)
class FastAPI:
    def __init__(self, **k): self.router = types.SimpleNamespace(routes=[]); self.routes = self.router.routes
    def _reg(self, method):
        def deco(path, **k):
            def inner(fn):
                self.router.routes.append(types.SimpleNamespace(path=path, method=method, endpoint=fn)); return fn
            return inner
        return deco
    def __getattr__(self, n):
        if n in ("get", "post", "put", "delete", "patch"): return self._reg(n)
        raise AttributeError(n)
    def middleware(self, kind): return lambda fn: fn
    def add_middleware(self, *a, **k): pass
class JSONResponse:
    def __init__(self, status_code=200, content=None, headers=None): self.status_code, self.content = status_code, content
_mod("fastapi", FastAPI=FastAPI, HTTPException=HTTPException, UploadFile=_Any, File=lambda *a, **k: None, Form=lambda *a, **k: None, Request=_Any)
_mod("fastapi.responses", JSONResponse=JSONResponse)
_mod("fastapi.middleware"); _mod("fastapi.middleware.cors")
_mod("starlette"); _mod("starlette.concurrency")
_mod("groq"); _mod("dotenv", load_dotenv=lambda *a, **k: None)
def Field(default=None, **k): return default
class BaseModel:
    def __init__(self, **kw):
        for name in getattr(type(self), "__annotations__", {}):
            setattr(self, name, kw.get(name, getattr(type(self), name, None)))
_mod("pydantic", BaseModel=BaseModel, Field=Field)

DB = "/tmp/main_integration.db"
if os.path.exists(DB): os.remove(DB)
# an OLD database, from before this upgrade (memories has no category column)
raw = sqlite3.connect(DB)
raw.execute("CREATE TABLE memories (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
raw.execute("INSERT INTO memories (content) VALUES ('legacy memory')"); raw.commit(); raw.close()
os.environ["CORA_LOCAL_DATABASE"] = DB
for k in ("VERCEL", "DATABASE_URL"): os.environ.pop(k, None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main
print("main imported; routes:", len(main.app.router.routes))

# ---------- migration kept old data ----------
mems = main.get_memories()
assert any(m["content"] == "legacy memory" and m["category"] == "general" for m in mems), mems
print("old database migrated OK")

# ---------- fake AI ----------
seen = {}
def fake_llm(system, user, max_tokens=900, temperature=0.3, json_mode=False):
    if "planning module" in system:
        return json.dumps({"steps": [{"tool": "web_research", "input": {"question": "AI firms"}, "purpose": "Research"},
                                     {"tool": "draft", "input": {"instruction": "Compare {{step1}}"}, "purpose": "Write comparison"}]})
    if system.startswith("You check work"): return json.dumps({"ok": True, "reason": "fine"})
    if "final message" in system: return "I researched and compared them. Everything checked out."
    if "Write exactly what is asked" in system: return "Comparison [1]"
    if "pick what is worth remembering" in system or "You pick what is worth" in system:
        return json.dumps({"suggestions": [{"content": "User is upgrading CORA", "category": "project"}]})
    return "{}"
main._x_llm = fake_llm
main._x_research = lambda q, d=2: {"question": q, "reply": "Findings [1]", "sources": [{"n": 1, "title": "T", "url": "https://e.com"}], "queries": [q]}
main.has_ai_provider = lambda: True
class FakeClient:
    class chat:
        class completions:
            @staticmethod
            def create(**kw):
                seen["messages"] = kw["messages"]
                msg = types.SimpleNamespace(content="Right then, here you go.")
                return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])
main.get_ai_client = lambda: FakeClient()
C = main.ChatRequest

# ---------- memory via chat ----------
r = main.chat(C(message="remember project: building CORA phase 1"))["reply"]; assert "projects" in r.lower(), r
r = main.chat(C(message="remember I prefer British spelling"))["reply"]; assert "preferences" in r.lower(), r
r = main.chat(C(message="remember my password is hunter2"))["reply"]; assert "password" in r.lower() and "store" in r.lower(), r
assert not any("hunter2" in m["content"] for m in main.get_memories())
listing = main.chat(C(message="what do you remember"))["reply"]
assert "Projects:" in listing and "Preferences:" in listing and "General:" in listing, listing
r = main.chat(C(message="what should you remember from this chat"))["reply"]; assert "upgrading CORA" in r, r
print("chat memory commands OK")

# ---------- normal chat uses the new persona + grouped memory + no Sir ----------
out = main.chat(C(message="How are you getting on today?"))
assert out["reply"] == "Right then, here you go."
sysmsg = seen["messages"][0]["content"]
assert "Never call the user 'Sir'" in sysmsg and "Projects:" in sysmsg and "first person" in sysmsg and "legacy memory" in sysmsg
print("persona + grouped memory in chat prompt OK")

# ---------- agent via plain language ----------
out = main.chat(C(message="Research five AI companies, compare their services and prepare a report."))
assert out.get("agent_status") == "done" and "researched" in out["reply"], out
tid = out["agent_task_id"]
assert main.agent_get_task(tid)["plan"][0]["verified"] is True
st = main.chat(C(message="how's my task going"))["reply"]; assert "researched" in st or "finished" in st, st
print("agent through /chat OK")

# ---------- REST endpoints ----------
t = main.agent_create_task(main.AgentTaskCreate(goal="Research cats and compare them with dogs please", run=False))
assert t["status"] == "planned"
t = main.agent_run_task(t["id"]); assert t["status"] == "done"
t2 = main.agent_create_task(main.AgentTaskCreate(goal="Research birds and compare them with bats please", run=False))
assert main.agent_cancel_task(t2["id"])["success"]
assert main.agent_run_task(t2["id"])["status"] == "cancelled"
assert main.agent_stop_all()["success"]
assert len(main.agent_list_tasks()["tasks"]) >= 3
mem = main.create_memory(main.MemoryCreate(content="I am building a robot", category=None)); assert mem["category"] == "project", mem
assert main.edit_memory(mem["id"], main.MemoryUpdate(content=None, category="decision"))["success"]
assert main.view_memories("decision")["total"] == 1
try: main.create_memory(main.MemoryCreate(content="api key is abc123", category=None)); raise SystemExit("secret accepted!")
except HTTPException as e: assert e.status_code == 400
print("REST endpoints OK")

# ---------- session secret ----------
main.ACCESS_PASSWORD = "p" * 20
main.SESSION_SECRET = "s" * 40
tok = main.auth_login(main.AuthLoginRequest(password="p" * 20))["token"]
issued, sig = tok.split(".", 1)
assert hmac.compare_digest(sig, hmac.new(("s" * 40).encode(), issued.encode(), hashlib.sha256).hexdigest())
assert not hmac.compare_digest(sig, hmac.new(("p" * 20).encode(), issued.encode(), hashlib.sha256).hexdigest()), "token must not depend on the password"
main.CLOUD_MODE = True
class Req:
    def __init__(self, token): self.url = types.SimpleNamespace(path="/chat"); self.headers = {"authorization": "Bearer " + token}
async def nxt(req): return "PASSED"
assert asyncio.run(main.protect_cloud_api(Req(tok), nxt)) == "PASSED"
legacy = str(int(time.time())); legacy_tok = legacy + "." + hmac.new(("p" * 20).encode(), legacy.encode(), hashlib.sha256).hexdigest()
assert asyncio.run(main.protect_cloud_api(Req(legacy_tok), nxt)).status_code == 401, "password-keyed token must be rejected once SESSION_SECRET is set"
assert main.ai_status()["session_secret_configured"] is True
main.CLOUD_MODE = False
print("session secret OK")
print("ALL INTEGRATION CHECKS PASS")
