"""
Unit tests for ClipDetector and StateManager.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from yt_manager.config import YTManagerConfig
from yt_manager.detector import ClipDetector, compute_sha256
from yt_manager.state import StateManager


class TestClipDetector(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = YTManagerConfig(base_dir=self.temp_dir)
        self.state = StateManager(self.config.db_path)
        self.detector = ClipDetector(self.config, self.state)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_dummy_video(self, name: str, content: bytes = b"dummy video content 12345") -> Path:
        p = self.config.inbox_dir / name
        with open(p, "wb") as f:
            f.write(content)
        return p

    def test_empty_inbox(self):
        res = self.detector.evaluate_daily_batch()
        self.assertEqual(res.status, "INSUFFICIENT")
        self.assertEqual(len(res.clips), 0)

    def test_single_clip_rejected(self):
        self._create_dummy_video("clip1.mp4")
        res = self.detector.evaluate_daily_batch()
        self.assertEqual(res.status, "INSUFFICIENT")
        self.assertEqual(len(res.clips), 1)

    def test_three_clips_queues_two_and_retains_one(self):
        self._create_dummy_video("clip1.mp4", b"c1")
        self._create_dummy_video("clip2.mp4", b"c2")
        self._create_dummy_video("clip3.mp4", b"c3")
        res = self.detector.evaluate_daily_batch()
        self.assertEqual(res.status, "READY")
        self.assertEqual(len(res.clips), 2)
        self.assertEqual(res.remaining_count, 1)

        # Staging only moves 2 clips, leaving 1 in inbox for the next day
        batch_id, staged = self.detector.stage_batch(res)
        self.assertEqual(len(staged), 2)
        remaining_in_inbox = self.detector.scan_inbox()
        self.assertEqual(len(remaining_in_inbox), 1)
        self.assertEqual(remaining_in_inbox[0].name, "clip3.mp4")

    def test_exactly_two_clips_accepted(self):
        self._create_dummy_video("clip1.mp4", b"c1")
        self._create_dummy_video("clip2.mp4", b"c2")
        res = self.detector.evaluate_daily_batch()
        self.assertEqual(res.status, "READY")
        self.assertEqual(len(res.clips), 2)
        self.assertIsNotNone(res.batch_id)

    def test_duplicate_clip_rejected(self):
        c1 = self._create_dummy_video("clip1.mp4", b"c1")
        self._create_dummy_video("clip2.mp4", b"c2")

        c1_hash = compute_sha256(c1)
        self.state.record_successful_upload(
            file_hash=c1_hash,
            original_filename="clip1.mp4",
            youtube_video_id="TEST_VID_001",
            youtube_url="https://youtu.be/TEST_VID_001",
        )

        res = self.detector.evaluate_daily_batch()
        self.assertEqual(res.status, "DUPLICATE_DETECTED")

    def test_stage_batch(self):
        self._create_dummy_video("clip1.mp4", b"c1")
        self._create_dummy_video("clip2.mp4", b"c2")
        res = self.detector.evaluate_daily_batch()
        batch_id, staged = self.detector.stage_batch(res)

        self.assertEqual(len(staged), 2)
        # Verify files were moved out of inbox
        self.assertEqual(len(self.detector.scan_inbox()), 0)
        # Verify files exist in processing/<batch_id>/
        for p in staged:
            self.assertTrue(p.exists())
            self.assertIn(batch_id, str(p))


if __name__ == "__main__":
    unittest.main()
