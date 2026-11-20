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


if __name__ == "__main__":
    unittest.main()
