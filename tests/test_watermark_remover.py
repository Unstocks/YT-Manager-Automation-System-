"""
Unit tests for WatermarkMasker.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from yt_manager.watermark_remover import WatermarkMasker

SAMPLE_CLIP = Path("uploaded/test_20261120_100723/media_1795143017068_2d97bbe8.mp4")


class TestWatermarkMasker(unittest.TestCase):
    def setUp(self):
        self.masker = WatermarkMasker()
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_apply_blurred_mask(self):
        if not SAMPLE_CLIP.exists():
            self.skipTest("Sample clip not found")

        out = self.temp_dir / "masked.mp4"
        res = self.masker.apply_blurred_mask(SAMPLE_CLIP, out, position="bottom_right")

        self.assertTrue(res.exists())
        self.assertGreater(res.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
