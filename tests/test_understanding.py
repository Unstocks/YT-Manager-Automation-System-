"""
Unit tests for VideoUnderstandingEngine.
"""
import shutil
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
