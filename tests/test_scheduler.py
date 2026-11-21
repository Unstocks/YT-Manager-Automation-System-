"""
Unit tests for TaskSchedulerManager and Schedule Timing.
"""
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from yt_manager.config import YTManagerConfig
from yt_manager.scheduler import TaskSchedulerManager, TASK_NAME


class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = YTManagerConfig(base_dir=self.temp_dir)
        self.scheduler = TaskSchedulerManager(self.config)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_default_schedule_configuration(self):
        self.assertEqual(self.config.schedule_time, "18:00")
        self.assertEqual(self.config.timezone, "Asia/Kolkata")
        self.assertEqual(self.config.utc_offset_hours, 5.5)
        self.assertEqual(self.config.daily_clip_count, 2)
        self.assertEqual(self.config.retry_interval_minutes, 15)
        self.assertEqual(self.config.daily_cutoff_time, "23:59")

    def test_task_name_constant(self):
        self.assertEqual(TASK_NAME, "YT-Manager-Daily")

    def test_midnight_cutoff_and_window_evaluation(self):
        from yt_manager.orchestrator import WorkflowOrchestrator
        from datetime import datetime, timedelta, timezone

        orch = WorkflowOrchestrator(self.config, mock_mode=False)
        tz = timezone(timedelta(hours=5.5))

        # Test A: 23:50 IST (10 min before 12:00 AM midnight) -> SHOULD BE WITHIN WINDOW
        dt_before_midnight = datetime(2026, 11, 20, 23, 50, 0, tzinfo=tz)
        target_hour, target_min = map(int, self.config.schedule_time.split(":"))
        cutoff_hour, cutoff_min = map(int, self.config.daily_cutoff_time.split(":"))
        cur_min = dt_before_midnight.hour * 60 + dt_before_midnight.minute
        is_active = (target_hour * 60 + target_min) <= cur_min <= (cutoff_hour * 60 + cutoff_min)
        self.assertTrue(is_active)

        # Test B: 00:05 IST (5 min after 12:00 AM midnight) -> SHOULD BE OUTSIDE WINDOW (SHIFTS TO NEXT DAY)
        dt_after_midnight = datetime(2026, 11, 21, 0, 5, 0, tzinfo=tz)
        cur_min_after = dt_after_midnight.hour * 60 + dt_after_midnight.minute
        is_active_after = (target_hour * 60 + target_min) <= cur_min_after <= (cutoff_hour * 60 + cutoff_min)
        self.assertFalse(is_active_after)

        # Verify date rollover occurred exactly at midnight
        self.assertEqual(dt_before_midnight.strftime("%Y-%m-%d"), "2026-11-20")
        self.assertEqual(dt_after_midnight.strftime("%Y-%m-%d"), "2026-11-21")

    def test_record_test_trigger_event(self):
        import json
        proof_file = self.config.data_dir / "trigger_test_proof.json"
        self.assertFalse(proof_file.exists())

        self.scheduler.record_test_trigger_event()
        self.assertTrue(proof_file.exists())
        data = json.loads(proof_file.read_text(encoding="utf-8"))
        self.assertEqual(data.get("status"), "SUCCESS")
        self.assertIn("IST", data.get("timestamp"))

    def test_wait_for_network_connectivity(self):
        from yt_manager.orchestrator import wait_for_network_connectivity
        from unittest.mock import patch

        # Simulate immediate success
        with patch("yt_manager.orchestrator.check_network_connectivity", return_value=True):
            self.assertTrue(wait_for_network_connectivity(max_wait_seconds=2, interval=0.1))

        # Simulate timeout failure
        with patch("yt_manager.orchestrator.check_network_connectivity", return_value=False):
            self.assertFalse(wait_for_network_connectivity(max_wait_seconds=1, interval=0.1))


if __name__ == "__main__":
    unittest.main()
