import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config.settings import settings
from backend.app.storage.database import init_db
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.scanner import router as scanner_router
from backend.app.api.v1.backtest import router as backtest_router
from backend.app.api.v1.universe import router as universe_router
from backend.app.api.v1.settings import router as settings_router
from backend.app.services.scheduler import start_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.LOG_LEVEL == "INFO" else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("nse_scanner.main")

app = FastAPI(
    title="NSE India Equity Momentum Scanner API",
    description="Backend service layer for composite strategy indicators, scanners, and backtesting simulator.",
    version="1.0.0"
)

# Configure CORS Middleware for dashboard integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local/production dashboard UI
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
# Include auth router as both /api/v1/auth and /api/v1/fyers to support whatever callback redirect URI is configured
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(auth_router, prefix="/api/v1/fyers", tags=["Authentication Callback"])
app.include_router(scanner_router, prefix="/api/v1/scanner", tags=["Scanner"])
app.include_router(backtest_router, prefix="/api/v1/backtest", tags=["Backtesting"])
app.include_router(universe_router, prefix="/api/v1/universe", tags=["Universe"])
app.include_router(settings_router, prefix="/api/v1/settings", tags=["Settings"])

@app.on_event("startup")
async def on_startup():
    logger.info("Initializing database...")
    init_db()
    
    logger.info("Starting Daily Ingestion Scheduler...")
    # Start scheduler background task
    asyncio.create_task(start_scheduler())
    logger.info("Startup sequence completed successfully!")

@app.get("/")
def read_root():
    return {
        "status": "healthy",
        "app": "NSE India Equity Momentum Scanner API",
        "version": "1.0.0"
    }
