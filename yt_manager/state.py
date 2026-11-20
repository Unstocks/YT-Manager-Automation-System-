"""
YT Manager State Persistence Engine
Powered by SQLite3 for atomic, ACID-compliant, local-first transaction guarantees.
Survives system restarts, crash recoveries, and ensures absolute idempotency.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


class StateManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS batches (
                id TEXT PRIMARY KEY,
                execution_date TEXT NOT NULL,
                status TEXT NOT NULL,  -- PENDING, IN_PROGRESS, COMPLETED, FAILED, PARTIAL
                clip_count INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                report_path TEXT
            );

            CREATE TABLE IF NOT EXISTS clips (
                id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                duration REAL,
                width INTEGER,
                height INTEGER,
                status TEXT NOT NULL,  -- DETECTED, INSPECTED, METADATA_GENERATED, UPLOADING, UPLOADED, VERIFIED, FAILED
                retry_count INTEGER DEFAULT 0,
                metadata_path TEXT,
                youtube_video_id TEXT,
                youtube_url TEXT,
                privacy_status TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (batch_id) REFERENCES batches(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS upload_history (
                file_hash TEXT PRIMARY KEY,
                original_filename TEXT NOT NULL,
                youtube_video_id TEXT NOT NULL,
                youtube_url TEXT NOT NULL,
                uploaded_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS execution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_clips_batch ON clips(batch_id);
            CREATE INDEX IF NOT EXISTS idx_clips_hash ON clips(file_hash);
            CREATE INDEX IF NOT EXISTS idx_batches_date ON batches(execution_date);
            """)

    def is_hash_uploaded(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Check if a video with this SHA-256 hash was previously uploaded."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM upload_history WHERE file_hash = ?", (file_hash,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_batch(self, batch_id: str, date_str: str, clip_count: int) -> str:
        """Create a new daily batch entry."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO batches (id, execution_date, status, clip_count, started_at)
                VALUES (?, ?, 'IN_PROGRESS', ?, ?)
                """,
                (batch_id, date_str, clip_count, now),
            )
        return batch_id

    def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM batches WHERE id = ?", (batch_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_batch_for_date(self, date_str: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM batches WHERE execution_date = ? ORDER BY started_at DESC LIMIT 1",
                (date_str,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_batch_status(
        self, batch_id: str, status: str, report_path: Optional[str] = None
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            if status in ("COMPLETED", "FAILED", "PARTIAL"):
                conn.execute(
                    """
                    UPDATE batches SET status = ?, completed_at = ?, report_path = coalesce(?, report_path)
                    WHERE id = ?
                    """,
                    (status, now, report_path, batch_id),
                )
            else:
                conn.execute(
                    "UPDATE batches SET status = ? WHERE id = ?", (status, batch_id)
                )

    def register_clip(
        self,
        clip_id: str,
        batch_id: str,
        original_filename: str,
        file_hash: str,
        file_size: int,
        duration: float = 0.0,
        width: int = 0,
        height: int = 0,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO clips (
                    id, batch_id, original_filename, file_hash, file_size,
                    duration, width, height, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DETECTED', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    updated_at = excluded.updated_at
                """,
                (
                    clip_id,
                    batch_id,
                    original_filename,
                    file_hash,
                    file_size,
                    duration,
                    width,
                    height,
                    now,
                    now,
                ),
            )

    def update_clip_metadata(
        self,
        clip_id: str,
        duration: float,
        width: int,
        height: int,
        metadata_path: str,
        status: str = "METADATA_GENERATED",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE clips SET
                    duration = ?,
                    width = ?,
                    height = ?,
                    metadata_path = ?,
                    status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (duration, width, height, metadata_path, status, now, clip_id),
            )

    def update_clip_status(
        self,
        clip_id: str,
        status: str,
        error_message: Optional[str] = None,
        youtube_video_id: Optional[str] = None,
        youtube_url: Optional[str] = None,
        privacy_status: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE clips SET
                    status = ?,
                    error_message = ?,
                    youtube_video_id = coalesce(?, youtube_video_id),
                    youtube_url = coalesce(?, youtube_url),
                    privacy_status = coalesce(?, privacy_status),
                    updated_at = ?
                WHERE id = ?
                """,
                (status, error_message, youtube_video_id, youtube_url, privacy_status, now, clip_id),
            )

    def record_successful_upload(
        self,
        file_hash: str,
        original_filename: str,
        youtube_video_id: str,
        youtube_url: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO upload_history (file_hash, original_filename, youtube_video_id, youtube_url, uploaded_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(file_hash) DO UPDATE SET
                    youtube_video_id = excluded.youtube_video_id,
                    youtube_url = excluded.youtube_url,
                    uploaded_at = excluded.uploaded_at
                """,
                (file_hash, original_filename, youtube_video_id, youtube_url, now),
            )

    def get_clips_for_batch(self, batch_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM clips WHERE batch_id = ? ORDER BY created_at ASC",
                (batch_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def log(self, batch_id: Optional[str], level: str, message: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO execution_logs (batch_id, level, message, timestamp) VALUES (?, ?, ?, ?)",
                (batch_id, level, message, now),
            )
