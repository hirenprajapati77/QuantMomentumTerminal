import sys
import logging
from backend.app.config.settings import settings

def setup_logging():
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(settings.DATA_DIR / "app.log")
        ]
    )

setup_logging()
logger = logging.getLogger("nse_scanner")
