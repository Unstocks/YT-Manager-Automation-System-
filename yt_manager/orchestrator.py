"""
YT Manager Workflow Orchestrator Module
Coordinates the entire daily automation lifecycle from inbox ingestion to upload verification:
1. Detects & validates exactly 2 clips.
2. Inspects media & extracts frames/audio.
3. Performs AI content understanding.
4. Generates SEO titles, descriptions, tags, hashtags.
5. Uploads Video 1 & verifies Video 1.
6. Uploads Video 2 & verifies Video 2.
7. Saves records, moves completed files to uploaded/, moves failed to failed/.
8. Generates Daily Execution Report and dispatches notifications.
"""
from __future__ import annotations

import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .auth import ChannelMismatchError, YouTubeAuthManager
from .config import YTManagerConfig
from .detector import ClipDetector, DetectionResult
from .inspector import MediaInspector
from .metadata import SEOMetadataGenerator, VideoMetadata
from .notifier import Notifier
from .reporter import ClipExecutionReport, DailyBatchReport, ReportGenerator
from .state import StateManager
from .transformer import MediaTransformer
from .understanding import ContentUnderstanding, VideoUnderstandingEngine
from .uploader import YouTubeUploader
from .verifier import VideoVerifier


def check_network_connectivity(timeout: float = 3.0) -> bool:
    """Verifies that the machine has an active internet connection to YouTube/Google."""
    import socket
    for host in ("8.8.8.8", "1.1.1.1", "www.youtube.com"):
        try:
            port = 53 if host[0].isdigit() else 443
            socket.create_connection((host, port), timeout=timeout).close()
            return True
        except (socket.timeout, OSError):
            continue
    return False


def wait_for_network_connectivity(max_wait_seconds: int = 30, interval: float = 5.0) -> bool:
    """Waits up to max_wait_seconds for Wi-Fi / Internet connection to become available after system wake/boot."""
    import time
    if check_network_connectivity(timeout=2.0):
        return True
    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        time.sleep(interval)
        if check_network_connectivity(timeout=2.0):
            return True
    return False


class WorkflowOrchestrator:
    def __init__(
        self,
        config: Optional[YTManagerConfig] = None,
        mock_mode: bool = False,
    ):
        self.config = config or YTManagerConfig.load()
        self.mock_mode = mock_mode

        self.state = StateManager(self.config.db_path)
        self.detector = ClipDetector(self.config, self.state)
        self.transformer = MediaTransformer(self.config)
        self.inspector = MediaInspector()
        self.understanding_engine = VideoUnderstandingEngine(self.config.gemini_api_key)
        self.metadata_generator = SEOMetadataGenerator(self.config)
        self.auth = YouTubeAuthManager(self.config)
        self.uploader = YouTubeUploader(self.config, self.auth, mock_mode=self.mock_mode)
        self.verifier = VideoVerifier(self.config, self.auth, mock_mode=self.mock_mode)
        self.notifier = Notifier(self.config, self.state)
        self.reporter = ReportGenerator(self.config)

    def run_daily_batch(
        self, force_date: Optional[str] = None, force: bool = False
    ) -> DailyBatchReport:
        """
        Executes the daily batch workflow in IST (UTC+05:30):
        1. Pre-flight network health check.
        2. Daily active window & midnight cutoff check (e.g. 18:00 to 23:59 IST).
           - Executes if opened anytime in the active window (including 30 or 10 min before 12:00 AM).
           - If upload fails, clips are safely returned to inbox/ queue.
           - After 12:00 AM midnight (past 23:59), cleanly shifts to the next day's execution.
        3. Idempotent check for already completed batch today.
        4. Detects clips, stages them, uploads to YouTube, verifies, and archives.
        """
        tz = timezone(timedelta(hours=self.config.utc_offset_hours))
        now_ist = datetime.now(tz)
        today_ist = force_date or now_ist.strftime("%d %B %Y")
        today_date_str = force_date or now_ist.strftime("%Y-%m-%d")

        # 1. Pre-flight Network Health Check with 30s Wi-Fi handshake grace period (Skip in mock/test mode)
        if not self.mock_mode and not wait_for_network_connectivity(max_wait_seconds=30):
            offline_msg = "No internet connection detected after 30s grace period. Batch deferred until network connectivity is restored."
            self.notifier.notify(
                event="NETWORK_OFFLINE",
                title="Network Offline — Batch Deferred",
                message=offline_msg,
                level="WARNING",
            )
            return DailyBatchReport(
                execution_date=today_ist,
                scheduled_time=f"{self.config.schedule_time} {self.config.timezone}",
                clips_received=0,
                metadata_generated=0,
                successfully_uploaded=0,
                failed=0,
                execution_status="DEFERRED (OFFLINE)",
                failure_details=offline_msg,
                required_action="Connect laptop to Wi-Fi/Internet; system will automatically resume on next trigger.",
            )

        # 2. Daily Active Window & Midnight Cutoff Check
        if not self.mock_mode and not force and not force_date:
            target_hour, target_min = map(int, self.config.schedule_time.split(":"))
            cutoff_hour, cutoff_min = map(int, self.config.daily_cutoff_time.split(":"))
            current_minutes = now_ist.hour * 60 + now_ist.minute
            target_minutes = target_hour * 60 + target_min
            cutoff_minutes = cutoff_hour * 60 + cutoff_min

            if not (target_minutes <= current_minutes <= cutoff_minutes):
                time_str = now_ist.strftime("%H:%M")
                window_msg = (
                    f"Current time ({time_str} IST) is outside the daily broadcasting window "
                    f"({self.config.schedule_time} – {self.config.daily_cutoff_time} IST). "
                    f"Execution safely shifted to today's {self.config.schedule_time} IST window."
                )
                self.notifier.notify(
                    event="WINDOW_DEFERRED",
                    title="Execution Window Inactive",
                    message=window_msg,
                    level="INFO",
                )
                return DailyBatchReport(
                    execution_date=today_ist,
                    scheduled_time=f"{self.config.schedule_time} {self.config.timezone}",
                    clips_received=0,
                    metadata_generated=0,
                    successfully_uploaded=0,
                    failed=0,
                    execution_status="DEFERRED (OUTSIDE_WINDOW)",
                    failure_details=window_msg,
                    required_action=f"Clips remain safely queued in inbox; execution will automatically trigger during {self.config.schedule_time} – {self.config.daily_cutoff_time} IST.",
                )

        # 3. Check for already completed batch today (Duplicate-run protection)
        existing_batch = self.state.get_batch_for_date(today_date_str)
        if existing_batch and existing_batch["status"] == "COMPLETED":
            self.notifier.notify(
                event="ALREADY_COMPLETED",
                title="Daily Batch Already Completed",
                message=f"A successful batch {existing_batch['id']} has already executed for {today_date_str}.",
                level="INFO",
            )
            report = DailyBatchReport(
                execution_date=today_ist,
                scheduled_time=f"{self.config.schedule_time} {self.config.timezone}",
                clips_received=0,
                metadata_generated=0,
                successfully_uploaded=0,
                failed=0,
                execution_status="COMPLETED (PRIOR RUN)",
            )
            return report

        # 2. Check Daily Input Folder & Validate
        detection = self.detector.evaluate_daily_batch(date_str=today_date_str)

        # Pre-flight auto-harvest from Pinterest board if inbox is insufficient
        if detection.status == "INSUFFICIENT" and self.config.pinterest_board_url:
            missing_count = self.config.daily_clip_count - len(detection.clips)
            try:
                from .pinterest_harvester import PinterestHarvester
                harvester = PinterestHarvester(self.config, self.state)
                harvested = harvester.run_pre_upload_harvest(
                    board_url=self.config.pinterest_board_url,
                    target_count=missing_count,
                )
                if harvested:
                    self.state.log(
                        None,
                        "INFO",
                        f"Auto-harvested {len(harvested)} clip(s) from Pinterest board {self.config.pinterest_board_url}",
                    )
                    detection = self.detector.evaluate_daily_batch(date_str=today_date_str)
            except Exception as e:
                self.state.log(None, "WARNING", f"Auto-harvest from Pinterest board failed: {e}")

        if detection.status == "INSUFFICIENT":
            self.notifier.notify_inbox_incomplete(len(detection.clips), self.config.daily_clip_count)
            report = DailyBatchReport(
                execution_date=today_ist,
                scheduled_time=f"{self.config.schedule_time} {self.config.timezone}",
                clips_received=len(detection.clips),
                metadata_generated=0,
                successfully_uploaded=0,
                failed=0,
                execution_status="INCOMPLETE_INPUT",
                failure_details=detection.message,
                required_action="Provide exactly two valid video clips in YT-Manager/inbox/.",
            )
            self.reporter.save_report(report)
            return report

        if detection.status != "READY":
            self.notifier.notify(
                event="DETECTION_ERROR",
                title=f"Batch Staging Blocked: {detection.status}",
                message=detection.message,
                level="WARNING",
            )
            report = DailyBatchReport(
                execution_date=today_ist,
                scheduled_time=f"{self.config.schedule_time} {self.config.timezone}",
                clips_received=len(detection.clips),
                metadata_generated=0,
                successfully_uploaded=0,
                failed=0,
                execution_status=f"FAILED ({detection.status})",
                failure_details=detection.message,
                required_action="Review inbox directory and ensure exactly two non-duplicate clips exist.",
            )
            self.reporter.save_report(report)
            return report

        # 3. Stage Batch (Atomically move to processing/<batch_id>/)
        batch_id, staged_paths = self.detector.stage_batch(detection)
        self.notifier.notify_processing_started(batch_id, len(staged_paths))

        clip_reports: List[ClipExecutionReport] = []
        success_count = 0
        failure_count = 0

        # Process clips independently
        for idx, video_path in enumerate(staged_paths, start=1):
            clip_id = f"{batch_id}_clip_{idx:02d}"
            clip_report = self._process_single_clip(
                batch_id=batch_id,
                clip_id=clip_id,
                index=idx,
                video_path=video_path,
            )
            clip_reports.append(clip_report)
            if clip_report.upload_status == "SUCCESS":
                success_count += 1
            else:
                failure_count += 1

        # 4. Final Batch Status Evaluation
        if success_count == len(staged_paths):
            overall_status = "COMPLETED"
            self.notifier.notify_upload_completed(batch_id, success_count)
        elif success_count > 0:
            overall_status = "PARTIAL"
        else:
            overall_status = "FAILED"

        report = DailyBatchReport(
            execution_date=today_ist,
            scheduled_time=f"{self.config.schedule_time} {self.config.timezone}",
            clips_received=len(staged_paths),
            metadata_generated=len([c for c in clip_reports if c.metadata_status == "Completed"]),
            successfully_uploaded=success_count,
            failed=failure_count,
            execution_status=overall_status,
            clips=clip_reports,
            failure_details=None if failure_count == 0 else f"{failure_count} upload(s) failed during execution.",
            required_action=None if failure_count == 0 else "Inspect error logs and run 'python -m yt_manager retry'.",
        )

        report_path = self.reporter.save_report(report)
        self.state.update_batch_status(batch_id, overall_status, report_path=str(report_path))
        return report

    def _process_single_clip(
        self,
        batch_id: str,
        clip_id: str,
        index: int,
        video_path: Path,
    ) -> ClipExecutionReport:
        """
        Executes the complete processing lifecycle for one clip:
        Inspect -> Understand -> Generate Metadata -> Upload -> Verify -> Archive.
        """
        original_filename = video_path.name
        work_dir = video_path.parent / f"work_{clip_id}"

        try:
            # 0. Anti-Copyright Media Transformation (Speedup, Micro-Zoom/Crop, Color Pop, Audio Loudnorm)
            active_video_path = video_path
            if self.config.enable_video_transformer and not self.mock_mode:
                self.notifier.notify(
                    event="TRANSFORMING",
                    title=f"Transforming Video {index}",
                    message=f"Applying anti-copyright filters & audio loudness normalization on {original_filename}...",
                    batch_id=batch_id,
                )
                transformed_path = work_dir / f"transformed_{original_filename}"
                t_res = self.transformer.transform_clip(video_path, transformed_path)
                if t_res.success and t_res.transformed:
                    active_video_path = t_res.output_path
                    self.state.log(
                        batch_id,
                        "INFO",
                        f"Clip {clip_id} successfully transformed for anti-copyright ({t_res.processing_time_seconds:.2f}s).",
                    )

            # 1. Media Inspection
            self.notifier.notify(
                event="INSPECTING",
                title=f"Inspecting Video {index}",
                message=f"Extracting technical metrics and frames from {active_video_path.name}...",
                batch_id=batch_id,
            )
            inspection = self.inspector.inspect(active_video_path, work_dir=work_dir)

            # 2. AI Content Understanding
            self.notifier.notify(
                event="UNDERSTANDING",
                title=f"Analyzing Video {index}",
                message="Understanding content, entities, and on-screen messages...",
                batch_id=batch_id,
            )
            understanding = self.understanding_engine.analyze(inspection)

            # CIRCUIT BREAKER: Block upload if content understanding is unverified fallback
            if not self.mock_mode and getattr(understanding, "is_fallback", False):
                err_msg = (
                    f"CIRCUIT BREAKER TRIGGERED: AI video understanding was unable to verify visual/audio content of '{original_filename}' "
                    f"(confidence: {understanding.confidence:.2f}). Upload blocked to protect channel quality from unverified/scraper metadata. "
                    f"Please verify GEMINI_API_KEY in config/settings.json or provide a sidecar .txt/.json file."
                )
                self.state.log(batch_id, "ERROR", err_msg)
                self.notifier.notify(
                    event="CONTENT_BLOCKED",
                    title="Upload Blocked — AI Vision Offline",
                    message=f"Halted upload for '{original_filename}' to prevent unverified metadata on YouTube.",
                    level="ERROR",
                    batch_id=batch_id,
                )
                return ClipExecutionReport(
                    index=index,
                    original_filename=original_filename,
                    generated_title="[BLOCKED] Unverified Content",
                    description_status="Blocked by Circuit Breaker",
                    metadata_status="Blocked",
                    upload_status="BLOCKED (CIRCUIT_BREAKER)",
                    youtube_video_id="",
                    youtube_url="",
                    error_message=err_msg,
                )

            # 3. SEO Metadata Generation
            self.notifier.notify(
                event="METADATA_GENERATION",
                title=f"Generating SEO Metadata {index}",
                message="Crafting optimized title, structured description, and niche tags...",
                batch_id=batch_id,
            )
            metadata = self.metadata_generator.generate(
                batch_id=batch_id,
                clip_id=clip_id,
                original_filename=original_filename,
                understanding=understanding,
            )
            metadata_file = self.metadata_generator.save_metadata(metadata)

            self.state.update_clip_metadata(
                clip_id=clip_id,
                duration=inspection.duration_seconds,
                width=inspection.width,
                height=inspection.height,
                metadata_path=str(metadata_file),
            )

            # 4. Upload Video
            self.notifier.notify(
                event="UPLOADING",
                title=f"Uploading Video {index}",
                message=f"Starting resumable YouTube Data API v3 upload: '{metadata.title}'...",
                batch_id=batch_id,
            )
            self.state.update_clip_status(clip_id, "UPLOADING")

            def on_progress(uploaded_bytes: int, total_bytes: int, elapsed: float) -> None:
                pct = (uploaded_bytes / total_bytes * 100) if total_bytes > 0 else 0
                if uploaded_bytes == total_bytes or int(pct) % 25 == 0:
                    self.notifier.notify(
                        event="UPLOAD_PROGRESS",
                        title=f"Upload Progress Video {index}",
                        message=f"{pct:.1f}% ({uploaded_bytes}/{total_bytes} bytes in {elapsed:.1f}s)",
                        batch_id=batch_id,
                    )

            upload_result = self.uploader.upload_video(
                video_path=active_video_path,
                metadata=metadata,
                progress_callback=on_progress,
            )

            # 5. Post-Upload Verification
            self.notifier.notify(
                event="VERIFYING",
                title=f"Verifying Video {index}",
                message=f"Confirming YouTube catalog registration for {upload_result.video_id}...",
                batch_id=batch_id,
            )
            verification = self.verifier.verify_video(upload_result.video_id)

            if not verification.verified:
                err_msg = verification.rejection_reason or "Video verification failed on YouTube."
                self.state.update_clip_status(
                    clip_id=clip_id,
                    status="FAILED",
                    error_message=err_msg,
                    youtube_video_id=upload_result.video_id,
                )
                self._move_to_failed(video_path, batch_id)
                return ClipExecutionReport(
                    index=index,
                    original_filename=original_filename,
                    generated_title=metadata.title,
                    description_status="Generated",
                    metadata_status="Completed",
                    upload_status="FAILED",
                    youtube_video_id=upload_result.video_id,
                    youtube_url=upload_result.youtube_url,
                    error_message=err_msg,
                )

            # 6. Post Creator Engagement Comment
            if getattr(self.config, "enable_creator_comment", True):
                try:
                    from .metadata import generate_creator_comment
                    custom_template = getattr(self.config, "creator_comment_template", "")
                    comment_text = custom_template if custom_template else generate_creator_comment(understanding)
                    comment_id = self.uploader.post_comment(upload_result.video_id, comment_text)
                    if comment_id:
                        self.state.log(
                            batch_id,
                            "INFO",
                            f"Posted creator engagement comment on {upload_result.video_id}: {comment_id}",
                        )
                except Exception as e:
                    self.state.log(batch_id, "WARNING", f"Failed to post creator comment: {e}")

            # 7. Save Records and Move to Uploaded
            file_hash = self.detector.validate_clip(video_path).file_hash
            self.state.record_successful_upload(
                file_hash=file_hash,
                original_filename=original_filename,
                youtube_video_id=upload_result.video_id,
                youtube_url=upload_result.youtube_url,
            )
            self.state.update_clip_status(
                clip_id=clip_id,
                status="VERIFIED",
                youtube_video_id=upload_result.video_id,
                youtube_url=upload_result.youtube_url,
                privacy_status=verification.privacy_status,
            )

            self._move_to_uploaded(video_path, batch_id)

            # Clean up temp frames work directory
            if work_dir.exists():
                try:
                    shutil.rmtree(work_dir)
                except Exception:
                    pass

            return ClipExecutionReport(
                index=index,
                original_filename=original_filename,
                generated_title=metadata.title,
                description_status="Generated",
                metadata_status="Completed",
                upload_status="SUCCESS",
                youtube_video_id=upload_result.video_id,
                youtube_url=upload_result.youtube_url,
            )

        except Exception as e:
            err_str = str(e)
            self.notifier.notify_upload_failed(batch_id, original_filename, err_str)
            self.state.update_clip_status(clip_id, "FAILED", error_message=err_str)
            self._move_to_failed(video_path, batch_id)

            return ClipExecutionReport(
                index=index,
                original_filename=original_filename,
                generated_title="Failed to generate",
                description_status="Failed",
                metadata_status="Failed",
                upload_status="FAILED",
                youtube_video_id="",
                youtube_url="",
                error_message=err_str,
            )

    def _move_to_uploaded(self, video_path: Path, batch_id: str) -> None:
        """Moves verified video safely from processing/ to uploaded/<batch_id>/."""
        target_dir = self.config.uploaded_dir / batch_id
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / video_path.name
        if video_path.exists():
            shutil.move(str(video_path), str(dest))

    def _move_to_failed(self, video_path: Path, batch_id: str) -> None:
        """
        Safely returns failed video back to the inbox/ queue so that it will
        automatically and smoothly retry in the next daily batch.
        Also archives a copy in failed/<batch_id>/ for forensic diagnostics.
        """
        if not video_path.exists():
            return

        # 1. Archive diagnostic copy into failed/<batch_id>/
        diagnostic_dir = self.config.failed_dir / batch_id
        diagnostic_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(str(video_path), str(diagnostic_dir / video_path.name))
        except Exception:
            pass

        # 2. Return the video back to inbox/ queue for smooth next-day retry
        inbox_dest = self.config.inbox_dir / video_path.name
        if inbox_dest.exists() and inbox_dest != video_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            inbox_dest = self.config.inbox_dir / f"{video_path.stem}_retry_{timestamp}{video_path.suffix}"

        shutil.move(str(video_path), str(inbox_dest))
        self.state.log(
            batch_id,
            "INFO",
            f"Returned failed video {video_path.name} to inbox queue at {inbox_dest.name} for future retry.",
        )
        self.notifier.notify(
            event="REQUEUED_FAILED_CLIP",
            title="Clip Re-queued to Inbox",
            message=f"'{video_path.name}' failed during upload and has been safely returned to your inbox queue for automatic re-upload.",
            level="WARNING",
            batch_id=batch_id,
        )

    def run_single_clip_test(self, clip_path: Path) -> ClipExecutionReport:
        """
        Executes a dedicated single-clip test run.
        Directly exercises media inspection, SEO metadata generation, and upload.
        """
        if not clip_path.exists():
            raise FileNotFoundError(f"Clip not found at: {clip_path}")

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        test_batch_id = f"test_{timestamp_str}"
        clip_id = f"{test_batch_id}_clip_01"

        # Copy clip into processing directory
        processing_dir = self.config.processing_dir / test_batch_id
        processing_dir.mkdir(parents=True, exist_ok=True)
        staged_clip = processing_dir / clip_path.name
        shutil.copy2(str(clip_path), str(staged_clip))

        file_size = staged_clip.stat().st_size
        file_hash = self.detector.validate_clip(staged_clip).file_hash

        today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.state.create_batch(test_batch_id, today_date, 1)
        self.state.register_clip(
            clip_id=clip_id,
            batch_id=test_batch_id,
            original_filename=staged_clip.name,
            file_hash=file_hash,
            file_size=file_size,
        )

        return self._process_single_clip(
            batch_id=test_batch_id,
            clip_id=clip_id,
            index=1,
            video_path=staged_clip,
        )
