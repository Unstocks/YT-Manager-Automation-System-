"""
End-to-End Integration tests for WorkflowOrchestrator.
Simulates daily execution with 2 video clips.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from yt_manager.config import YTManagerConfig
from yt_manager.orchestrator import WorkflowOrchestrator

SAMPLE_VIDEO_PATH = Path(
    "C:/Users/sanja/.gemini/antigravity/scratch/YT-Manager/uploaded/test_20261120_100723/media_1795143017068_2d97bbe8.mp4"
)
if not SAMPLE_VIDEO_PATH.exists():
    SAMPLE_VIDEO_PATH = Path(
        "C:/Users/sanja/.gemini/antigravity/brain/644084ee-6c51-48f9-9026-e53ad1e15c71/.user_uploaded/media_1795143017068_2d97bbe8.mp4"
    )


class TestOrchestratorIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = YTManagerConfig(base_dir=self.temp_dir)
        self.orchestrator = WorkflowOrchestrator(self.config, mock_mode=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_daily_batch_flow(self):
        # 1. Place exactly two clips into inbox
        inbox = self.config.inbox_dir
        if SAMPLE_VIDEO_PATH.exists():
            shutil.copy2(str(SAMPLE_VIDEO_PATH), str(inbox / "daily_clip_01.mp4"))
            # Make a slightly modified second clip (different byte) so hash is unique
            data = SAMPLE_VIDEO_PATH.read_bytes() + b"\x00"
            (inbox / "daily_clip_02.mp4").write_bytes(data)
        else:
            (inbox / "clip1.mp4").write_bytes(b"dummy1")
            (inbox / "clip2.mp4").write_bytes(b"dummy2")

        # 2. Run Daily Batch
        report = self.orchestrator.run_daily_batch(force_date="2026-11-20")

        # 3. Assertions
        self.assertEqual(report.execution_status, "COMPLETED")
        self.assertEqual(report.clips_received, 2)
        self.assertEqual(report.metadata_generated, 2)
        self.assertEqual(report.successfully_uploaded, 2)
        self.assertEqual(report.failed, 0)
        self.assertEqual(len(report.clips), 2)

        # Verify inbox is now empty
        self.assertEqual(len(list(inbox.glob("*.mp4"))), 0)

        # Verify clips were moved to uploaded/<batch_id>/
        uploaded_clips = list(self.config.uploaded_dir.rglob("*.mp4"))
        self.assertEqual(len(uploaded_clips), 2)

        # Verify metadata JSON documents were created
        meta_files = list(self.config.metadata_dir.glob("*.json"))
        self.assertEqual(len(meta_files), 2)

        # Verify report was generated on disk
        reports = list(self.config.reports_dir.glob("daily_report_*.txt"))
        self.assertEqual(len(reports), 1)
        report_text = reports[0].read_text(encoding="utf-8")
        self.assertIn("YT MANAGER — DAILY REPORT", report_text)
        self.assertIn("Execution Status: COMPLETED", report_text)

        # 4. Duplicate Run Protection Test: Running again on the same day should be rejected
        second_run = self.orchestrator.run_daily_batch(force_date="2026-11-20")
        self.assertEqual(second_run.execution_status, "COMPLETED (PRIOR RUN)")

    def test_auto_harvest_when_inbox_insufficient(self):
        # Configure Pinterest board
        self.config.pinterest_board_url = "https://pinterest.com/unstocks/daily-shorts"
        inbox = self.config.inbox_dir

        # Inbox is initially empty
        self.assertEqual(len(list(inbox.glob("*.mp4"))), 0)

        # Mock run_pre_upload_harvest to place 2 valid video files in inbox
        from unittest.mock import patch
        from yt_manager.pinterest_harvester import HarvestedCandidate

        def mock_harvest(board_url, target_count=2, clean_bgm=True, mask_watermark=True):
            if SAMPLE_VIDEO_PATH.exists():
                clip1 = inbox / "unstocks_short_pin_101.mp4"
                shutil.copy2(str(SAMPLE_VIDEO_PATH), str(clip1))
                clip2 = inbox / "unstocks_short_pin_102.mp4"
                clip2.write_bytes(SAMPLE_VIDEO_PATH.read_bytes() + b"\x01")
            else:
                clip1 = inbox / "unstocks_short_pin_101.mp4"
                clip1.write_bytes(b"dummy1")
                clip2 = inbox / "unstocks_short_pin_102.mp4"
                clip2.write_bytes(b"dummy2")
            return [
                HarvestedCandidate(pin_id="pin_101", pin_url="http://p1", video_url="http://v1", raw_video_path=Path(""), final_inbox_path=clip1, status="READY"),
                HarvestedCandidate(pin_id="pin_102", pin_url="http://p2", video_url="http://v2", raw_video_path=Path(""), final_inbox_path=clip2, status="READY"),
            ]

        with patch("yt_manager.pinterest_harvester.PinterestHarvester.run_pre_upload_harvest", side_effect=mock_harvest):
            report = self.orchestrator.run_daily_batch(force_date="2026-11-21")

        self.assertEqual(report.execution_status, "COMPLETED")
        self.assertEqual(report.clips_received, 2)
        self.assertEqual(report.successfully_uploaded, 2)
        self.assertEqual(report.failed, 0)
        # Inbox should be empty after processing
        self.assertEqual(len(list(inbox.glob("*.mp4"))), 0)


if __name__ == "__main__":
    unittest.main()
