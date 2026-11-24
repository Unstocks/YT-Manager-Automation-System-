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
        self.assertIn("#shorts", metadata.title.lower())
        self.assertIn("#fyp", metadata.title.lower())
        self.assertTrue(metadata.title.endswith("#fyp"))
        self.assertLessEqual(len(metadata.title), 80)

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

    def test_dynamic_title_generation_no_hardcoded_templates(self):
        # 1. Shorts video with dialogue
        u1 = ContentUnderstanding(
            subject="Neural Network Optimization",
            central_topic="Backpropagation Acceleration",
            spoken_dialogue="Today we explore gradient descent speedups with momentum.",
            main_takeaway="Momentum dampens oscillations in steep valleys.",
            is_short=True,
        )
        meta1 = self.generator.generate("batch_01", "c1", "vid1.mp4", u1)
        self.assertLess(len(meta1.title), 80)
        self.assertTrue(meta1.title.endswith("#fyp"))
        self.assertIn("#shorts", meta1.title.lower())
        self.assertIn("#Backpropagation", meta1.title)
        self.assertNotIn("System Architecture Deep Dive", meta1.title)
        self.assertNotIn("Core Architecture Guide", meta1.title)
        self.assertIn("Backpropagation", meta1.title)

        # 2. Landscape video without dialogue
        u2 = ContentUnderstanding(
            subject="Vector Database Indexing",
            central_topic="HNSW Graphs vs IVF Flat",
            main_takeaway="HNSW provides faster query latency at the expense of memory footprint.",
            is_short=False,
        )
        meta2 = self.generator.generate("batch_01", "c2", "vid2.mp4", u2)
        self.assertLess(len(meta2.title), 80)
        self.assertNotIn("#Shorts", meta2.title)
        self.assertNotIn("#shorts", meta2.title.lower())
        self.assertNotIn("#fyp", meta2.title.lower())
        self.assertNotIn("System Architecture Deep Dive", meta2.title)
        self.assertNotIn("Core Architecture Guide", meta2.title)

        # 3. Super long topic respects 80-char limit
        u3 = ContentUnderstanding(
            subject="Extremely Long Technical Subject That Exceeds Normal Length Thresholds By Far",
            central_topic="Extremely Long Technical Subject That Exceeds Normal Length Thresholds By Far",
            is_short=True,
        )
        meta3 = self.generator.generate("batch_01", "c3", "vid3.mp4", u3)
        self.assertLess(len(meta3.title), 80)
        self.assertTrue(meta3.title.endswith("#fyp"))
        self.assertIn("#shorts", meta3.title.lower())

    def test_description_and_tags_contain_actual_entities_no_boilerplate(self):
        understanding = ContentUnderstanding(
            subject="Postgres Concurrency",
            central_topic="MVCC and Row Locking",
            summary="An analysis of how PostgreSQL achieves snapshot isolation using Multi-Version Concurrency Control.",
            main_takeaway="FOR UPDATE locks rows exclusively while preventing read blocks.",
            entities=["PostgreSQL", "MVCC", "Row Locking", "ACID Transactions"],
            on_screen_text=["Row Locks", "Isolation Levels"],
            is_short=True,
        )

        metadata = self.generator.generate("batch_01", "c_mvcc", "mvcc.mp4", understanding)

        # Description assertions
        desc = metadata.description
        self.assertNotIn("Mastering mvcc and row locking is essential for building scalable", desc)
        self.assertNotIn("Lindy durability", desc)
        self.assertNotIn("Architecture tradeoffs and decision-making patterns", desc)
        self.assertIn("PostgreSQL", desc)
        self.assertIn("ACID Transactions", desc)
        self.assertIn("Key points highlighted:", desc)
        self.assertIn("• Row Locks", desc)
        self.assertIn("About Unstocks:", desc)

        # Hashtags assertions
        self.assertIn("PostgreSQL", metadata.hashtags)
        self.assertNotIn("SoftwareEngineering", metadata.hashtags)
        self.assertNotIn("SystemDesign", metadata.hashtags)
        self.assertIn("Shorts", metadata.hashtags)
        self.assertIn("fyp", metadata.hashtags)

        # Tags assertions
        total_tag_chars = sum(len(t) for t in metadata.tags)
        self.assertLess(total_tag_chars, 500)
        self.assertIn("postgresql", metadata.tags)
        self.assertIn("acid transactions", metadata.tags)
        self.assertIn("unstocks", metadata.tags)
        self.assertIn("shorts", metadata.tags)
        # Ensure generic defaults are NOT forced when not in entities
        self.assertNotIn("software architecture", metadata.tags)
        self.assertNotIn("engineering leadership", metadata.tags)

    def test_generate_creator_comment(self):
        from yt_manager.metadata import generate_creator_comment
        understanding = ContentUnderstanding(
            subject="Kubernetes Pod Networking",
            central_topic="CNI and iptables routing",
            summary="A deep dive into container network interfaces and packet filtering.",
            main_takeaway="eBPF reduces latency compared to standard kube-proxy iptables rules.",
            entities=["Kubernetes", "eBPF", "Networking"],
            is_short=True,
        )
        comment = generate_creator_comment(understanding)
        self.assertIn("eBPF reduces latency", comment)
        self.assertIn("cni and iptables routing", comment.lower())
        self.assertIn("@unstocks", comment)

    def test_pillar_creator_comment_generation(self):
        from yt_manager.metadata import generate_creator_comment
        # Luxury / Scarcity
        u_luxury = ContentUnderstanding(
            subject="Luxury Economics",
            featured_brand="Ferrari",
            central_topic="Veblen Goods and Artificial Scarcity",
            is_short=True,
        )
        c_luxury = generate_creator_comment(u_luxury)
        self.assertIn("Ferrari", c_luxury)
        self.assertIn("ultra-exclusive luxury brand", c_luxury)

        # First Principles
        u_fp = ContentUnderstanding(
            subject="Mental Models",
            featured_brand="Elon Musk",
            central_topic="First Principles Thinking",
            is_short=True,
        )
        c_fp = generate_creator_comment(u_fp)
        self.assertIn("Elon Musk", c_fp)
        self.assertIn("First Principles Test", c_fp)

        # Competitive Intel
        u_ci = ContentUnderstanding(
            subject="Growth Strategy",
            central_topic="Competitor Analysis & SEO Reverse Engineering",
            is_short=True,
        )
        c_ci = generate_creator_comment(u_ci)
        self.assertIn("reverse-engineer your top 3 competitors", c_ci)

    def test_non_repetitive_titles(self):
        # Two clips with same brand but different clip IDs have distinct rotating formulas
        u = ContentUnderstanding(
            subject="Luxury Economics",
            featured_brand="Ferrari",
            central_topic="Veblen Goods and Scarcity",
            is_short=True,
        )
        meta_a = self.generator.generate("batch_01", "clip_01", "vid1.mp4", u)
        meta_b = self.generator.generate("batch_01", "clip_02", "vid2.mp4", u)
        # Verify valid lengths and formatting
        self.assertLessEqual(len(meta_a.title), 78)
        self.assertLessEqual(len(meta_b.title), 78)
        self.assertIn("#Ferrari", meta_a.title)
        self.assertIn("#Ferrari", meta_b.title)
        self.assertNotIn("Built A $1B Empire With ZERO Ads", meta_a.title)
        self.assertNotIn("Built A $1B Empire With ZERO Ads", meta_b.title)


if __name__ == "__main__":
    unittest.main()
