import os
from pathlib import Path
from dotenv import load_dotenv

# Load env file from the project root
env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=env_path)

class Settings:
    FYERS_APP_ID: str = os.getenv("FYERS_APP_ID", "")
    FYERS_SECRET_ID: str = os.getenv("FYERS_SECRET_ID", "")
    FYERS_REDIRECT_URI: str = os.getenv("FYERS_REDIRECT_URI", "")
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgrespassword@localhost:5432/nse_scanner")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", "./data"))

    @property
    def token_path(self) -> Path:
        return self.DATA_DIR / "fyers_token.txt"

settings = Settings()

# Ensure data directory exists
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
