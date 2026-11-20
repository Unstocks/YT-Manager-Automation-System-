"""
Unit tests for ThumbnailPicker.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from yt_manager.inspector import MediaInspector
from yt_manager.thumbnail_picker import ThumbnailPicker

SAMPLE_VIDEO_PATH = Path(
    "C:/Users/sanja/.gemini/antigravity/scratch/YT-Manager/uploaded/test_20261120_100723/media_1795143017068_2d97bbe8.mp4"
)
if not SAMPLE_VIDEO_PATH.exists():
    SAMPLE_VIDEO_PATH = Path(
        "C:/Users/sanja/.gemini/antigravity/brain/644084ee-6c51-48f9-9026-e53ad1e15c71/.user_uploaded/media_1795143017068_2d97bbe8.mp4"
    )


class TestThumbnailPicker(unittest.TestCase):
    def setUp(self):
        self.inspector = MediaInspector()
        self.picker = ThumbnailPicker()
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_thumbnail_selection_and_enhancement(self):
        if not SAMPLE_VIDEO_PATH.exists():
            self.skipTest("Sample video clip not found")

        # 1. Extract candidate frames
        frames_dir = self.temp_dir / "frames"
        frames = self.inspector.extract_keyframes(SAMPLE_VIDEO_PATH, frames_dir, fps=1.0, max_frames=10)
        self.assertGreater(len(frames), 0)

        # 2. Select best thumbnail
        out_dir = self.temp_dir / "thumbs"
        cand = self.picker.select_best_thumbnail(frames, out_dir, clip_id="clip_test_01", enhance=True)

        self.assertIsNotNone(cand)
        self.assertTrue(cand.best_frame_path.exists())
        self.assertTrue(cand.enhanced_thumbnail_path.exists())
        self.assertGreater(cand.enhanced_thumbnail_path.stat().st_size, 0)
        self.assertGreater(cand.score, 0.0)

        # 3. Test mock upload
        res = self.picker.upload_thumbnail("mock_vid_123", cand.enhanced_thumbnail_path, "mock_token", mock_mode=True)
        self.assertTrue(res.get("mock"))


if __name__ == "__main__":
    unittest.main()
