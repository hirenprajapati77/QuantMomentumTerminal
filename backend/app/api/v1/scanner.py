import time
import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from backend.app.storage.database import get_db
from backend.app.models.scan_result import ScanResult
from backend.app.models.candle import DailyCandle
from backend.app.models.universe import UniverseStock
from backend.app.services.scanner import ScannerService

router = APIRouter()
scanner_service = ScannerService()

class ScanTriggerResponse(BaseModel):
    status: str
    message: str
    effective_date: Optional[str] = None
    mode: Optional[str] = None

class ScannerStatusResponse(BaseModel):
    is_running: bool



class ScanRequest(BaseModel):
    date: Optional[str] = Field(None, description="Date in YYYY-MM-DD format. Defaults to current date if not provided.")
    force_recompute: bool = Field(False, description="If true, bypasses the Redis signal cache and recomputes indicators fresh. Use after a data correction/backfill to guarantee no stale cached signals are reused.")
    ingest: bool = Field(
        True,
        description=(
            "If true (default), run catch-up market-data ingestion before scoring. "
            "Set false to score existing DB candles only."
        ),
    )

class ScanResultSchema(BaseModel):
    symbol: str
    date: str
    technical_score: float
    fundamental_score: float
    final_score: float
    grade: str
    entry_triggered: bool
    breakout_vol_ratio: Optional[float] = None
    close_pct_of_range: Optional[float] = None
    upper_wick_pct: Optional[float] = None
    passes_fundamental: bool
    
    # Trade-Plan Additions
    sector: Optional[str] = None
    entry: Optional[float] = None
    entry_status: Optional[str] = None
    stop: Optional[float] = None
    target1: Optional[float] = None
    target2: Optional[float] = None
    target3: Optional[float] = None
    confidence: Optional[str] = None
    remarks: Optional[str] = None
    holding_days: Optional[int] = None

    class Config:
        orm_mode = True

def run_scan_in_background(target_date: datetime.date, force_recompute: bool = False):
    from backend.app.storage.database import SessionLocal
    import logging
    logger = logging.getLogger("nse_scanner.api_background")
    db_bg = SessionLocal()
    try:
        scanner_service.run_daily_scan(db_bg, target_date, force_recompute=force_recompute)
    except Exception as e:
        logger.error(f"Error executing background scan for {target_date}: {e}", exc_info=True)
    finally:
        db_bg.close()


def run_ingest_and_scan_in_background(through_date: datetime.date):
    """Full pipeline: catch up missing candles + short history, then score."""
    import logging
    from backend.app.services.scheduler import sync_catch_up_pipeline
    logger = logging.getLogger("nse_scanner.api_background")
    try:
        sync_catch_up_pipeline(through_date)
    except Exception as e:
        logger.error(f"Error executing ingest+scan catch-up through {through_date}: {e}", exc_info=True)

@router.post("/scan", response_model=ScanTriggerResponse)
def trigger_scan(background_tasks: BackgroundTasks, payload: Optional[ScanRequest] = None):
    """
    Asynchronously trigger strategy scoring (and by default, market-data catch-up)
    for the active universe.
    """
    from zoneinfo import ZoneInfo
    target_date = datetime.datetime.now(ZoneInfo("Asia/Kolkata")).date()
    if payload and payload.date:
        try:
            target_date = datetime.datetime.strptime(payload.date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    
    from backend.app.services.scanner import is_scanner_running
    if is_scanner_running():
        raise HTTPException(status_code=409, detail="A scan is already in progress.")
        
    force_recompute = bool(payload and payload.force_recompute)
    do_ingest = True if payload is None else bool(payload.ingest)

    if do_ingest:
        background_tasks.add_task(run_ingest_and_scan_in_background, target_date)
        return {
            "status": "scanning",
            "mode": "ingest_and_scan",
            "effective_date": target_date.strftime("%Y-%m-%d"),
            "message": (
                f"Catch-up ingestion + scan triggered through {target_date.isoformat()}. "
                "This downloads missing market data before scoring."
            ),
        }

    background_tasks.add_task(run_scan_in_background, target_date, force_recompute)
    return {
        "status": "scanning",
        "mode": "scan_only",
        "effective_date": target_date.strftime("%Y-%m-%d"),
        "message": (
            f"Score-only scan triggered for {target_date.isoformat()} "
            "(falls back to latest candle date if that day has no data)."
        ),
    }

@router.get("/status", response_model=ScannerStatusResponse)
def get_scanner_status():
    """
    Get the current execution status of the background scanner.
    """
    from backend.app.services.scanner import is_scanner_running
    return {"is_running": is_scanner_running()}

@router.get("/results", response_model=List[ScanResultSchema])
def get_scan_results(
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    grade: Optional[str] = Query(None, description="Filter by grade (e.g. Elite, A+, A, Watch, Reject)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    db: Session = Depends(get_db)
):
    """
    Query historical scanner scores and signal logs from the database.
    """
    query = db.query(ScanResult)
    
    if start_date:
        try:
            s_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(ScanResult.date >= s_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")
            
    if end_date:
        try:
            e_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(ScanResult.date <= e_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD.")
            
    if grade:
        query = query.filter(ScanResult.grade == grade)
        
    if symbol:
        query = query.filter(ScanResult.symbol == symbol.upper())
        
    results = query.order_by(ScanResult.date.desc(), ScanResult.final_score.desc()).all()
    
    response = []
    for r in results:
        response.append({
            "symbol": r.symbol,
            "date": r.date.strftime("%Y-%m-%d"),
            "technical_score": r.technical_score,
            "fundamental_score": r.fundamental_score,
            "final_score": r.final_score,
            "grade": r.grade,
            "entry_triggered": r.entry_triggered,
            "breakout_vol_ratio": r.breakout_vol_ratio,
            "close_pct_of_range": r.close_pct_of_range,
            "upper_wick_pct": r.upper_wick_pct,
            "passes_fundamental": r.passes_fundamental,
            
            # Persistence additions
            "sector": r.sector,
            "entry": r.entry,
            "entry_status": r.entry_status,
            "stop": r.stop,
            "target1": r.target1,
            "target2": r.target2,
            "target3": r.target3,
            "confidence": r.confidence,
            "remarks": r.remarks,
            "holding_days": r.holding_days
        })
    return response

class CandleSchema(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    delivery_pct: Optional[float] = None

@router.get("/candles", response_model=List[CandleSchema])
def get_candles(
    symbol: str,
    limit: int = Query(150, description="Max candles to return"),
    db: Session = Depends(get_db)
):
    """
    Get historical EOD candles for a symbol, ordered chronologically.
    """
    candles = db.query(DailyCandle).filter(
        DailyCandle.symbol == symbol.upper()
    ).order_by(DailyCandle.date.desc()).limit(limit).all()
    
    # Reverse so they are in chronological order
    candles.reverse()
    
    return [
        {
            "date": c.date.strftime("%Y-%m-%d"),
            "open": float(c.open),
            "high": float(c.high),
            "low": float(c.low),
            "close": float(c.close),
            "volume": int(c.volume),
            "delivery_pct": float(c.delivery_pct) if c.delivery_pct is not None else None
        }
        for c in candles
    ]


class LastRunSchema(BaseModel):
    timestamp: Optional[int] = None

@router.get("/last-run", response_model=LastRunSchema)
def get_last_run(db: Session = Depends(get_db)):
    """
    Get the timestamp of the last successful daily scan execution.
    """
    import os
    import json
    
    # Try reading the actual execution timestamp first
    data_dir = os.getenv("DATA_DIR", "./data")
    last_run_path = os.path.join(data_dir, "last_run.json")
    if os.path.exists(last_run_path):
        try:
            with open(last_run_path, "r") as f:
                data = json.load(f)
                if "timestamp" in data:
                    return {"timestamp": data["timestamp"]}
        except Exception:
            pass
            
    # Fallback to database max_date combining
    from sqlalchemy import func
    import datetime
    
    max_date = db.query(func.max(ScanResult.date)).scalar()
    if max_date:
        dt = datetime.datetime.combine(max_date, datetime.time.min)
        timestamp = int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())
        return {"timestamp": timestamp}
            
    return {"timestamp": None}


class DataHealthSchema(BaseModel):
    last_candle_date: Optional[str] = None
    last_scan_date: Optional[str] = None
    active_symbols: int
    symbols_with_min_history: int
    symbols_scored_on_last_candle: int
    min_history_candles: int
    calendar_days_behind: Optional[int] = None
    is_stale: bool
    warning: Optional[str] = None


@router.get("/data-health", response_model=DataHealthSchema)
def get_data_health(db: Session = Depends(get_db)):
    """
    Operational snapshot of market-data freshness and scoreable universe coverage.
    Use this to detect stalled ingestion (no new candles) vs. true zero-signal days.
    """
    from zoneinfo import ZoneInfo
    from backend.app.services.scheduler import MIN_HISTORY_CANDLES, get_short_history_symbols

    today = datetime.datetime.now(ZoneInfo("Asia/Kolkata")).date()
    active_symbols = [
        s.symbol for s in db.query(UniverseStock).filter(UniverseStock.is_active == True).all()
    ]
    active_count = len(active_symbols)

    last_candle = db.query(func.max(DailyCandle.date)).scalar()
    last_scan = db.query(func.max(ScanResult.date)).scalar()

    # Cache short history count for 60s to prevent repeated heavy GROUP BY queries
    global _short_history_cache
    now = time.time()
    if '_short_history_cache' not in globals() or (now - _short_history_cache.get("timestamp", 0)) > 60:
        short = get_short_history_symbols(db, active_symbols, MIN_HISTORY_CANDLES) if active_symbols else []
        _short_history_cache = {"timestamp": now, "short_count": len(short)}
    short_count = _short_history_cache.get("short_count", 0)
    sufficient = active_count - short_count

    scored_on_last = 0
    if last_candle is not None:
        scored_on_last = db.query(func.count(ScanResult.id)).filter(
            ScanResult.date == last_candle
        ).scalar() or 0

    days_behind = (today - last_candle).days if last_candle is not None else None
    # Normal trading calendar lag (Saturday=5, Sunday=6, Monday=0):
    # - Saturday: 1 day lag from Friday (days_behind <= 1)
    # - Sunday: 2 days lag from Friday (days_behind <= 2)
    # - Monday (before EOD scan): 3 days lag from Friday (days_behind <= 3)
    is_normal_trading_lag = False
    if last_candle is not None and days_behind is not None:
        w = today.weekday()
        if w == 5 and days_behind <= 1:
            is_normal_trading_lag = True
        elif w == 6 and days_behind <= 2:
            is_normal_trading_lag = True
        elif w == 0 and days_behind <= 3:
            is_normal_trading_lag = True

    is_stale = days_behind is None or (days_behind > 3 and not is_normal_trading_lag)

    warning = None
    if last_candle is None:
        warning = "No candle data in database. Run ingest+scan after Fyers auth."
    elif days_behind and days_behind > 1 and not is_normal_trading_lag:
        warning = (
            f"Market data is {days_behind} calendar days behind "
            f"(last candle {last_candle.isoformat()}). Catch-up ingestion required."
        )
    elif active_count > 0 and (sufficient / active_count) < 0.90:
        warning = (
            f"{active_count - sufficient} active symbols have fewer than "
            f"{MIN_HISTORY_CANDLES} candles and cannot score trend/VCP reliably."
        )

    return {
        "last_candle_date": last_candle.isoformat() if last_candle else None,
        "last_scan_date": last_scan.isoformat() if last_scan else None,
        "active_symbols": active_count,
        "symbols_with_min_history": sufficient,
        "symbols_scored_on_last_candle": scored_on_last,
        "min_history_candles": MIN_HISTORY_CANDLES,
        "calendar_days_behind": days_behind,
        "is_stale": is_stale,
        "warning": warning,
    }

