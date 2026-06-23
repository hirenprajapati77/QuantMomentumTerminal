from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from backend.app.config.settings import settings
import logging

logger = logging.getLogger("nse_scanner.database")

if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    try:
        # Import all models to ensure they are registered on the Base metadata before creation
        from backend.app.models.candle import DailyCandle
        from backend.app.models.fundamental import CompanyFundamental
        from backend.app.models.universe import UniverseStock
        from backend.app.models.scan_result import ScanResult
        from backend.app.models.backtest import BacktestJob, BacktestTrade

        # Create all tables if they don't exist
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized and tables created successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}", exc_info=True)
        raise
