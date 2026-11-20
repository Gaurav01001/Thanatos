from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)


class UserMemory:
    """
    Stage 8 Persistent User Memory Subsystem.
    
    Stores persistent user identity, preferences, and episodic facts
    in a lightweight, zero-dependency local SQLite database.
    
    Data survives application exits, computer reboots, and session wipes.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            # Default location: d:\Thanatos\data\user_memory.db
            base_dir = Path(__file__).resolve().parents[3] / "data"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = base_dir / "user_memory.db"

        self._lock = threading.Lock()
        self._init_database()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Creates a thread-safe connection with row factory enabled, automatically closing it."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_database(self) -> None:
        """Initializes tables for key-value facts and freeform episodic notes."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Table 1: Key-Value User Profile (e.g. name, language, os, role)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Table 2: Episodic Notes / Instructions (e.g. project details, preferences)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()
            logger.info("UserMemory database initialized at %s", self.db_path)

    def set_fact(self, key: str, value: str) -> bool:
        """
        Saves or updates an attribute (e.g. key="name", value="Gaurav").
        Case-insensitive keys for easy retrieval.
        """
        if not key or not value:
            return False

        clean_key = key.strip().lower()
        clean_val = value.strip()
        now = datetime.now().isoformat()

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_profile (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
            """, (clean_key, clean_val, now))
            conn.commit()
            logger.info("Saved user fact [%s: %s]", clean_key, clean_val)
            return True

    def get_fact(self, key: str) -> Optional[str]:
        """Retrieves a specific fact by key."""
        if not key:
            return None

        clean_key = key.strip().lower()
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM user_profile WHERE key = ?", (clean_key,))
            row = cursor.fetchone()
            return row["value"] if row else None

    def add_note(self, content: str) -> bool:
        """Stores an open-ended observation or user preference, preventing exact duplicates."""
        if not content or not content.strip():
            return False

        clean_content = content.strip()
        now = datetime.now().isoformat()

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM user_notes WHERE LOWER(content) = LOWER(?) LIMIT 1", (clean_content,))
            if cursor.fetchone():
                logger.info("User note already exists (deduplicated): %s", clean_content)
                return True

            cursor.execute("""
                INSERT INTO user_notes (content, created_at)
                VALUES (?, ?)
            """, (clean_content, now))
            conn.commit()
            logger.info("Added user note: %s", clean_content)
            return True

    def get_all_memories(self) -> dict[str, Any]:
        """Returns all stored profile attributes and notes in a structured dictionary."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT key, value FROM user_profile ORDER BY key ASC")
            profile = {row["key"]: row["value"] for row in cursor.fetchall()}

            cursor.execute("SELECT id, content FROM user_notes ORDER BY id ASC")
            notes = [{"id": row["id"], "content": row["content"]} for row in cursor.fetchall()]

            return {"profile": profile, "notes": notes}

    def delete_fact(self, key: str) -> bool:
        """Deletes a specific profile attribute."""
        if not key:
            return False

        clean_key = key.strip().lower()
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_profile WHERE key = ?", (clean_key,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_note(self, note_id: int) -> bool:
        """Deletes a specific note by ID."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_notes WHERE id = ?", (note_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_all(self) -> bool:
        """Wipes all persistent user memory tables completely."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_profile")
            cursor.execute("DELETE FROM user_notes")
            conn.commit()
            logger.info("Cleared all user memory.")
            return True

    def build_context_prompt(self) -> str:
        """
        Synthesizes known user context into a compact system block to inject into the LLM.
        Keeps token overhead minimal while ensuring full personalization.
        """
        memories = self.get_all_memories()
        profile = memories["profile"]
        notes = memories["notes"]

        if not profile and not notes:
            return ""

        lines = ["[Known User Information & Preferences]"]
        
        # Priority profile facts
        if "name" in profile:
            lines.append(f"- User's Name: {profile['name']}")
        
        for k, v in profile.items():
            if k != "name":
                lines.append(f"- {k.replace('_', ' ').capitalize()}: {v}")

        for note in notes[:5]:  # Include up to 5 most relevant notes
            lines.append(f"- {note['content']}")

        return "\n".join(lines)
