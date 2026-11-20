"""
YT Manager Notification Engine
Provides lightweight, reliable notifications:
- Windows Native Toast Notifications (via PowerShell WinRT API).
- Console alerting with clear visual banners.
- Persistent file and database logging.
- Optional outgoing HTTP Webhook (Discord/Slack/Telegram) when configured.
"""
from __future__ import annotations

import json
import logging
import subprocess
import urllib.request
from datetime import datetime
from typing import Optional

from .config import YTManagerConfig
from .state import StateManager


class Notifier:
    def __init__(self, config: YTManagerConfig, state: Optional[StateManager] = None):
        self.config = config
        self.state = state

        # Configure file logger
        self.log_file = self.config.logs_dir / "yt_manager.log"
        self.logger = logging.getLogger("YTManager")
        self.logger.setLevel(logging.INFO)

        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file, encoding="utf-8")
            fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
            handler.setFormatter(fmt)
            self.logger.addHandler(handler)

    def _send_windows_toast(self, title: str, message: str) -> None:
        """Sends native Windows 10/11 desktop toast notification via PowerShell."""
        if not self.config.enable_toast_notifications:
            return

        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        `$template = @"
<toast>
    <visual>
        <binding template="ToastGeneric">
            <text>{title}</text>
            <text>{message}</text>
        </binding>
    </visual>
</toast>
"@
        `$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        `$xml.LoadXml(`$template)
        `$toast = [Windows.UI.Notifications.ToastNotification]::new(`$xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("YT Manager").Show(`$toast)
        """
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                timeout=5,
            )
        except Exception:
            # Non-fatal if desktop toasts are disabled by group policy or unattended environment
            pass

    def _send_webhook(self, title: str, message: str, level: str) -> None:
        """Sends lightweight webhook message if configured (supports Discord, Telegram, Slack, and generic webhooks)."""
        if not self.config.webhook_url:
            return

        url = self.config.webhook_url.strip()
        try:
            # 1. Discord Webhook
            if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
                color_map = {
                    "INFO": 0x3498DB,     # Blue
                    "SUCCESS": 0x2ECC71,  # Green
                    "WARNING": 0xF1C40F,  # Amber
                    "ERROR": 0xE74C3C,    # Red
                }
                embed = {
                    "title": f"YT Manager: {title}",
                    "description": message,
                    "color": color_map.get(level, 0x3498DB),
                    "footer": {"text": "Unstocks YT-Manager Automation"},
                    "timestamp": datetime.now().isoformat(),
                }
                payload = {"embeds": [embed]}
            # 2. Telegram Bot Webhook
            elif "api.telegram.org" in url:
                payload = {
                    "text": f"<b>YT Manager: {title}</b>\n\n{message}",
                    "parse_mode": "HTML",
                }
            # 3. Generic Webhook (Slack / custom HTTP receiver)
            else:
                payload = {
                    "title": f"YT Manager: {title}",
                    "text": f"*{title}*\n{message}",
                    "level": level,
                    "timestamp": datetime.now().isoformat(),
                }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "YT-Manager-Notifier/1.0"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            self.logger.warning(f"Webhook dispatch failed: {e}")

    def notify(
        self,
        event: str,
        title: str,
        message: str,
        level: str = "INFO",
        batch_id: Optional[str] = None,
    ) -> None:
        """Central notification dispatch."""
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Console display
        if self.config.enable_console_notifications:
            prefix = "[INFO]" if level == "INFO" else f"[{level}]"
            print(f"[{timestamp_str}] {prefix} {title} :: {message}")

        # 2. File & Database Logging
        if level == "ERROR":
            self.logger.error(f"{title}: {message}")
        elif level == "WARNING":
            self.logger.warning(f"{title}: {message}")
        else:
            self.logger.info(f"{title}: {message}")

        if self.state:
            self.state.log(batch_id, level, f"{title}: {message}")

        # 3. Windows Native Toast
        self._send_windows_toast(f"YT Manager: {title}", message)

        # 4. Webhook (if enabled)
        self._send_webhook(title, message, level)

    def notify_inbox_incomplete(self, current_count: int, required_count: int) -> None:
        self.notify(
            event="INBOX_INCOMPLETE",
            title="Batch Incomplete - Clips Missing",
            message=f"Found {current_count}/{required_count} clips in inbox. Waiting for 2 clips before starting.",
            level="WARNING",
        )

    def notify_processing_started(self, batch_id: str, count: int) -> None:
        self.notify(
            event="PROCESSING_STARTED",
            title="Daily Automation Started",
            message=f"Batch {batch_id}: Processing {count} video clips for upload.",
            level="INFO",
            batch_id=batch_id,
        )

    def notify_upload_completed(self, batch_id: str, successful: int) -> None:
        self.notify(
            event="UPLOAD_COMPLETED",
            title="Uploads Successful",
            message=f"Batch {batch_id}: All {successful} videos successfully uploaded and verified on YouTube!",
            level="INFO",
            batch_id=batch_id,
        )

    def notify_upload_failed(self, batch_id: str, clip_name: str, error: str) -> None:
        self.notify(
            event="UPLOAD_FAILED",
            title="Upload Failed",
            message=f"Failed to upload {clip_name}: {error}",
            level="ERROR",
            batch_id=batch_id,
        )

    def notify_auth_required(self) -> None:
        self.notify(
            event="AUTH_REQUIRED",
            title="YouTube Authentication Required",
            message="Valid OAuth credentials not found. Run 'python -m yt_manager auth' to connect your channel.",
            level="ERROR",
        )

    def notify_quota_exceeded(self) -> None:
        self.notify(
            event="QUOTA_EXCEEDED",
            title="YouTube API Quota Exceeded",
            message="Daily YouTube API quota limit reached. Execution postponed until quota resets at midnight PST.",
            level="ERROR",
        )
