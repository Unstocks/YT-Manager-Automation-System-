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


if __name__ == "__main__":
    unittest.main()
