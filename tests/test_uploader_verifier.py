"""
Unit tests for YouTubeUploader, VideoVerifier, and Channel Security Verification.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from yt_manager.auth import ChannelMismatchError, YouTubeAuthManager
from yt_manager.config import YTManagerConfig
from yt_manager.metadata import VideoMetadata
from yt_manager.uploader import YouTubeUploader
from yt_manager.verifier import VideoVerifier


class TestUploaderAndVerifier(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = YTManagerConfig(base_dir=self.temp_dir)
        self.uploader = YouTubeUploader(self.config, mock_mode=True)
        self.verifier = VideoVerifier(self.config, mock_mode=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mock_upload_and_verification(self):
        # Create dummy video
        video_path = self.temp_dir / "sample.mp4"
        with open(video_path, "wb") as f:
            f.write(b"0" * (1024 * 512))  # 512 KB

        meta = VideoMetadata(
            batch_id="batch_01",
            clip_id="clip_01",
            original_filename="sample.mp4",
            title="Sample Title #Shorts",
            description="Sample Description\n\n#Shorts",
            tags=["sample", "test"],
            hashtags=["Shorts"],
            category_id="28",
            language="en",
            content_summary="Summary",
        )

        progress_calls = []

        def on_progress(up, tot, el):
            progress_calls.append((up, tot))

        res = self.uploader.upload_video(video_path, meta, progress_callback=on_progress)
        self.assertTrue(res.success)
        self.assertTrue(res.video_id.startswith("mock_"))
        self.assertEqual(res.bytes_uploaded, 512 * 1024)
        self.assertGreater(len(progress_calls), 0)

        # Verification
        v_res = self.verifier.verify_video(res.video_id)
        self.assertTrue(v_res.verified)
        self.assertEqual(v_res.upload_status, "processed")

    def test_channel_mismatch_security(self):
        # If an account has wrong channel ID, verify_target_channel raises ChannelMismatchError
        auth_mgr = YouTubeAuthManager(self.config)

        # Mock query return with wrong ID
        class MockAuthManager:
            def verify_target_channel(self):
                raise ChannelMismatchError("Channel mismatch detected!")

        uploader = YouTubeUploader(self.config, auth_manager=MockAuthManager(), mock_mode=False)

        video_path = self.temp_dir / "sample.mp4"
        with open(video_path, "wb") as f:
            f.write(b"0" * 100)

        meta = VideoMetadata(
            batch_id="batch_01",
            clip_id="clip_01",
            original_filename="sample.mp4",
            title="Test",
            description="Test",
            tags=["test"],
            hashtags=["test"],
            category_id="28",
            language="en",
            content_summary="Test",
        )

        with self.assertRaises(ChannelMismatchError):
            uploader.upload_video(video_path, meta)

    def test_post_comment_mock(self):
        comment_id = self.uploader.post_comment("mock_video_999", "Great insight on system design!")
        self.assertEqual(comment_id, "mock_comment_mock_video_999")

        # Empty video_id or empty comment should return None
        self.assertIsNone(self.uploader.post_comment("", "Comment"))
        self.assertIsNone(self.uploader.post_comment("mock_video_999", "   "))


if __name__ == "__main__":
    unittest.main()
