import logging
import requests as req
from backend.app.config.settings import settings

logger = logging.getLogger("nse_scanner.alerts")

def send_telegram_alert(message: str) -> None:
    """Send a Telegram alert. Silently fails if credentials not configured."""
    try:
        token = settings.TELEGRAM_BOT_TOKEN
        chat_id = settings.TELEGRAM_CHAT_ID
        if not token or not chat_id:
            return
        
        res = req.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=5
        )
        if res.status_code != 200:
            logger.error(f"Failed to send Telegram alert: HTTP {res.status_code} - {res.text}")
    except Exception as e:
        logger.error(f"Error dispatching Telegram alert: {e}")
        pass  # Never let alerting break the main application execution
