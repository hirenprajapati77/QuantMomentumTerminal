from sqlalchemy import Column, String, Date, Numeric, BigInteger
from backend.app.storage.database import Base

class DailyCandle(Base):
    __tablename__ = "daily_candles"
    __table_args__ = {'extend_existing': True}

    symbol = Column(String(20), primary_key=True, index=True)
    date = Column(Date, primary_key=True, index=True)
    open = Column(Numeric(precision=10, scale=2), nullable=False)
    high = Column(Numeric(precision=10, scale=2), nullable=False)
    low = Column(Numeric(precision=10, scale=2), nullable=False)
    close = Column(Numeric(precision=10, scale=2), nullable=False)
    volume = Column(BigInteger, nullable=False)
    delivery_qty = Column(BigInteger, nullable=True)
    delivery_pct = Column(Numeric(precision=5, scale=2), nullable=True)

    def __repr__(self):
        return f"<DailyCandle {self.symbol} on {self.date}: C={self.close} V={self.volume} Del={self.delivery_pct}%>"
