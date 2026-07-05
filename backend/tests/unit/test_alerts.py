import unittest.mock
from backend.app.core.alerts import send_telegram_alert
from backend.app.config.settings import settings

def test_send_telegram_alert_disabled():
    # If settings doesn't have token/chat_id, it returns immediately without requests
    with unittest.mock.patch("requests.post") as mock_post:
        with unittest.mock.patch.object(settings, "TELEGRAM_BOT_TOKEN", ""):
            with unittest.mock.patch.object(settings, "TELEGRAM_CHAT_ID", ""):
                send_telegram_alert("Test message")
                mock_post.assert_not_called()

def test_send_telegram_alert_handles_exceptions_gracefully():
    # If requests raises an exception, send_telegram_alert catches it and doesn't crash
    with unittest.mock.patch("requests.post", side_effect=Exception("Connection timed out")):
        with unittest.mock.patch.object(settings, "TELEGRAM_BOT_TOKEN", "fake_token"):
            with unittest.mock.patch.object(settings, "TELEGRAM_CHAT_ID", "fake_chat_id"):
                # Should not raise exception
                send_telegram_alert("Test message")
