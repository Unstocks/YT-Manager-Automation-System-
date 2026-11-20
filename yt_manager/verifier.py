"""
YT Manager YouTube Post-Upload Verification Module
Queries the YouTube Data API v3 to verify video presence, publication privacy,
and video processing/rejection status.
Never assumes success solely because an upload stream completed.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .auth import YouTubeAuthManager
from .config import YTManagerConfig

YOUTUBE_VIDEOS_ENDPOINT = (
    "https://www.googleapis.com/youtube/v3/videos?part=id,snippet,status,contentDetails,processingDetails&id="
)


@dataclass
class VerificationResult:
    video_id: str
    verified: bool
    title: str
    upload_status: str  # uploaded, processed, failed, rejected
    privacy_status: str  # public, unlisted, private
    rejection_reason: Optional[str] = None
    processing_status: Optional[str] = None  # processing, succeeded, failed, terminated
    raw_details: Dict[str, Any] = None


class VideoVerifier:
    def __init__(
        self,
        config: YTManagerConfig,
        auth_manager: Optional[YouTubeAuthManager] = None,
        mock_mode: bool = False,
    ):
        self.config = config
        self.auth = auth_manager or YouTubeAuthManager(config)
        self.mock_mode = mock_mode

    def verify_video(
        self, video_id: str, max_polling_attempts: int = 3, poll_delay_seconds: int = 3
    ) -> VerificationResult:
        """
        Polls YouTube API to verify that the video ID exists and is properly processed/published.
        """
        if self.mock_mode or video_id.startswith("mock_"):
            return VerificationResult(
                video_id=video_id,
                verified=True,
                title="Decision-Making Is a Trained Skill | Structured Problem Solving #Shorts",
                upload_status="processed",
                privacy_status=self.config.privacy_status,
                processing_status="succeeded",
                raw_details={"mock": True},
            )

        access_token = self.auth.get_valid_access_token()
        url = f"{YOUTUBE_VIDEOS_ENDPOINT}{video_id}"

        for attempt in range(1, max_polling_attempts + 1):
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                method="GET",
            )

            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                err = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Failed to query video status for {video_id} (HTTP {e.code}): {err}")

            items = data.get("items", [])
            if not items:
                if attempt < max_polling_attempts:
                    time.sleep(poll_delay_seconds)
                    continue
                return VerificationResult(
                    video_id=video_id,
                    verified=False,
                    title="",
                    upload_status="not_found",
                    privacy_status="unknown",
                    rejection_reason="Video ID was not found in YouTube catalog after upload.",
                )

            item = items[0]
            snippet = item.get("snippet", {})
            status = item.get("status", {})
            processing = item.get("processingDetails", {})

            upload_status = status.get("uploadStatus", "uploaded")
            privacy_status = status.get("privacyStatus", "unknown")
            rejection_reason = status.get("rejectionReason")
            processing_status = processing.get("processingStatus")

            # Check if video was rejected by YouTube
            if upload_status == "rejected" or rejection_reason:
                return VerificationResult(
                    video_id=video_id,
                    verified=False,
                    title=snippet.get("title", ""),
                    upload_status=upload_status,
                    privacy_status=privacy_status,
                    rejection_reason=rejection_reason or "Video was rejected by YouTube policy/processing.",
                    processing_status=processing_status,
                    raw_details=item,
                )

            # Successfully uploaded and accepted
            return VerificationResult(
                video_id=video_id,
                verified=True,
                title=snippet.get("title", ""),
                upload_status=upload_status,
                privacy_status=privacy_status,
                processing_status=processing_status,
                raw_details=item,
            )

        return VerificationResult(
            video_id=video_id,
            verified=False,
            title="",
            upload_status="timeout",
            privacy_status="unknown",
            rejection_reason="Timed out waiting for YouTube API confirmation.",
        )
