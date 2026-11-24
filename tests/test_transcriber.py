"""
Unit Tests for AudioTranscriber Module
"""
import unittest
from pathlib import Path
from yt_manager.transcriber import AudioTranscriber


class TestAudioTranscriber(unittest.TestCase):
    def setUp(self):
        self.transcriber = AudioTranscriber()

    def test_parse_transcript_elon_musk(self):
        sample = (
            "First principles is a physics way of looking at the world. "
            "Elon Musk explained that at Tesla and SpaceX you boil things down to the most fundamental truths."
        )
        parsed = self.transcriber.parse_transcript_into_context(sample)
        self.assertEqual(parsed["featured_brand"], "Elon Musk")
        self.assertIn("Tesla", parsed["spoken_dialogue"])
        self.assertIn("Unstocks", parsed["entities"])
        self.assertGreaterEqual(parsed["confidence"], 0.9)

    def test_parse_transcript_starbucks(self):
        sample = (
            "Starbucks does not just sell coffee beans. Howard Schultz realized that "
            "customers need a third place between home and work where they feel community."
        )
        parsed = self.transcriber.parse_transcript_into_context(sample)
        self.assertEqual(parsed["featured_brand"], "Starbucks")
        self.assertIn("third place", parsed["spoken_dialogue"].lower())

    def test_parse_transcript_ferrari(self):
        sample = (
            "Ferrari will always produce one less car than the market demands. "
            "Enzo understood that artificial scarcity drives infinite pricing power."
        )
        parsed = self.transcriber.parse_transcript_into_context(sample)
        self.assertEqual(parsed["featured_brand"], "Ferrari")

    def test_parse_transcript_generic_business(self):
        sample = (
            "Stop wasting money on random ads. Optimize your conversion rate and retention funnel first."
        )
        parsed = self.transcriber.parse_transcript_into_context(sample)
        self.assertIn("Unstocks", parsed["entities"])
        self.assertTrue(len(parsed["main_takeaway"]) > 0)


if __name__ == "__main__":
    unittest.main()
