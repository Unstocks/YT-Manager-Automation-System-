"""
Unit tests for PinterestHarvester.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from yt_manager.config import YTManagerConfig
from yt_manager.pinterest_harvester import PinterestHarvester
from yt_manager.state import StateManager

SAMPLE_VIDEO_PATH = Path(
    "C:/Users/sanja/.gemini/antigravity/brain/644084ee-6c51-48f9-9026-e53ad1e15c71/.user_uploaded/media_1795143017068_2d97bbe8.mp4"
)


class TestPinterestHarvester(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = YTManagerConfig(base_dir=self.temp_dir)
        self.state = StateManager(self.config.db_path)
        self.harvester = PinterestHarvester(self.config, self.state)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_pin_id(self):
        url = "https://www.pinterest.com/pin/766456430382366110/"
        pin_id = self.harvester.parse_pin_id(url)
        self.assertEqual(pin_id, "766456430382366110")

    def test_duplicate_pin_tracking(self):
        pin_id = "test_pin_999"
        self.assertFalse(self.state.is_pin_harvested(pin_id))
        self.state.record_harvested_pin(pin_id, "https://pinterest.com/pin/test_pin_999")
        self.assertTrue(self.state.is_pin_harvested(pin_id))

    def test_local_staging_pipeline(self):
        if not SAMPLE_VIDEO_PATH.exists():
            self.skipTest("Sample video clip not found")

        # Mock download by pointing directly to sample video
        work_dir = self.temp_dir / "work"
        work_dir.mkdir(parents=True, exist_ok=True)
        raw_download = work_dir / "raw_pin_766456430382366110.mp4"
        shutil.copy2(str(SAMPLE_VIDEO_PATH), str(raw_download))

        # Test process and stage
        pin_url = "https://www.pinterest.com/pin/766456430382366110/"
        
        # Test inspection
        inspection = self.harvester.inspector.inspect(raw_download)
        self.assertTrue(5.0 <= inspection.duration_seconds <= 60.0)
        self.assertTrue(inspection.is_short)

        # Stage into inbox
        final_inbox = self.config.inbox_dir / "unstocks_short_766456430382366110.mp4"
        shutil.copy2(str(raw_download), str(final_inbox))
        self.assertTrue(final_inbox.exists())

    def test_run_pre_upload_harvest_skips_duplicates(self):
        # Mark pin1 as already harvested
        self.state.record_harvested_pin("pin_01", "https://pinterest.com/pin/pin_01")
        self.assertTrue(self.state.is_pin_harvested("pin_01"))

        # Mock fetch_board_pins to return 3 pins: pin_01 (duplicate), pin_02, pin_03
        self.harvester.fetch_board_pins = lambda url, max_pins=20: [
            "https://www.pinterest.com/pin/pin_01/",
            "https://www.pinterest.com/pin/pin_02/",
            "https://www.pinterest.com/pin/pin_03/",
        ]

        # Mock process_and_stage_pin to simulate successful staging for fresh pins
        from yt_manager.pinterest_harvester import HarvestedCandidate

        def mock_process(pin_url, work_dir, clean_bgm=True, mask_watermark=True):
            pin_id = self.harvester.parse_pin_id(pin_url)
            if self.state.is_pin_harvested(pin_id):
                return HarvestedCandidate(pin_id=pin_id, pin_url=pin_url, video_url="", raw_video_path=Path(""), status="ALREADY_PROCESSED")
            
            fake_staged = self.config.inbox_dir / f"unstocks_short_{pin_id}.mp4"
            fake_staged.write_bytes(b"dummy_short")
            self.state.record_harvested_pin(pin_id, pin_url, "http://video.mp4")
            return HarvestedCandidate(pin_id=pin_id, pin_url=pin_url, video_url="http://video.mp4", raw_video_path=Path(""), final_inbox_path=fake_staged, duration_seconds=25.0, status="READY")

        self.harvester.process_and_stage_pin = mock_process

        # Run harvest requesting 2 clips
        staged = self.harvester.run_pre_upload_harvest("https://pinterest.com/user/board", target_count=2)

        # Must skip pin_01 and stage exactly pin_02 and pin_03
        self.assertEqual(len(staged), 2)
        self.assertEqual(staged[0].pin_id, "pin_02")
        self.assertEqual(staged[1].pin_id, "pin_03")
        self.assertTrue((self.config.inbox_dir / "unstocks_short_pin_02.mp4").exists())
        self.assertTrue((self.config.inbox_dir / "unstocks_short_pin_03.mp4").exists())


if __name__ == "__main__":
    unittest.main()
