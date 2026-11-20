"""
YT Manager Telegram Ingestion Engine
Allows the creator to deposit video clips directly from their smartphone into inbox/
via a private Telegram Bot, receive real-time status confirmations, and trigger uploads.
Operates using pure Python standard library (urllib.request) with zero pip dependencies.
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import YTManagerConfig
from .inspector import MediaInspector

logger = logging.getLogger("YTManager.Telegram")


class TelegramIngestionBot:
    def __init__(self, config: Optional[YTManagerConfig] = None):
        self.config = config or YTManagerConfig.load()
        self.token = self.config.telegram_bot_token.strip()
        self.chat_id = str(self.config.telegram_chat_id).strip()
        self.inspector = MediaInspector()
        self.last_update_id = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.token and len(self.token) > 15 and ":" in self.token)

    @property
    def base_url(self) -> str:
        return f"https://api.telegram.org/bot{self.token}"

    @property
    def file_base_url(self) -> str:
        return f"https://api.telegram.org/file/bot{self.token}"

    def send_message(self, chat_id: str, text: str, parse_mode: str = "Markdown") -> bool:
        """Sends a text message back to the user on Telegram."""
        if not self.is_configured:
            return False

        endpoint = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Failed to send Telegram message to {chat_id}: {e}")
            return False

    def get_updates(self, offset: Optional[int] = None, timeout: int = 5) -> List[Dict[str, Any]]:
        """Polls for new incoming messages from Telegram."""
        if not self.is_configured:
            return []

        url = f"{self.base_url}/getUpdates?timeout={timeout}"
        if offset is not None:
            url += f"&offset={offset}"

        req = urllib.request.Request(url, headers={"User-Agent": "YT-Manager-Telegram/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout + 5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    return data.get("result", [])
                return []
        except Exception as e:
            logger.debug(f"Telegram getUpdates poll failed: {e}")
            return []

    def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Fetches file metadata and download path from Telegram."""
        endpoint = f"{self.base_url}/getFile?file_id={file_id}"
        req = urllib.request.Request(endpoint, headers={"User-Agent": "YT-Manager-Telegram/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    return data.get("result")
                return None
        except Exception as e:
            logger.warning(f"Failed to fetch Telegram file info for {file_id}: {e}")
            return None

    def download_file(self, file_path: str, dest_path: Path) -> bool:
        """Downloads the video file from Telegram servers in streaming chunks."""
        url = f"{self.file_base_url}/{file_path}"
        req = urllib.request.Request(url, headers={"User-Agent": "YT-Manager-Telegram/1.0"})
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                with open(dest_path, "wb") as f:
                    while chunk := resp.read(65536):
                        f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"Failed downloading Telegram file {file_path} to {dest_path}: {e}")
            if dest_path.exists():
                try:
                    dest_path.unlink()
                except Exception:
                    pass
            return False

    def handle_message(self, message: Dict[str, Any]) -> Optional[Path]:
        """
        Processes a single incoming Telegram message:
        - Auto-pairs chat_id on first interaction if unconfigured.
        - Enforces security: rejects unauthorized senders.
        - Handles commands: /start, /status, /run, /help.
        - Ingests video clips and deposits them into inbox/.
        """
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        from_user = message.get("from", {}).get("first_name", "Creator")
        if not chat_id:
            return None

        # 1. Pairing and Security Verification
        if not self.chat_id:
            # Auto-pair with first user message
            self.chat_id = chat_id
            self.config.update_setting("telegram_chat_id", chat_id)
            welcome_text = (
                f"🎉 *YT Manager Bot Paired Successfully!*\n\n"
                f"Hello {from_user}! This bot is now locked exclusively to your Telegram account (`{chat_id}`).\n\n"
                f"📱 *Mobile Uploads Enabled:*\n"
                f"Whenever you have video clips on your phone, simply attach and send them here. "
                f"They will be downloaded directly into your laptop's `inbox/` for the 5:00 PM IST upload batch!\n\n"
                f"Commands:\n"
                f"• `/status` — View current inbox count and queue\n"
                f"• `/run` — Trigger upload batch right now\n"
                f"• `/help` — Show help commands"
            )
            self.send_message(chat_id, welcome_text)
            return None

        # Enforce single-operator security
        if chat_id != self.chat_id:
            logger.warning(f"Rejected unauthorized Telegram message from chat_id {chat_id}")
            self.send_message(chat_id, "⛔ *Unauthorized Access.* This is a private channel automation bot.")
            return None

        text = (message.get("text") or message.get("caption") or "").strip()

        # 2. Text Commands Handling
        if text.startswith("/"):
            cmd = text.split()[0].lower()
            if cmd == "/start" or cmd == "/help":
                help_text = (
                    f"🎬 *Unstocks YT Manager Bot*\n\n"
                    f"Send me any `.mp4` or `.mov` video to queue it for daily YouTube upload!\n\n"
                    f"*Commands:*\n"
                    f"• `/status` — View inbox clips, channel match, and schedule\n"
                    f"• `/run` — Force daily batch execution now\n"
                    f"• `/help` — Show this message"
                )
                self.send_message(chat_id, help_text)
                return None

            elif cmd == "/status":
                inbox_clips = sorted(
                    [f for f in self.config.inbox_dir.iterdir() if f.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")],
                    key=lambda f: f.stat().st_mtime,
                )
                status_lines = [
                    f"📊 *YT Manager System Status*",
                    f"🎯 *Channel:* {self.config.channel_name}",
                    f"⏰ *Schedule:* {self.config.schedule_time} {self.config.timezone} Daily",
                    f"📁 *Inbox Count:* {len(inbox_clips)} / {self.config.daily_clip_count} required",
                    "",
                ]
                if inbox_clips:
                    status_lines.append("*Clips in Queue:*")
                    for c in inbox_clips:
                        size_mb = c.stat().st_size / 1024 / 1024
                        status_lines.append(f"• `{c.name}` ({size_mb:.1f} MB)")
                else:
                    status_lines.append("📭 _Inbox is currently empty._")

                if len(inbox_clips) == self.config.daily_clip_count:
                    status_lines.append("\n✅ *Batch is READY for daily upload!*")
                elif len(inbox_clips) < self.config.daily_clip_count:
                    needed = self.config.daily_clip_count - len(inbox_clips)
                    status_lines.append(f"\n⏳ Need {needed} more clip(s).")
                else:
                    status_lines.append(f"\n⚠️ Excess clips ({len(inbox_clips)}). System will process oldest 2 if configured.")

                self.send_message(chat_id, "\n".join(status_lines))
                return None

            elif cmd == "/run":
                self.send_message(chat_id, "🚀 *Starting daily YouTube batch workflow...*\nPlease wait while clips are processed and verified.")
                try:
                    from .orchestrator import WorkflowOrchestrator
                    orchestrator = WorkflowOrchestrator(self.config)
                    report = orchestrator.run_daily_batch(force=True)
                    result_text = (
                        f"🏁 *Batch Execution Finished!*\n"
                        f"Status: *{report.execution_status}*\n"
                        f"Uploaded: *{report.successfully_uploaded} / {report.clips_received}* videos\n"
                    )
                    if report.clips:
                        result_text += "\n*Uploaded Videos:*\n"
                        for c in report.clips:
                            if c.upload_status == "SUCCESS":
                                result_text += f"• [{c.generated_title}]({c.youtube_url})\n"
                    self.send_message(chat_id, result_text)
                except Exception as e:
                    self.send_message(chat_id, f"❌ *Batch Execution Error:* {e}")
                return None

        # 3. Video / Document Ingestion
        video_obj = message.get("video")
        doc_obj = message.get("document")

        target_file_id = None
        orig_filename = None

        if video_obj:
            target_file_id = video_obj.get("file_id")
            orig_filename = video_obj.get("file_name") or f"mobile_clip_{int(time.time())}.mp4"
        elif doc_obj:
            mime = doc_obj.get("mime_type", "")
            fname = doc_obj.get("file_name", "")
            if mime.startswith("video/") or fname.lower().endswith((".mp4", ".mov", ".webm", ".mkv")):
                target_file_id = doc_obj.get("file_id")
                orig_filename = fname or f"mobile_clip_{int(time.time())}.mp4"

        if not target_file_id:
            # Not a video file, acknowledge politely
            self.send_message(
                chat_id,
                "💡 Send me a video file from your phone to add it directly to today's YouTube queue."
            )
            return None

        # Check Telegram Bot API 20MB limit
        file_size = (video_obj or doc_obj).get("file_size", 0)
        if file_size > 20 * 1024 * 1024:
            size_mb = file_size / (1024 * 1024)
            self.send_message(
                chat_id,
                f"⚠️ *File is too large ({size_mb:.1f} MB)*\n\n"
                f"Telegram cloud limits bot downloads to 20 MB per file.\n\n"
                f"💡 *Tips to keep maximum quality:*\n"
                f"• For Shorts (15–60s), export at 1080p 30fps / 10–12 Mbps bitrate (usually ~10–18 MB).\n"
                f"• Or send as a standard Gallery video so Telegram optimizes it to fit."
            )
            return None

        # Sanitize filename
        clean_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', orig_filename)
        if not clean_name.lower().endswith((".mp4", ".mov", ".webm", ".mkv")):
            clean_name += ".mp4"

        dest_file = self.config.inbox_dir / clean_name
        if dest_file.exists():
            clean_name = f"{dest_file.stem}_{int(time.time())}{dest_file.suffix}"
            dest_file = self.config.inbox_dir / clean_name

        self.send_message(chat_id, f"⏳ *Downloading '{clean_name}'* from phone...")

        # Fetch file path from Telegram
        file_info = self.get_file_info(target_file_id)
        if not file_info or "file_path" not in file_info:
            self.send_message(chat_id, f"❌ Failed to locate video file on Telegram servers.")
            return None

        remote_path = file_info["file_path"]
        success = self.download_file(remote_path, dest_file)
        if not success:
            self.send_message(chat_id, f"❌ Download failed for '{clean_name}'. Please try sending again.")
            return None

        # Probe video using MediaInspector
        try:
            inspection = self.inspector.probe(dest_file)
            dur = inspection.duration_seconds
            res = f"{inspection.width}x{inspection.height}"
            fmt = "9:16 Shorts" if inspection.is_short else "Landscape"
        except Exception:
            dur = 0.0
            res = "Unknown"
            fmt = "Video"

        size_mb = (dest_file.stat().st_size / 1024 / 1024) if dest_file.exists() else 0.0
        inbox_count = len(
            [f for f in self.config.inbox_dir.iterdir() if f.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")]
        )

        reply_msg = (
            f"✅ *Clip Successfully Staged!*\n\n"
            f"🎬 *File:* `{clean_name}`\n"
            f"📏 *Format:* {fmt} ({res}) | {dur:.1f}s | {size_mb:.1f} MB\n\n"
            f"📊 *Inbox Queue:* {inbox_count} / {self.config.daily_clip_count} clips ready\n"
        )
        if inbox_count == self.config.daily_clip_count:
            reply_msg += "🎉 *Daily batch is now READY for 5:00 PM upload!*"
        elif inbox_count < self.config.daily_clip_count:
            reply_msg += f"⏳ Send {self.config.daily_clip_count - inbox_count} more clip to complete today's batch."
        else:
            reply_msg += f"ℹ️ You have {inbox_count} clips queued in inbox."

        self.send_message(chat_id, reply_msg)
        logger.info(f"Telegram ingested video: {clean_name} ({size_mb:.1f} MB)")
        return dest_file

    def poll_once(self) -> int:
        """Polls for new Telegram updates and processes them. Returns count of ingested clips."""
        if not self.is_configured:
            return 0

        updates = self.get_updates(offset=self.last_update_id + 1 if self.last_update_id else None)
        ingested = 0
        for upd in updates:
            upd_id = upd.get("update_id", 0)
            if upd_id > self.last_update_id:
                self.last_update_id = upd_id

            msg = upd.get("message")
            if msg:
                saved_path = self.handle_message(msg)
                if saved_path:
                    ingested += 1

        return ingested

    def run_polling_loop(self, interval: float = 3.0, run_once: bool = False) -> None:
        """Runs the continuous polling listener for mobile video uploads."""
        if not self.is_configured:
            print("[Telegram] Bot token is not configured. Please set 'telegram_bot_token' in settings.json.")
            return

        print(f"\n[Telegram] Bot listener active for @unstocks_manager_bot")
        print(f"[Telegram] Listening for mobile video uploads into: {self.config.inbox_dir}")
        print("[Telegram] Press Ctrl+C to stop.\n")

        while True:
            try:
                self.poll_once()
                if run_once:
                    break
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\n[Telegram] Listener stopped by user.")
                break
            except Exception as e:
                logger.warning(f"[Telegram] Polling error: {e}")
                time.sleep(interval)
