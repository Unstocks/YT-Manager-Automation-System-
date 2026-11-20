"""
Unit tests for VideoUnderstandingEngine.
"""
import shutil
import tempfile
import unittest
import unittest.mock
import urllib.error
from pathlib import Path

from yt_manager.inspector import MediaInspection
from yt_manager.understanding import VideoUnderstandingEngine, clean_title_from_filename


class TestVideoUnderstandingEngine(unittest.TestCase):
    def setUp(self):
        self.engine = VideoUnderstandingEngine()
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_clean_title_from_filename(self):
        self.assertEqual(clean_title_from_filename("clip_01.mp4"), "System Architecture & Engineering")
        self.assertEqual(clean_title_from_filename("system_design_patterns.mp4"), "System Design Patterns")
        self.assertEqual(clean_title_from_filename("batch_20261120_event_driven_microservices.mov"), "Event Driven Microservices")
        self.assertEqual(clean_title_from_filename("distributed_consensus_raft_algorithm.webm"), "Distributed Consensus Raft Algorithm")

    def test_sidecar_json_ingestion(self):
        vid_file = self.temp_dir / "cache_invalidation.mp4"
        vid_file.write_bytes(b"dummy")
        sidecar_json = self.temp_dir / "cache_invalidation.json"
        sidecar_json.write_text("""
        {
            "subject": "Cache Invalidation Strategies",
            "central_topic": "Write-Through vs Write-Behind",
            "entities": ["Redis", "Memcached", "Distributed Cache"],
            "main_takeaway": "Write-behind caching improves write latency at the cost of eventual consistency.",
            "category_id": "28"
        }
        """, encoding="utf-8")

        inspection = MediaInspection(
            file_path=vid_file,
            duration_seconds=45.0,
            width=720,
            height=1280,
            aspect_ratio=0.5625,
            is_short=True,
            video_codec="h264",
            audio_codec="aac",
            has_audio=True,
            fps=30.0,
            bitrate=1000000,
        )

        understanding = self.engine.analyze(inspection)
        self.assertEqual(understanding.subject, "Cache Invalidation Strategies")
        self.assertEqual(understanding.central_topic, "Write-Through vs Write-Behind")
        self.assertIn("Redis", understanding.entities)
        self.assertIn("eventual consistency", understanding.main_takeaway)

    def test_factual_fallback_no_hallucinations(self):
        vid_file = self.temp_dir / "database_indexing_explained.mp4"
        vid_file.write_bytes(b"dummy")

        inspection = MediaInspection(
            file_path=vid_file,
            duration_seconds=55.0,
            width=1080,
            height=1920,
            aspect_ratio=0.5625,
            is_short=True,
            video_codec="h264",
            audio_codec="aac",
            has_audio=True,
            fps=30.0,
            bitrate=2000000,
        )

        understanding = self.engine.analyze(inspection)
        self.assertEqual(understanding.subject, "Database Indexing Explained")
        # Ensure it does NOT invent fake stats like 35,000 decisions
        self.assertNotIn("35,000 decisions", understanding.summary)
        self.assertNotIn("35,000 decisions", understanding.main_takeaway)
        self.assertEqual(understanding.is_short, True)
        # Check Task 1C deterministic fallback updates
        self.assertEqual(understanding.confidence, 0.7)
        self.assertEqual(understanding.entities, ["Database Indexing Explained", "Unstocks"])
        self.assertNotIn("Software Architecture", understanding.entities)
        self.assertNotIn("Technical Decision Making", understanding.entities)

    @unittest.mock.patch("time.sleep")
    @unittest.mock.patch("urllib.request.urlopen")
    def test_gemini_vision_retry_on_transient_error(self, mock_urlopen, mock_sleep):
        frame = self.temp_dir / "frame_001.jpg"
        frame.write_bytes(b"\xff\xd8\xff\xe0dummyjpeg")

        inspection = MediaInspection(
            file_path=self.temp_dir / "test.mp4",
            duration_seconds=15.0,
            width=720,
            height=1280,
            aspect_ratio=0.5625,
            is_short=True,
            video_codec="h264",
            audio_codec="aac",
            has_audio=True,
            fps=30.0,
            bitrate=1000000,
            extracted_frames=[frame],
        )

        engine = VideoUnderstandingEngine(gemini_api_key="test_api_key_123")

        # Mock first attempt fails with HTTP 429, second attempt succeeds
        resp_obj = unittest.mock.MagicMock()
        resp_obj.read.return_value = b'{"candidates": [{"content": {"parts": [{"text": "{\\"subject\\": \\"Retry Succeeded\\", \\"central_topic\\": \\"Transient Resilience\\"}"}]}}]}'
        resp_obj.__enter__.return_value = resp_obj

        mock_urlopen.side_effect = [
            urllib.error.HTTPError("https://api.google.com", 429, "Too Many Requests", {}, None),
            resp_obj,
        ]

        with self.assertLogs("YTManager.Understanding", level="WARNING") as cm:
            res = engine._call_gemini_vision(inspection, "Analyze frames")

        self.assertIsNotNone(res)
        self.assertEqual(res.get("subject"), "Retry Succeeded")
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once_with(2)
        self.assertTrue(any("transient HTTP 429" in msg for msg in cm.output))

    @unittest.mock.patch("time.sleep")
    @unittest.mock.patch("urllib.request.urlopen")
    def test_gemini_vision_permanent_failure_logs_warning_and_returns_none(self, mock_urlopen, mock_sleep):
        frame = self.temp_dir / "frame_001.jpg"
        frame.write_bytes(b"\xff\xd8\xff\xe0dummyjpeg")

        inspection = MediaInspection(
            file_path=self.temp_dir / "test.mp4",
            duration_seconds=15.0,
            width=720,
            height=1280,
            aspect_ratio=0.5625,
            is_short=True,
            video_codec="h264",
            audio_codec="aac",
            has_audio=True,
            fps=30.0,
            bitrate=1000000,
            extracted_frames=[frame],
        )

        engine = VideoUnderstandingEngine(gemini_api_key="test_api_key_123")

        # Mock permanent URLError on both attempts
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        with self.assertLogs("YTManager.Understanding", level="WARNING") as cm:
            res = engine._call_gemini_vision(inspection, "Analyze frames")

        self.assertIsNone(res)
        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertTrue(any("network error after retry" in msg for msg in cm.output))


if __name__ == "__main__":
    unittest.main()
