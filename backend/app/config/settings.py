import os
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
        return self._read_config("secret_id", self._FYERS_SECRET_ID)

    @property
    def FYERS_REDIRECT_URI(self) -> str:
        return self._read_config("redirect_uri", self._FYERS_REDIRECT_URI)

settings = Settings()

# Ensure data directory exists
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
