import os
import warnings
import json
from pathlib import Path
from dotenv import load_dotenv

# Load env file from the project root
env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=env_path)

class Settings:
    _FYERS_APP_ID: str = os.getenv("FYERS_APP_ID", "")
    _FYERS_SECRET_ID: str = os.getenv("FYERS_SECRET_ID", "")
    _FYERS_REDIRECT_URI: str = os.getenv("FYERS_REDIRECT_URI", "")
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgrespassword@localhost:5432/nse_scanner")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", "./data"))

    # Security Configuration
    SETTINGS_PIN: str = os.getenv("SETTINGS_PIN", "1234")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey")

    # Observability Alerts
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    @property
    def config_path(self) -> Path:
        return self.DATA_DIR / "fyers_config.json"

    @property
    def token_path(self) -> Path:
        return self.DATA_DIR / "fyers_token.txt"

    def _read_config(self, key: str, default: str) -> str:
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text())
                return data.get(key, default)
            except:
                pass
        return default

    @property
    def FYERS_APP_ID(self) -> str:
        return self._read_config("app_id", self._FYERS_APP_ID)

    @property
    def FYERS_SECRET_ID(self) -> str:
        raw_secret = self._read_config("secret_id", self._FYERS_SECRET_ID)
        if raw_secret and raw_secret != self._FYERS_SECRET_ID:
            from backend.app.core.crypto import decrypt_str
            try:
                return decrypt_str(raw_secret)
            except Exception as e:
                warnings.warn(f"Failed to decrypt FYERS_SECRET_ID, returning raw value: {e}", stacklevel=1)
        return raw_secret

    @property
    def FYERS_REDIRECT_URI(self) -> str:
        return self._read_config("redirect_uri", self._FYERS_REDIRECT_URI)

settings = Settings()

# Ensure data directory exists
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

import logging
logger = logging.getLogger("nse_scanner.config")

# Warn loudly if insecure defaults are in use
if settings.SETTINGS_PIN == "1234":
    logger.warning("SECURITY WARNING: SETTINGS_PIN is using the default '1234'. Set SETTINGS_PIN env var before production deployment.")
    warnings.warn(
        "SECURITY: SETTINGS_PIN is using the default '1234'. Set SETTINGS_PIN env var before production deployment.",
        stacklevel=1
    )
if settings.SECRET_KEY == "supersecretkey":
    logger.critical("SECURITY CRITICAL: SECRET_KEY is using the default value. This allows session tokens to be forged!")
    warnings.warn(
        "SECURITY: SECRET_KEY is using the default value. Set SECRET_KEY env var before production deployment.",
        stacklevel=1
    )
    # Refuse startup in production (if Database URL is PostgreSQL and not on localhost/127.0.0.1)
    db_url = settings.DATABASE_URL.lower()
    is_local_db = "localhost" in db_url or "127.0.0.1" in db_url or "sqlite" in db_url
    if not is_local_db:
        raise ValueError("CRITICAL SECURITY ERROR: Default SECRET_KEY is not allowed in production contexts. Please configure the SECRET_KEY environment variable.")
