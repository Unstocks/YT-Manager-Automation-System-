"""
Unit tests for MediaInspector.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from yt_manager.inspector import MediaInspector

SAMPLE_VIDEO_PATH = Path(
    "C:/Users/sanja/.gemini/antigravity/scratch/YT-Manager/uploaded/test_20261120_100723/media_1795143017068_2d97bbe8.mp4"
)
if not SAMPLE_VIDEO_PATH.exists():
    SAMPLE_VIDEO_PATH = Path(
        "C:/Users/sanja/.gemini/antigravity/brain/644084ee-6c51-48f9-9026-e53ad1e15c71/.user_uploaded/media_1795143017068_2d97bbe8.mp4"
    )


class TestMediaInspector(unittest.TestCase):
    def setUp(self):
        self.inspector = MediaInspector()
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_probe_real_clip(self):
        if not SAMPLE_VIDEO_PATH.exists():
            self.skipTest("Sample video clip not found on path")

        inspection = self.inspector.inspect(SAMPLE_VIDEO_PATH, work_dir=self.temp_dir)

        # Check durations and dimensions
        self.assertAlmostEqual(inspection.duration_seconds, 17.88, places=1)
        self.assertEqual(inspection.width, 720)
        self.assertEqual(inspection.height, 1280)
        self.assertTrue(inspection.is_short, "Vertical video under 60s should qualify as YouTube Short")
        self.assertEqual(inspection.video_codec, "h264")
        self.assertTrue(inspection.has_audio)

        # Check extracted frames
        self.assertGreater(len(inspection.extracted_frames), 0)
        for frame in inspection.extracted_frames:
            self.assertTrue(frame.exists())
            self.assertGreater(frame.stat().st_size, 0)

        # Check extracted audio
        self.assertIsNotNone(inspection.extracted_audio_path)
        self.assertTrue(inspection.extracted_audio_path.exists())


if __name__ == "__main__":
    unittest.main()
