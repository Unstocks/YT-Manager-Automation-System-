"""
YT Manager Configuration Module
Loads settings from config/settings.json, environment variables, or defaults.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class YTManagerConfig:
    # Target Channel Config
    channel_id: str = "UCT0tm0KSB2BlIjdY6uUZCeA"
    channel_url: str = "https://youtube.com/@unstocks"
    channel_name: str = "Unstocks"

    # Scheduling
    schedule_time: str = "18:00"  # 6:00 PM IST
    timezone: str = "Asia/Kolkata"
    utc_offset_hours: float = 5.5
    daily_clip_count: int = 2
    retry_interval_minutes: int = 15
    daily_cutoff_time: str = "23:59"

    # Directory Paths (Relative to YT-Manager root or absolute)
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    inbox_dir: Path = field(init=False)
    processing_dir: Path = field(init=False)
    uploaded_dir: Path = field(init=False)
    failed_dir: Path = field(init=False)
    logs_dir: Path = field(init=False)
    reports_dir: Path = field(init=False)
    metadata_dir: Path = field(init=False)
    config_dir: Path = field(init=False)
    data_dir: Path = field(init=False)

    # API & OAuth Config
    client_secrets_path: Path = field(init=False)
    token_path: Path = field(init=False)
    db_path: Path = field(init=False)
    privacy_status: str = "public"  # public | unlisted | private
    upload_chunk_size: int = 1024 * 1024 * 5  # 5 MB resumable chunks
    api_request_timeout: int = 60

    # AI & Metadata Options
    default_category_id: str = "28"  # 28: Science & Technology, 27: Education
    default_language: str = "en"
    gemini_api_key: str = ""
    allow_deterministic_excess: bool = False  # If False, reports ambiguity when >2 clips exist

    # Notification Config
    enable_toast_notifications: bool = True
    enable_console_notifications: bool = True
    webhook_url: str = ""

    # Pinterest Curation Config
    pinterest_board_url: str = ""

    # Creator First-Comment Config
    enable_creator_comment: bool = True
    creator_comment_template: str = ""

    # Viral & Format Hashtag Config for Shorts
    default_hashtags: List[str] = field(
        default_factory=lambda: ["Shorts", "ytshorts", "ShortsFeed", "fyp", "fypage", "viral"]
    )

    def __post_init__(self) -> None:
        self.inbox_dir = self.base_dir / "inbox"
        self.processing_dir = self.base_dir / "processing"
        self.uploaded_dir = self.base_dir / "uploaded"
        self.failed_dir = self.base_dir / "failed"
        self.logs_dir = self.base_dir / "logs"
        self.reports_dir = self.logs_dir / "reports"
        self.metadata_dir = self.base_dir / "metadata"
        self.config_dir = self.base_dir / "config"
        self.data_dir = self.base_dir / "data"

        self.client_secrets_path = self.config_dir / "client_secrets.json"
        self.token_path = self.config_dir / "token.json"
        self.db_path = self.data_dir / "yt_manager.db"

        # Ensure directories exist
        for d in [
            self.inbox_dir,
            self.processing_dir,
            self.uploaded_dir,
            self.failed_dir,
            self.logs_dir,
            self.reports_dir,
            self.metadata_dir,
            self.config_dir,
            self.data_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls, custom_config_path: Path | None = None) -> YTManagerConfig:
        """Load configuration from settings.json or defaults."""
        default_base = Path(__file__).resolve().parent.parent
        settings_file = custom_config_path or (default_base / "config" / "settings.json")

        loaded_data: Dict[str, Any] = {}
        if settings_file.exists():
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
            except Exception as e:
                print(f"[Config] Warning: Failed to parse {settings_file}: {e}")

        # Environment variable overrides
        env_channel_id = os.environ.get("YT_CHANNEL_ID")
        if env_channel_id:
            loaded_data["channel_id"] = env_channel_id

        env_privacy = os.environ.get("YT_PRIVACY_STATUS")
        if env_privacy:
            loaded_data["privacy_status"] = env_privacy

        env_gemini_key = os.environ.get("GEMINI_API_KEY")
        if env_gemini_key:
            loaded_data["gemini_api_key"] = env_gemini_key

        config = cls(
            channel_id=loaded_data.get("channel_id", "UCT0tm0KSB2BlIjdY6uUZCeA"),
            channel_url=loaded_data.get("channel_url", "https://youtube.com/@unstocks"),
            channel_name=loaded_data.get("channel_name", "Unstocks"),
            schedule_time=loaded_data.get("schedule_time", "18:00"),
            timezone=loaded_data.get("timezone", "Asia/Kolkata"),
            utc_offset_hours=float(loaded_data.get("utc_offset_hours", 5.5)),
            daily_clip_count=int(loaded_data.get("daily_clip_count", 2)),
            retry_interval_minutes=int(loaded_data.get("retry_interval_minutes", 15)),
            daily_cutoff_time=loaded_data.get("daily_cutoff_time", "23:59"),
            privacy_status=loaded_data.get("privacy_status", "public"),
            default_category_id=loaded_data.get("default_category_id", "28"),
            default_language=loaded_data.get("default_language", "en"),
            gemini_api_key=loaded_data.get("gemini_api_key", ""),
            allow_deterministic_excess=bool(loaded_data.get("allow_deterministic_excess", False)),
            enable_toast_notifications=bool(loaded_data.get("enable_toast_notifications", True)),
            enable_console_notifications=bool(loaded_data.get("enable_console_notifications", True)),
            webhook_url=loaded_data.get("webhook_url", ""),
            pinterest_board_url=loaded_data.get("pinterest_board_url", ""),
            enable_creator_comment=bool(loaded_data.get("enable_creator_comment", True)),
            creator_comment_template=str(loaded_data.get("creator_comment_template", "")),
            default_hashtags=list(
                loaded_data.get(
                    "default_hashtags",
                    ["Shorts", "ytshorts", "ShortsFeed", "fyp", "fypage", "viral"],
                )
            ),
        )
        return config

    def save_default_settings(self) -> None:
        """Write default settings.json if it doesn't already exist."""
        settings_file = self.config_dir / "settings.json"
        if not settings_file.exists():
            payload = {
                "channel_id": self.channel_id,
                "channel_url": self.channel_url,
                "channel_name": self.channel_name,
                "schedule_time": self.schedule_time,
                "timezone": self.timezone,
                "utc_offset_hours": self.utc_offset_hours,
                "daily_clip_count": self.daily_clip_count,
                "retry_interval_minutes": self.retry_interval_minutes,
                "daily_cutoff_time": self.daily_cutoff_time,
                "privacy_status": self.privacy_status,
                "default_category_id": self.default_category_id,
                "default_language": self.default_language,
                "allow_deterministic_excess": self.allow_deterministic_excess,
                "enable_toast_notifications": self.enable_toast_notifications,
                "enable_console_notifications": self.enable_console_notifications,
                "webhook_url": self.webhook_url,
                "pinterest_board_url": self.pinterest_board_url,
                "enable_creator_comment": self.enable_creator_comment,
                "creator_comment_template": self.creator_comment_template,
                "default_hashtags": self.default_hashtags,
            }
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4)
