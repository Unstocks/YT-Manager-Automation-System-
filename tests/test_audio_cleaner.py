"""
Unit tests for AudioCleaner.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from yt_manager.audio_cleaner import AudioCleaner

SAMPLE_VIDEO_PATH = Path(
    "C:/Users/sanja/.gemini/antigravity/scratch/YT-Manager/uploaded/test_20261120_100723/media_1795143017068_2d97bbe8.mp4"
)
if not SAMPLE_VIDEO_PATH.exists():
    SAMPLE_VIDEO_PATH = Path(
        "C:/Users/sanja/.gemini/antigravity/brain/644084ee-6c51-48f9-9026-e53ad1e15c71/.user_uploaded/media_1795143017068_2d97bbe8.mp4"
    )


class TestAudioCleaner(unittest.TestCase):
    def setUp(self):
        self.cleaner = AudioCleaner()
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_audio_separation_and_remux(self):
        if not SAMPLE_VIDEO_PATH.exists():
            self.skipTest("Sample video clip not found")

        result = self.cleaner.separate_and_clean(SAMPLE_VIDEO_PATH, self.temp_dir)
        self.assertTrue(result.success)
        self.assertTrue(result.cleaned_video_path.exists())
        self.assertGreater(result.cleaned_video_path.stat().st_size, 0)
        self.assertTrue(result.speech_stem_path.exists())


if __name__ == "__main__":
    unittest.main()
