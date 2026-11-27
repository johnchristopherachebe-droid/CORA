"""Provider-agnostic research workspace. Search/fetch/video discovery are injected by the host."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse
import json, sqlite3, time, uuid, ipaddress
from contextlib import contextmanager

def _public_http_url(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
            return False
        host = p.hostname.rstrip(".").lower()
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal", ".test")):
            return False
        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                return False
        except ValueError:
            pass
        return True
    except Exception:
        return False

@dataclass
class Source:
    title: str
    publisher: str
    url: str
    snippet: str = ""
    published_at: str | None = None
    accessed_at: int = 0
    relevance: float | None = None

@dataclass
class Video:
    title: str
    channel: str
    url: str
    thumbnail: str | None = None
    duration: str | None = None

class ResearchWorkspace:
    def __init__(self, db_path: str | Path, search_fn, video_fn=None, postgres_dsn: str | None = None):
        self.db_path = str(db_path)
        self.postgres_dsn = (postgres_dsn or "").strip()
        self.search_fn = search_fn
        self.video_fn = video_fn
        self._init()

    @contextmanager
    def _db(self):
        if self.postgres_dsn:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(self.postgres_dsn, row_factory=dict_row, connect_timeout=10) as connection:
                yield connection
        else:
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            try:
                with connection:
                    yield connection
            finally:
                connection.close()

    def _execute(self, connection, sql: str, params=()):
        if self.postgres_dsn:
            return connection.execute(sql.replace("?", "%s"), params)
        return connection.execute(sql, params)

    def _init(self):
        with self._db() as c:
            self._execute(c, """CREATE TABLE IF NOT EXISTS research_sessions(
                id TEXT PRIMARY KEY, query TEXT NOT NULL, title TEXT NOT NULL,
                created_at INTEGER NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL)""")
            self._execute(c, "CREATE INDEX IF NOT EXISTS idx_research_sessions_created ON research_sessions(created_at DESC)")

    def create(self, query: str, title: str | None = None) -> dict:
        query = (query or "").strip()
        if not query or len(query) > 1000:
            raise ValueError("A research question between 1 and 1000 characters is required")
        raw_sources = self.search_fn(query)
        sources = []
        for raw in raw_sources or []:
            url = str(raw.get("url", ""))
            if not _public_http_url(url):
                continue
            sources.append(asdict(Source(
                title=str(raw.get("title") or "Untitled")[:300],
                publisher=str(raw.get("publisher") or raw.get("domain") or "")[:160],
                url=url, snippet=str(raw.get("snippet") or "")[:2000],
                published_at=raw.get("published_at"), accessed_at=int(time.time()),
                relevance=raw.get("relevance")
            )))
        videos = []
        if self.video_fn:
            for raw in self.video_fn(query) or []:
                url = str(raw.get("url", ""))
                if _public_http_url(url):
                    videos.append(asdict(Video(str(raw.get("title") or "Untitled")[:300],
                        str(raw.get("channel") or "")[:160], url,
                        raw.get("thumbnail"), raw.get("duration"))))
        session_id = uuid.uuid4().hex
        payload = {"overview": "", "sources": sources, "videos": videos, "analysis": [],
                   "notice": "Sources and videos are provider results; verify important claims against originals."}
        with self._db() as c:
            self._execute(c, "INSERT INTO research_sessions VALUES(?,?,?,?,?,?)",
                           (session_id, query, (title or query)[:200], int(time.time()), "complete", json.dumps(payload)))
        return self.get(session_id)

    def set_overview(self, session_id: str, overview: str) -> dict:
        with self._db() as c:
            row = self._execute(c, "SELECT payload FROM research_sessions WHERE id=?", (session_id,)).fetchone()
            if not row:
                raise KeyError("Research session not found")
            payload = json.loads(row["payload"])
            payload["overview"] = str(overview or "")[:12000]
            self._execute(c, "UPDATE research_sessions SET payload=? WHERE id=?", (json.dumps(payload), session_id))
        return self.get(session_id)

    def get(self, session_id: str) -> dict:
        with self._db() as c:
            row = self._execute(c, "SELECT * FROM research_sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            raise KeyError("Research session not found")
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        return result

    def list(self, limit: int = 30) -> list[dict]:
        with self._db() as c:
            rows = self._execute(c, "SELECT id,query,title,created_at,status FROM research_sessions ORDER BY created_at DESC LIMIT ?",
                                  (max(1, min(int(limit), 100)),)).fetchall()
        return [dict(x) for x in rows]
