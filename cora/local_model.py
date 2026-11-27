"""OpenAI-compatible local model adapter. Endpoint must be configured by the operator, not user input."""
from __future__ import annotations
import json, os
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse

class LocalModel:
    def __init__(self, base_url=None, model=None, api_key=None, timeout=45):
        self.base_url = (base_url or os.getenv("CORA_LOCAL_MODEL_URL", "")).rstrip("/")
        self.model = model or os.getenv("CORA_LOCAL_MODEL_NAME", "local-model")
        self.api_key = api_key or os.getenv("CORA_LOCAL_MODEL_API_KEY", "")
        self.timeout = max(5, min(int(timeout), 90))
        p = urlparse(self.base_url)
        if p.scheme not in ("http", "https") or not p.hostname:
            raise ValueError("Configure CORA_LOCAL_MODEL_URL with an operator-controlled HTTP(S) endpoint")
        if p.username or p.password:
            raise ValueError("Credentials must not be embedded in the model URL")
        if p.scheme == "http" and p.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("Non-local model endpoints must use HTTPS")

    def chat(self, messages, temperature=0.3, max_tokens=1200):
        body = json.dumps({"model": self.model, "messages": messages,
                           "temperature": temperature, "max_tokens": max_tokens}).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        req = Request(self.base_url + "/v1/chat/completions", data=body, headers=headers, method="POST")
        try:
            with urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read(2_000_000).decode("utf-8"))
        except (URLError, HTTPError, TimeoutError) as exc:
            raise RuntimeError("Local model request failed") from exc
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError("Local model returned an unexpected response")
