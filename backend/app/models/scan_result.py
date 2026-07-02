from sqlalchemy import Column, Integer, String, Date, Float, Boolean, UniqueConstraint
from backend.app.storage.database import Base

class ScanResult(Base):
    __tablename__ = "scan_results"
    __table_args__ = (
        UniqueConstraint('symbol', 'date', name='uq_scan_result_symbol_date'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, index=True, nullable=False)
    symbol = Column(String(20), index=True, nullable=False)
    technical_score = Column(Float, nullable=False)
    fundamental_score = Column(Float, nullable=False)
    final_score = Column(Float, nullable=False)
    grade = Column(String(10), nullable=False)  # Elite, A+, A, Watch, Reject
    entry_triggered = Column(Boolean, default=False)
    breakout_vol_ratio = Column(Float, nullable=True)
    close_pct_of_range = Column(Float, nullable=True)
    upper_wick_pct = Column(Float, nullable=True)
    passes_fundamental = Column(Boolean, default=False)

    # Trade-Plan Persistence Fields
    sector = Column(String(50), nullable=True)
    entry = Column(Float, nullable=True)
    entry_status = Column(String(15), index=True, nullable=True)  # Pending, Filled, Stopped Out
    stop = Column(Float, nullable=True)
    target1 = Column(Float, nullable=True)
    target2 = Column(Float, nullable=True)
    target3 = Column(Float, nullable=True)  # trailing stop price once active
    confidence = Column(String(10), nullable=True)  # High, Medium, Low, None
    remarks = Column(String(250), nullable=True)
    holding_days = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<ScanResult {self.symbol} on {self.date}: Score={self.final_score} Grade={self.grade} Entry={self.entry_triggered} Status={self.entry_status}>"
