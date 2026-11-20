"""
Unit tests for SEOMetadataGenerator.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from yt_manager.config import YTManagerConfig
from yt_manager.metadata import SEOMetadataGenerator
from yt_manager.understanding import ContentUnderstanding


class TestSEOMetadataGenerator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = YTManagerConfig(base_dir=self.temp_dir)
        self.generator = SEOMetadataGenerator(self.config)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_metadata_structure_shorts(self):
        understanding = ContentUnderstanding(
            subject="Engineering Decision Making",
            central_topic="Structured Problem Solving",
            on_screen_text=["Key Insight", "Decisions become sharper with structure"],
            spoken_dialogue="",
            entities=["Decision Architecture", "Problem Solving", "Unstocks"],
            intended_audience="Software Engineers & Architects",
            main_takeaway="Decision-making is a trained skill improved via structured methods.",
            category_id="27",
            category_name="Education",
            language="en",
            is_short=True,
            confidence=0.95,
        )

        metadata = self.generator.generate(
            batch_id="batch_20261120_180000",
            clip_id="batch_20261120_180000_clip_01",
            original_filename="clip_01.mp4",
            understanding=understanding,
        )

        # Title checks
        self.assertIn("Problem Solving", metadata.title)
        self.assertIn("#Shorts", metadata.title)
        self.assertLessEqual(len(metadata.title), 100)

        # Description checks
        self.assertIn("About Unstocks:", metadata.description)
        self.assertIn("structured problem solving", metadata.description.lower())
        self.assertTrue(len(metadata.hashtags) >= 2)

        # Tags check
        self.assertIn("unstocks", metadata.tags)
        self.assertLessEqual(sum(len(t) for t in metadata.tags), 500)

        # YouTube snippet payload
        snippet = metadata.to_youtube_snippet_payload()
        self.assertEqual(snippet["categoryId"], "27")
        self.assertEqual(snippet["defaultLanguage"], "en")
        self.assertTrue(len(snippet["title"]) <= 100)
        self.assertTrue(len(snippet["description"]) <= 5000)

        # Save metadata JSON file test
        meta_file = self.generator.save_metadata(metadata)
        self.assertTrue(meta_file.exists())
        self.assertGreater(meta_file.stat().st_size, 0)

    def test_metadata_structure_landscape(self):
        understanding = ContentUnderstanding(
            subject="Distributed Cache Invalidation",
            central_topic="Cache Invalidation Patterns",
            entities=["Redis", "Distributed Systems", "Unstocks"],
            intended_audience="Backend Engineers",
            main_takeaway="Two-phase invalidation prevents stale reads in distributed clusters.",
            category_id="28",
            category_name="Science & Technology",
            language="en",
            is_short=False,
            confidence=0.95,
        )

        metadata = self.generator.generate(
            batch_id="batch_20261120_180000",
            clip_id="batch_20261120_180000_clip_02",
            original_filename="distributed_cache.mp4",
            understanding=understanding,
        )

        self.assertIn("Cache Invalidation", metadata.title)
        self.assertNotIn("#Shorts", metadata.title)
        self.assertEqual(metadata.category_id, "28")
        self.assertIn("redis", metadata.tags)


if __name__ == "__main__":
    unittest.main()
