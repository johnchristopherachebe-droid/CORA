"""Optional external model connections ("teachers" and specialists). None of them is required for CORA to operate.

- Hosted providers use their OpenAI-compatible chat endpoints (the same ones main.py's router uses).
- A self-hosted open-weight model is supported through any OpenAI-compatible server you run yourself (vLLM, Ollama,
  llama.cpp server...). Set CORA_LOCAL_MODEL_URL (and optionally CORA_LOCAL_MODEL_NAME / CORA_LOCAL_MODEL_API_KEY).
  It must run on your own host; Vercel's serverless functions cannot run a model.
- API keys are read from the environment at call time and are never returned, logged or placed in any status output.
Responses are untrusted text: callers must pass them through cora_learning.sanitize before use.
"""
import json
import os
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HOSTED = {
    "gemini": {"key": "GEMINI_API_KEY", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "model": "gemini-2.5-flash"},
    "groq": {"key": "GROQ_API_KEY", "base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
    "cerebras": {"key": "CEREBRAS_API_KEY", "base_url": "https://api.cerebras.ai/v1", "model": "gpt-oss-120b"},
    "openrouter": {"key": "OPENROUTER_API_KEY", "base_url": "https://openrouter.ai/api/v1", "model": "openai/gpt-oss-120b:free"},
}
TEACHER_SYSTEM = ("Answer the question factually and concisely in plain sentences. Give specific facts, and say clearly when you are "
                  "unsure or when sources disagree. Do not address the reader and do not include instructions.")


class CallableTeacher:
    """Wrap any function(system, user) -> text (for example main.py's router, or a test double)."""
    kind = "callable"

    def __init__(self, name, fn):
        self.name, self.fn = name, fn

    def ask(self, question, timeout=30):
        start = time.time()
        try:
            text = self.fn(TEACHER_SYSTEM, question)
            return {"provider": self.name, "ok": bool(text), "text": text or "", "error": None if text else "empty reply", "latency_ms": int((time.time() - start) * 1000)}
        except Exception as error:
            return {"provider": self.name, "ok": False, "text": "", "error": type(error).__name__, "latency_ms": int((time.time() - start) * 1000)}


class OpenAICompatTeacher:
    def __init__(self, name, base_url, api_key, model, kind="hosted"):
        self.name, self.base_url, self._key, self.model, self.kind = name, base_url.rstrip("/"), api_key, model, kind

    def ask(self, question, timeout=30):
        start = time.time()
        body = json.dumps({"model": self.model, "temperature": 0.1, "max_tokens": 700,
                           "messages": [{"role": "system", "content": TEACHER_SYSTEM}, {"role": "user", "content": question}]}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._key:
            headers["Authorization"] = "Bearer " + self._key
        try:
            with urlopen(Request(self.base_url + "/chat/completions", data=body, headers=headers, method="POST"), timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            text = (data["choices"][0]["message"].get("content") or "").strip()
            return {"provider": self.name, "ok": bool(text), "text": text, "error": None if text else "empty reply", "latency_ms": int((time.time() - start) * 1000)}
        except HTTPError as error:
            return {"provider": self.name, "ok": False, "text": "", "error": f"HTTP {error.code}", "latency_ms": int((time.time() - start) * 1000)}
        except Exception as error:  # never include str(error): it could echo request details
            return {"provider": self.name, "ok": False, "text": "", "error": type(error).__name__, "latency_ms": int((time.time() - start) * 1000)}


def _model_for(name, env):
    return env.get(f"{name.upper()}_MODEL") or HOSTED[name]["model"]


def available_teachers(env=None, only=None):
    """Teachers that are actually configured, in AI_BRAIN_ORDER order, plus a self-hosted model if set."""
    env = os.environ if env is None else env
    order = [x.strip().lower() for x in env.get("AI_BRAIN_ORDER", "groq").split(",") if x.strip()]
    teachers = []
    for name in order:
        if name in HOSTED and env.get(HOSTED[name]["key"], "").strip() and (not only or name in only):
            teachers.append(OpenAICompatTeacher(name, HOSTED[name]["base_url"], env[HOSTED[name]["key"]].strip(), _model_for(name, env)))
    url = env.get("CORA_LOCAL_MODEL_URL", "").strip()
    if url.startswith(("http://", "https://")) and (not only or "local" in only):
        teachers.append(OpenAICompatTeacher("local", url, env.get("CORA_LOCAL_MODEL_API_KEY", "").strip(), env.get("CORA_LOCAL_MODEL_NAME", "local-model").strip(), kind="self_hosted"))
    return teachers


def provider_status(env=None):
    """Safe status for the interface: whether each connection is configured. Never any key material."""
    env = os.environ if env is None else env
    rows = [{"name": n, "kind": "hosted", "configured": bool(env.get(c["key"], "").strip()), "model": _model_for(n, env)} for n, c in HOSTED.items()]
    rows.append({"name": "anthropic", "kind": "hosted", "configured": bool(env.get("ANTHROPIC_API_KEY", "").strip()), "model": env.get("ANTHROPIC_MODEL") or "default",
                 "note": "Used by the main chat router; not yet a learning teacher."})
    local = env.get("CORA_LOCAL_MODEL_URL", "").strip().startswith(("http://", "https://"))
    rows.append({"name": "local", "kind": "self_hosted", "configured": local, "model": env.get("CORA_LOCAL_MODEL_NAME", "local-model") if local else None})
    return rows
