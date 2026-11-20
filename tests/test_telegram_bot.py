"""
Unit tests for TelegramIngestionBot.
"""
import json
import shutil
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from yt_manager.config import YTManagerConfig
from yt_manager.telegram_bot import TelegramIngestionBot


class TestTelegramIngestionBot(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = YTManagerConfig(
            base_dir=self.temp_dir,
            telegram_bot_token="123456789:ABCDefGhIjKlMnOpQrStUvWxYz",
            telegram_chat_id="987654321",
            enable_telegram_ingest=True,
        )
        self.bot = TelegramIngestionBot(self.config)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_is_configured(self):
        self.assertTrue(self.bot.is_configured)
        bad_bot = TelegramIngestionBot(YTManagerConfig(base_dir=self.temp_dir, telegram_bot_token=""))
        self.assertFalse(bad_bot.is_configured)

    @unittest.mock.patch("urllib.request.urlopen")
    def test_send_message(self, mock_urlopen):
        resp_obj = unittest.mock.MagicMock()
        resp_obj.status = 200
        resp_obj.__enter__.return_value = resp_obj
        mock_urlopen.return_value = resp_obj

        result = self.bot.send_message("987654321", "Hello from tests!")
        self.assertTrue(result)
        mock_urlopen.assert_called_once()

    @unittest.mock.patch("urllib.request.urlopen")
    def test_get_updates(self, mock_urlopen):
        resp_obj = unittest.mock.MagicMock()
        resp_obj.read.return_value = json.dumps({
            "ok": True,
            "result": [
                {"update_id": 101, "message": {"text": "hello", "chat": {"id": 987654321}}}
            ]
        }).encode("utf-8")
        resp_obj.__enter__.return_value = resp_obj
        mock_urlopen.return_value = resp_obj

        updates = self.bot.get_updates()
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["update_id"], 101)

    def test_auto_pairing_on_first_message(self):
        # Unpaired config
        unpaired_config = YTManagerConfig(
            base_dir=self.temp_dir,
            telegram_bot_token="123456789:ABCDefGhIjKlMnOpQrStUvWxYz",
            telegram_chat_id="",
        )
        bot = TelegramIngestionBot(unpaired_config)
        self.assertEqual(bot.chat_id, "")

        with unittest.mock.patch.object(bot, "send_message", return_value=True) as mock_send:
            bot.handle_message({
                "chat": {"id": 11223344},
                "from": {"first_name": "Sanjay"},
                "text": "/start",
            })

            # Check paired
            self.assertEqual(bot.chat_id, "11223344")
            mock_send.assert_called_once()
            args, _ = mock_send.call_args
            self.assertEqual(args[0], "11223344")
            self.assertIn("Bot Paired Successfully", args[1])

    def test_reject_unauthorized_user_after_pairing(self):
        with unittest.mock.patch.object(self.bot, "send_message", return_value=True) as mock_send:
            self.bot.handle_message({
                "chat": {"id": 555555},  # Different from paired 987654321
                "text": "give me video",
            })

            mock_send.assert_called_once()
            args, _ = mock_send.call_args
            self.assertIn("Unauthorized Access", args[1])

    def test_status_command(self):
        with unittest.mock.patch.object(self.bot, "send_message", return_value=True) as mock_send:
            self.bot.handle_message({
                "chat": {"id": 987654321},
                "text": "/status",
            })

            mock_send.assert_called_once()
            args, _ = mock_send.call_args
            self.assertIn("YT Manager System Status", args[1])
            self.assertIn("Inbox Count", args[1])

    def test_video_clip_ingestion(self):
        fake_video_msg = {
            "chat": {"id": 987654321},
            "video": {
                "file_id": "file_xyz_123",
                "file_name": "mobile_short.mp4",
                "file_size": 1024 * 1024 * 3,
                "duration": 22,
            }
        }

        def fake_download(remote_path, dest_path):
            dest_path.write_bytes(b"dummy_video_bytes")
            return True

        with unittest.mock.patch.object(self.bot, "get_file_info", return_value={"file_path": "videos/file_1.mp4"}), \
             unittest.mock.patch.object(self.bot, "download_file", side_effect=fake_download) as mock_dl, \
             unittest.mock.patch.object(self.bot, "send_message", return_value=True) as mock_send:

            saved_path = self.bot.handle_message(fake_video_msg)

            self.assertIsNotNone(saved_path)
            self.assertEqual(saved_path.name, "mobile_short.mp4")
            self.assertTrue(saved_path.exists())
            self.assertTrue(mock_send.call_count >= 2)


if __name__ == "__main__":
    unittest.main()
