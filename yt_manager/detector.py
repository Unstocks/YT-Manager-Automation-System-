"""
YT Manager Inbox Detection & Validation Module
Scans inbox, validates media, hashes files (SHA-256), prevents duplicate uploads,
and enforces the strict 2-clip daily batch rule.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from .config import YTManagerConfig
from .state import StateManager

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


@dataclass
class DetectedClip:
    path: Path
    filename: str
    file_hash: str
    file_size: int
    is_readable: bool
    is_duplicate: bool
    duplicate_info: Optional[dict] = None


@dataclass
class DetectionResult:
    status: str  # READY, INSUFFICIENT, DUPLICATE_DETECTED, ERROR
    message: str
    clips: List[DetectedClip]
    batch_id: Optional[str] = None
    processing_paths: List[Path] = None
    remaining_count: int = 0


def compute_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """Computes SHA-256 checksum of a file efficiently."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


class ClipDetector:
    def __init__(self, config: YTManagerConfig, state_manager: StateManager):
        self.config = config
        self.state = state_manager

    def scan_inbox(self) -> List[Path]:
        """Finds all video files inside the inbox directory."""
        if not self.config.inbox_dir.exists():
            return []
        files = []
        for p in self.config.inbox_dir.iterdir():
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(p)
        return sorted(files, key=lambda f: f.name)

    def validate_clip(self, file_path: Path) -> DetectedClip:
        """Inspects file readability, size, hash, and checks for prior uploads."""
        is_readable = os.access(file_path, os.R_OK)
        file_size = file_path.stat().st_size if is_readable else 0

        file_hash = ""
        is_duplicate = False
        duplicate_info = None

        if is_readable and file_size > 0:
            file_hash = compute_sha256(file_path)
            prior = self.state.is_hash_uploaded(file_hash)
            if prior:
                is_duplicate = True
                duplicate_info = prior

        return DetectedClip(
            path=file_path,
            filename=file_path.name,
            file_hash=file_hash,
            file_size=file_size,
            is_readable=is_readable and file_size > 0,
            is_duplicate=is_duplicate,
            duplicate_info=duplicate_info,
        )

    def evaluate_daily_batch(self, date_str: Optional[str] = None) -> DetectionResult:
        """
        Evaluates the inbox against the strict daily 2-clip batch rule:
        - Must contain exactly 2 valid, un-uploaded clips.
        - If < 2: rejects partial upload, reports missing count.
        - If > 2: rejects arbitrary selection, reports ambiguity.
        - If duplicates exist: rejects and warns.
        """
        raw_files = self.scan_inbox()
        total_found = len(raw_files)

        validated: List[DetectedClip] = []
        duplicates: List[DetectedClip] = []
        corrupted: List[DetectedClip] = []

        for p in raw_files:
            clip_meta = self.validate_clip(p)
            if not clip_meta.is_readable:
                corrupted.append(clip_meta)
            elif clip_meta.is_duplicate:
                duplicates.append(clip_meta)
            else:
                validated.append(clip_meta)

        if corrupted:
            msg = f"Corrupted or empty video files detected in inbox: {[c.filename for c in corrupted]}"
            return DetectionResult(status="ERROR", message=msg, clips=corrupted)

        if duplicates:
            msg = (
                f"Duplicate video(s) detected that were already uploaded to YouTube: "
                f"{[(c.filename, c.duplicate_info['youtube_video_id']) for c in duplicates]}"
            )
            return DetectionResult(
                status="DUPLICATE_DETECTED", message=msg, clips=duplicates
            )

        target_count = self.config.daily_clip_count
        if len(validated) < target_count:
            msg = (
                f"Batch incomplete: Found {len(validated)} valid clip(s) in inbox, "
                f"but {target_count} clips are required for daily batch."
            )
            return DetectionResult(status="INSUFFICIENT", message=msg, clips=validated)

        if len(validated) > target_count and not self.config.allow_deterministic_excess:
            msg = (
                f"Batch ambiguous: Found {len(validated)} valid clips in inbox, "
                f"but daily batch requires exactly {target_count} clips. "
                f"Ambiguous candidates: {[c.filename for c in validated]}. "
                f"Please leave exactly {target_count} clips in inbox or enable 'allow_deterministic_excess' in settings.json."
            )
            return DetectionResult(status="AMBIGUOUS_BATCH", message=msg, clips=validated)

        # Select exactly target_count (2) clips for today's batch in deterministic FIFO order (oldest staged first)
        # Any remaining clips stay in inbox for tomorrow's batch if allow_deterministic_excess is active.
        validated_sorted = sorted(
            validated,
            key=lambda c: (c.path.stat().st_mtime if c.path.exists() else 0, c.filename),
        )
        selected_clips = validated_sorted[:target_count]
        remaining_count = len(validated_sorted) - target_count

        tz = timezone(timedelta(hours=self.config.utc_offset_hours))
        today_date = date_str or datetime.now(tz).strftime("%Y-%m-%d")
        timestamp_str = datetime.now(tz).strftime("%Y%m%d_%H%M%S")
        batch_id = f"batch_{today_date}_{timestamp_str}"

        msg = f"Successfully queued {target_count} clip(s) for daily batch {batch_id}."
        if remaining_count > 0:
            msg += f" ({remaining_count} additional clip(s) safely retained in inbox for upcoming days)."

        return DetectionResult(
            status="READY",
            message=msg,
            clips=selected_clips,
            batch_id=batch_id,
            remaining_count=remaining_count,
        )

    def stage_batch(self, detection: DetectionResult) -> Tuple[str, List[Path]]:
        """
        Atomically moves verified clips from inbox/ into processing/<batch_id>/,
        registers batch and clips in persistent state manager.
        """
        if detection.status != "READY" or not detection.batch_id:
            raise ValueError(f"Cannot stage batch with status {detection.status}: {detection.message}")

        batch_id = detection.batch_id
        batch_processing_dir = self.config.processing_dir / batch_id
        batch_processing_dir.mkdir(parents=True, exist_ok=True)

        today_date = batch_id.split("_")[1] if len(batch_id.split("_")) > 1 else datetime.now(timezone(timedelta(hours=self.config.utc_offset_hours))).strftime("%Y-%m-%d")
        self.state.create_batch(batch_id, today_date, len(detection.clips))

        staged_paths: List[Path] = []
        for idx, clip in enumerate(detection.clips, start=1):
            clip_id = f"{batch_id}_clip_{idx:02d}"
            target_path = batch_processing_dir / clip.filename
            shutil.move(str(clip.path), str(target_path))
            staged_paths.append(target_path)

            self.state.register_clip(
                clip_id=clip_id,
                batch_id=batch_id,
                original_filename=clip.filename,
                file_hash=clip.file_hash,
                file_size=clip.file_size,
            )

        self.state.log(batch_id, "INFO", f"Staged {len(staged_paths)} clips into {batch_processing_dir}")
        return batch_id, staged_paths
