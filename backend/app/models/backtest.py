import datetime
from sqlalchemy import Column, Integer, String, Date, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.storage.database import Base

class BacktestJob(Base):
    __tablename__ = "backtest_jobs"
    __table_args__ = {'extend_existing': True}

    id = Column(String(36), primary_key=True)
    status = Column(String(20), default="PENDING", nullable=False) # PENDING, RUNNING, COMPLETED, FAILED
    score_threshold = Column(Float, nullable=False)
    time_stop_days = Column(Integer, nullable=False)
    initial_capital = Column(Float, nullable=False)
    metrics = Column(JSON, nullable=True) # Win rate, CAGR, Sharpe, drawdown, expectancy, total trades, equity curve, etc.
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)

    trades = relationship("BacktestTrade", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BacktestJob {self.id}: Status={self.status} Created={self.created_at}>"

class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), ForeignKey("backtest_jobs.id", ondelete="CASCADE"), index=True, nullable=False)
    symbol = Column(String(20), index=True, nullable=False)
    direction = Column(String(20), nullable=False) # BUY, SELL_PARTIAL, SELL_FINAL
    entry_date = Column(Date, nullable=False)
    exit_date = Column(Date, nullable=True)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    qty = Column(Float, nullable=False)
    pnl = Column(Float, nullable=True)
    reason = Column(String(50), nullable=True) # Stop Loss, Trailing Stop, Target 1, Target 2, Time Stop, Structure Failure, Distribution Exit

    job = relationship("BacktestJob", back_populates="trades")

    def __repr__(self):
        return f"<BacktestTrade {self.symbol} {self.direction}: Qty={self.qty} PnL={self.pnl} Reason={self.reason}>"
