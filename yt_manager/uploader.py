"""
YT Manager YouTube Data API v3 Resumable Upload Engine
Pure Python standard library implementation adhering to Google's official Resumable Upload protocol.
Features:
- Resumable chunked streaming (multiples of 256 KB).
- Interrupted upload resumption via HTTP 308 queries.
- Exponential backoff on transient network / 5xx server errors.
- Progress tracking callbacks (bytes transferred, percentage, elapsed time).
- Video ID extraction and upload response validation.
- Mock upload mode for dry runs, testing, and CI verification.
"""
from __future__ import annotations

import json
import mimetypes
import os
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .auth import YouTubeAuthManager
from .config import YTManagerConfig
from .metadata import VideoMetadata

RESUMABLE_UPLOAD_ENDPOINT = (
    "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
)

# Google Resumable Upload specification: Chunk sizes must be an exact multiple of 256 KB (262,144 bytes)
DEFAULT_CHUNK_SIZE = 256 * 1024 * 8  # 2 MB per chunk


@dataclass
class UploadResult:
    success: bool
    video_id: str
    youtube_url: str
    privacy_status: str
    bytes_uploaded: int
    duration_seconds: float
    raw_response: Dict[str, Any]
    error_message: Optional[str] = None


class YouTubeUploader:
    def __init__(
        self,
        config: YTManagerConfig,
        auth_manager: Optional[YouTubeAuthManager] = None,
        mock_mode: bool = False,
    ):
        self.config = config
        self.auth = auth_manager or YouTubeAuthManager(config)
        self.mock_mode = mock_mode

    def _initiate_resumable_session(
        self,
        video_path: Path,
        metadata: VideoMetadata,
        access_token: str,
        privacy_status: Optional[str] = None,
        publish_at: Optional[str] = None,
    ) -> str:
        """
        Sends initial metadata POST to YouTube API to obtain the unique resumable upload URL.
        Supports scheduled cloud publishing via publishAt parameter.
        """
        file_size = video_path.stat().st_size
        mime_type, _ = mimetypes.guess_type(str(video_path))
        mime_type = mime_type or "video/mp4"

        effective_privacy = privacy_status or self.config.privacy_status
        status_payload: Dict[str, Any] = {
            "privacyStatus": "private" if publish_at else effective_privacy,
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
        }
        if publish_at:
            status_payload["publishAt"] = publish_at

        body_payload = {
            "snippet": metadata.to_youtube_snippet_payload(),
            "status": status_payload,
        }

        req = urllib.request.Request(
            RESUMABLE_UPLOAD_ENDPOINT,
            data=json.dumps(body_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": mime_type,
                "X-Upload-Content-Length": str(file_size),
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.api_request_timeout) as resp:
                upload_url = resp.headers.get("Location")
                if not upload_url:
                    raise RuntimeError("YouTube API did not return a Location header for resumable upload.")
                return upload_url
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Failed to initiate YouTube upload session (HTTP {e.code}): {err_body}")

    def _query_resumable_offset(self, upload_url: str, total_size: int, access_token: str) -> int:
        """
        Queries YouTube for the last uploaded byte offset following an interrupted upload.
        """
        req = urllib.request.Request(
            upload_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Range": f"bytes */{total_size}",
                "Content-Length": "0",
            },
            method="PUT",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status in (200, 201):
                    return total_size
        except urllib.error.HTTPError as e:
            if e.code == 308:
                range_header = e.headers.get("Range")
                if range_header and range_header.startswith("bytes="):
                    _, end_byte = range_header.replace("bytes=", "").split("-")
                    return int(end_byte) + 1
                return 0
            raise
        return 0

    def upload_video(
        self,
        video_path: Path,
        metadata: VideoMetadata,
        progress_callback: Optional[Callable[[int, int, float], None]] = None,
        privacy_status: Optional[str] = None,
        publish_at: Optional[str] = None,
    ) -> UploadResult:
        """
        Performs the complete resumable upload of video_path with associated metadata.
        Optionally supports scheduled cloud publishing (publish_at).
        """
        start_time = time.time()
        file_size = video_path.stat().st_size

        if self.mock_mode:
            # Simulated high-fidelity mock upload for testing
            mock_id = f"mock_{metadata.clip_id}_{int(start_time)}"
            youtube_url = f"https://youtu.be/{mock_id}"

            # Simulate chunk progress
            step = max(file_size // 4, 1)
            for uploaded in range(0, file_size, step):
                if progress_callback:
                    progress_callback(uploaded, file_size, time.time() - start_time)
                time.sleep(0.05)

            if progress_callback:
                progress_callback(file_size, file_size, time.time() - start_time)

            return UploadResult(
                success=True,
                video_id=mock_id,
                youtube_url=youtube_url,
                privacy_status="private" if publish_at else (privacy_status or self.config.privacy_status),
                bytes_uploaded=file_size,
                duration_seconds=time.time() - start_time,
                raw_response={"id": mock_id, "mock": True, "publishAt": publish_at},
            )

        # 1. Channel verification & Auth
        identity = self.auth.verify_target_channel()
        access_token = self.auth.get_valid_access_token()

        # 2. Initiate resumable upload session
        upload_url = self._initiate_resumable_session(
            video_path, metadata, access_token, privacy_status=privacy_status, publish_at=publish_at
        )

        # 3. Stream chunks with resume capability
        chunk_size = DEFAULT_CHUNK_SIZE
        offset = 0
        retries = 0
        max_retries = 5

        with open(video_path, "rb") as f:
            while offset < file_size:
                f.seek(offset)
                chunk_data = f.read(chunk_size)
                chunk_len = len(chunk_data)
                end_byte = offset + chunk_len - 1

                content_range = f"bytes {offset}-{end_byte}/{file_size}"
                req = urllib.request.Request(
                    upload_url,
                    data=chunk_data,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/octet-stream",
                        "Content-Length": str(chunk_len),
                        "Content-Range": content_range,
                    },
                    method="PUT",
                )

                try:
                    with urllib.request.urlopen(req, timeout=self.config.api_request_timeout) as resp:
                        if resp.status in (200, 201):
                            resp_json = json.loads(resp.read().decode("utf-8"))
                            video_id = resp_json.get("id", "")
                            youtube_url = f"https://youtu.be/{video_id}"
                            duration = time.time() - start_time

                            if progress_callback:
                                progress_callback(file_size, file_size, duration)

                            return UploadResult(
                                success=True,
                                video_id=video_id,
                                youtube_url=youtube_url,
                                privacy_status=resp_json.get("status", {}).get("privacyStatus", "public"),
                                bytes_uploaded=file_size,
                                duration_seconds=duration,
                                raw_response=resp_json,
                            )
                except urllib.error.HTTPError as e:
                    if e.code == 308:
                        # Resume Incomplete: parse Range header
                        range_header = e.headers.get("Range")
                        if range_header and range_header.startswith("bytes="):
                            _, last_b = range_header.replace("bytes=", "").split("-")
                            offset = int(last_b) + 1
                        else:
                            offset += chunk_len
                        retries = 0
                        if progress_callback:
                            progress_callback(offset, file_size, time.time() - start_time)
                        continue

                    # Server error or rate limit
                    if e.code in (500, 502, 503, 504, 429) and retries < max_retries:
                        retries += 1
                        backoff = (2 ** retries) + random.uniform(0.1, 1.0)
                        time.sleep(backoff)
                        # Re-query offset
                        try:
                            offset = self._query_resumable_offset(upload_url, file_size, access_token)
                        except Exception:
                            pass
                        continue

                    err_body = e.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"YouTube upload failed at offset {offset} (HTTP {e.code}): {err_body}")

                except (urllib.error.URLError, TimeoutError, OSError) as e:
                    if retries < max_retries:
                        retries += 1
                        backoff = (2 ** retries) + random.uniform(0.1, 1.0)
                        time.sleep(backoff)
                        try:
                            offset = self._query_resumable_offset(upload_url, file_size, access_token)
                        except Exception:
                            pass
                        continue
                    raise RuntimeError(f"Network error during upload at offset {offset}: {e}")

        raise RuntimeError("Upload ended unexpectedly without server confirmation.")

    def post_comment(self, video_id: str, text: str) -> Optional[str]:
        """
        Posts a creator top-level comment on the uploaded video to boost early engagement.
        Returns the comment ID if successful, or None if failed/mocked.
        """
        if not video_id or not text.strip():
            return None

        if self.mock_mode:
            return f"mock_comment_{video_id}"

        try:
            token = self.auth.get_valid_access_token()
            url = "https://www.googleapis.com/youtube/v3/commentThreads?part=snippet"
            payload = {
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": text
                        }
                    }
                }
            }
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.config.api_request_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("id")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            if e.code == 403 and "insufficientPermissions" in err_body:
                print("\n[Comment] Note: Automatic comment posting requires 'youtube.force-ssl' scope.")
                print("[Comment] Run 'python -m yt_manager auth' to re-authenticate with comment permissions.\n")
            return None
        except Exception:
            return None
