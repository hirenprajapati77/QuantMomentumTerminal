import uuid
import datetime
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from backend.app.storage.database import get_db
from backend.app.models.backtest import BacktestJob, BacktestTrade
from backend.app.services.backtest import run_backtest_background_task

router = APIRouter()

class BacktestRunRequest(BaseModel):
    score_threshold: float = Field(85.0, description="Minimum score to trigger entry (e.g. 85.0 for strategy, 60.0 for mechanism check)")
    time_stop_days: int = Field(30, description="Time stop window in calendar trading days (e.g. 30 days or 5 days)")
    initial_capital: float = Field(1000000.0, description="Initial capital for portfolio allocation")

class BacktestJobSchema(BaseModel):
    id: str
    status: str
    score_threshold: float
    time_stop_days: int
    initial_capital: float
    created_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None
    metrics: Optional[Any] = None
    error_message: Optional[str] = None

    class Config:
        orm_mode = True

class BacktestTradeSchema(BaseModel):
    id: int
    job_id: str
    symbol: str
    direction: str
    entry_date: str
    exit_date: Optional[str] = None
    entry_price: float
    exit_price: Optional[float] = None
    qty: float
    pnl: Optional[float] = None
    reason: Optional[str] = None

    class Config:
        orm_mode = True

@router.post("/run", response_model=BacktestJobSchema)
def run_backtest(
    payload: BacktestRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Spawns an asynchronous backtest simulator run with parameters.
    Returns a unique job_id immediately while calculations run in the background.
    """
    job_id = str(uuid.uuid4())
    
    # Create database entry
    job = BacktestJob(
        id=job_id,
        status="PENDING",
        score_threshold=payload.score_threshold,
        time_stop_days=payload.time_stop_days,
        initial_capital=payload.initial_capital,
        created_at=datetime.datetime.utcnow()
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Enqueue background task
    background_tasks.add_task(
        run_backtest_background_task,
        job_id=job_id,
        score_threshold=payload.score_threshold,
        time_stop_days=payload.time_stop_days,
        initial_capital=payload.initial_capital
    )
    
    return job

@router.get("/jobs", response_model=List[BacktestJobSchema])
def list_backtest_jobs(db: Session = Depends(get_db)):
    """
    List all historical and running backtest runs.
    """
    jobs = db.query(BacktestJob).order_by(BacktestJob.created_at.desc()).all()
    return jobs

@router.get("/jobs/{job_id}", response_model=BacktestJobSchema)
def get_backtest_job(job_id: str, db: Session = Depends(get_db)):
    """
    Retrieve execution state and aggregate performance metrics of a specific backtest.
    """
    job = db.query(BacktestJob).filter(BacktestJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Backtest job not found.")
    return job

@router.get("/jobs/{job_id}/trades", response_model=List[BacktestTradeSchema])
def get_backtest_job_trades(job_id: str, db: Session = Depends(get_db)):
    """
    Retrieve the full detailed list of trades executed during the backtest run.
    """
    job = db.query(BacktestJob).filter(BacktestJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Backtest job not found.")
        
    trades = db.query(BacktestTrade).filter(BacktestTrade.job_id == job_id).order_by(BacktestTrade.entry_date.asc(), BacktestTrade.id.asc()).all()
    
    response = []
    for t in trades:
        response.append({
            "id": t.id,
            "job_id": t.job_id,
            "symbol": t.symbol,
            "direction": t.direction,
            "entry_date": t.entry_date.strftime("%Y-%m-%d"),
            "exit_date": t.exit_date.strftime("%Y-%m-%d") if t.exit_date else None,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "qty": t.qty,
            "pnl": t.pnl,
            "reason": t.reason
        })
    return response
