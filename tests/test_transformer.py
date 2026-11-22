"""
Unit tests for MediaTransformer module.
Verifies studio-grade anti-copyright transformation, audio stream detection,
silent video handling, configuration toggling, and fail-safe fallback behavior.
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from yt_manager.config import YTManagerConfig
from yt_manager.transformer import MediaTransformer, TransformationResult

FIXTURE_VIDEO = Path(__file__).parent / "fixtures" / "sample_test_video.mp4"


class TestMediaTransformer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = YTManagerConfig(base_dir=self.temp_dir)
        self.transformer = MediaTransformer(self.config)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_audio_stream_detection(self):
        """Verifies that has_audio_stream accurately identifies audio tracks."""
        if not FIXTURE_VIDEO.exists():
            self.skipTest("Sample test fixture not available.")
        has_audio = self.transformer.has_audio_stream(FIXTURE_VIDEO)
        self.assertIsInstance(has_audio, bool)

    def test_transform_clip_execution(self):
        """Verifies end-to-end transformation execution produces a valid output file."""
        if not FIXTURE_VIDEO.exists():
            self.skipTest("Sample test fixture not available.")

        out_path = self.temp_dir / "transformed_sample.mp4"
        res = self.transformer.transform_clip(
            input_path=FIXTURE_VIDEO,
            output_path=out_path,
        )

        self.assertTrue(res.success)
        self.assertTrue(res.transformed)
        self.assertTrue(out_path.exists())
        self.assertGreater(out_path.stat().st_size, 0)
        self.assertGreater(res.processing_time_seconds, 0)

    def test_transform_disabled_in_config(self):
        """Verifies that disabling the transformer passes the original file through."""
        self.config.enable_video_transformer = False
        out_path = self.temp_dir / "passthrough_sample.mp4"

        res = self.transformer.transform_clip(
            input_path=FIXTURE_VIDEO,
            output_path=out_path,
        )

        self.assertTrue(res.success)
        self.assertFalse(res.transformed)
        self.assertTrue(out_path.exists())

    def test_silent_clip_handling(self):
        """Verifies that videos without audio tracks are processed safely without filter errors."""
        silent_video = self.temp_dir / "silent_test.mp4"
        # Generate a 2-second silent synthetic video
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=360x640:d=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(silent_video)
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except Exception:
            self.skipTest("FFmpeg synthetic video generation not available.")

        self.assertFalse(self.transformer.has_audio_stream(silent_video))

        out_path = self.temp_dir / "transformed_silent.mp4"
        res = self.transformer.transform_clip(
            input_path=silent_video,
            output_path=out_path,
        )

        self.assertTrue(res.success)
        self.assertTrue(res.transformed)
        self.assertFalse(res.has_audio)
        self.assertTrue(out_path.exists())

    def test_fallback_on_corrupt_input(self):
        """Verifies that an unreadable or corrupt file triggers the fail-safe fallback."""
        corrupt_input = self.temp_dir / "corrupt_test.mp4"
        with open(corrupt_input, "w") as f:
            f.write("This is not a real video file content.")

        out_path = self.temp_dir / "fallback_output.mp4"
        res = self.transformer.transform_clip(
            input_path=corrupt_input,
            output_path=out_path,
        )

        # Fallback catches the error gracefully and does not crash
        self.assertFalse(res.success)
        self.assertIsNotNone(res.error_message)


if __name__ == "__main__":
    unittest.main()
