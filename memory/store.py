"""
Shared SQLite memory store — accessible by all agents.
"""
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path(__file__).parent.parent / "data" / "memory.db"


class MemoryStore:
    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT    NOT NULL,
                    role      TEXT    NOT NULL,
                    agent     TEXT    NOT NULL,
                    content   TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS facts (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT    NOT NULL,
                    category  TEXT    NOT NULL,
                    key       TEXT    NOT NULL,
                    value     TEXT    NOT NULL,
                    UNIQUE(category, key) ON CONFLICT REPLACE
                );

                CREATE TABLE IF NOT EXISTS handoffs (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp        TEXT NOT NULL,
                    specialist_type  TEXT NOT NULL,
                    original_query   TEXT NOT NULL,
                    summary          TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS summaries (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    period    TEXT NOT NULL,
                    content   TEXT NOT NULL
                );
            """)

    # ── Messages ──────────────────────────────────────────────────────────────

    def add_message(self, role: str, agent: str, content: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO messages (timestamp, role, agent, content) VALUES (?,?,?,?)",
                (self._now(), role, agent, content),
            )

    def get_recent_messages(self, n: int = 30) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM messages ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # ── Facts ─────────────────────────────────────────────────────────────────

    def add_fact(self, category: str, key: str, value: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO facts (timestamp, category, key, value) VALUES (?,?,?,?)",
                (self._now(), category, key, value),
            )

    def get_facts(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM facts ORDER BY category, key").fetchall()
        return [dict(r) for r in rows]

    # ── Handoffs ──────────────────────────────────────────────────────────────

    def add_handoff(self, specialist_type: str, original_query: str, summary: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO handoffs (timestamp, specialist_type, original_query, summary) VALUES (?,?,?,?)",
                (self._now(), specialist_type, original_query, summary),
            )

    def get_recent_handoffs(self, n: int = 5) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM handoffs ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # ── Context block (injected into every agent system prompt) ───────────────

    def build_context_block(self) -> str:
        parts: list[str] = []

        facts = self.get_facts()
        if facts:
            parts.append("## Known Facts About the User")
            for f in facts:
                parts.append(f"- [{f['category']}] {f['key']}: {f['value']}")

        handoffs = self.get_recent_handoffs()
        if handoffs:
            parts.append("\n## Recent Specialist Handoffs")
            for h in handoffs:
                parts.append(
                    f"- {h['timestamp'][:16]} | {h['specialist_type'].upper()}: {h['summary'][:200]}"
                )

        recent = self.get_recent_messages(20)
        if recent:
            parts.append("\n## Recent Conversation History")
            for m in recent:
                tag = f"[{m['agent']}]" if m["agent"] != "user" else "[User]"
                parts.append(f"{tag} {m['content'][:300]}")

        return "\n".join(parts) if parts else "(No prior context yet)"

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
