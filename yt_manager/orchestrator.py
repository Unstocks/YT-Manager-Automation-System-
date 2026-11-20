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
from datetime import datetime, timezone
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
from .thumbnail_picker import ThumbnailPicker
from .understanding import ContentUnderstanding, VideoUnderstandingEngine
from .uploader import YouTubeUploader
from .verifier import VideoVerifier


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
        self.inspector = MediaInspector()
        self.understanding_engine = VideoUnderstandingEngine(self.config.gemini_api_key)
        self.metadata_generator = SEOMetadataGenerator(self.config)
        self.auth = YouTubeAuthManager(self.config)
        self.uploader = YouTubeUploader(self.config, self.auth, mock_mode=self.mock_mode)
        self.verifier = VideoVerifier(self.config, self.auth, mock_mode=self.mock_mode)
        self.thumbnail_picker = ThumbnailPicker()
        self.notifier = Notifier(self.config, self.state)
        self.reporter = ReportGenerator(self.config)

    def run_daily_batch(self, force_date: Optional[str] = None) -> DailyBatchReport:
        """
        Executes the daily 6:00 PM IST batch workflow.
        """
        today_ist = force_date or datetime.now(timezone.utc).strftime("%d %B %Y")
        today_date_str = force_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 1. Check for already completed batch today (Duplicate-run protection)
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
            # 1. Media Inspection
            self.notifier.notify(
                event="INSPECTING",
                title=f"Inspecting Video {index}",
                message=f"Extracting technical metrics and frames from {original_filename}...",
                batch_id=batch_id,
            )
            inspection = self.inspector.inspect(video_path, work_dir=work_dir)

            # 2. AI Content Understanding
            self.notifier.notify(
                event="UNDERSTANDING",
                title=f"Analyzing Video {index}",
                message="Understanding content, entities, and on-screen messages...",
                batch_id=batch_id,
            )
            understanding = self.understanding_engine.analyze(inspection)

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

            # 4. High-CTR Frame Selection (Thumbnail)
            thumb_candidate = None
            if self.config.enable_auto_thumbnail and inspection.extracted_frames:
                try:
                    thumb_candidate = self.thumbnail_picker.select_best_thumbnail(
                        extracted_frames=inspection.extracted_frames,
                        output_dir=work_dir,
                        clip_id=clip_id,
                        enhance=True,
                    )
                    self.notifier.notify(
                        event="THUMBNAIL_SELECTED",
                        title=f"Selected High-CTR Thumbnail {index}",
                        message=f"Winning frame: {thumb_candidate.best_frame_path.name} (Score: {thumb_candidate.score:.1f})",
                        batch_id=batch_id,
                    )
                except Exception as ex:
                    self.notifier.notify(
                        event="THUMBNAIL_WARNING",
                        title=f"Thumbnail Selection Warning {index}",
                        message=f"Could not pick custom frame: {ex}",
                        level="WARNING",
                        batch_id=batch_id,
                    )

            # 5. Upload Video
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
                video_path=video_path,
                metadata=metadata,
                progress_callback=on_progress,
            )

            # 6. Apply Custom Thumbnail (if selected)
            if thumb_candidate and upload_result.success:
                try:
                    token = "mock_token" if self.mock_mode else self.auth.get_valid_access_token()
                    self.thumbnail_picker.upload_thumbnail(
                        video_id=upload_result.video_id,
                        thumbnail_path=thumb_candidate.enhanced_thumbnail_path,
                        access_token=token,
                        mock_mode=self.mock_mode,
                    )
                    self.notifier.notify(
                        event="THUMBNAIL_UPLOADED",
                        title=f"Thumbnail Applied Video {index}",
                        message=f"Set high-CTR thumbnail for video {upload_result.video_id}",
                        batch_id=batch_id,
                    )
                except Exception as t_err:
                    # Non-fatal if account doesn't have custom thumbnail feature enabled yet
                    self.notifier.notify(
                        event="THUMBNAIL_FAILED",
                        title=f"Thumbnail Upload Notice {index}",
                        message=f"YouTube accepted video, custom thumbnail notice: {t_err}",
                        level="WARNING",
                        batch_id=batch_id,
                    )

            # 7. Post-Upload Verification
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

            # 6. Save Records and Move to Uploaded
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
        """Moves failed video safely from processing/ to failed/<batch_id>/."""
        target_dir = self.config.failed_dir / batch_id
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / video_path.name
        if video_path.exists():
            shutil.move(str(video_path), str(dest))

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
