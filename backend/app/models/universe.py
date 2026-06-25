from sqlalchemy import Column, String, Boolean, DateTime
from backend.app.storage.database import Base
import datetime

class UniverseStock(Base):
    __tablename__ = "universe_stocks"
    __table_args__ = {'extend_existing': True}

    symbol = Column(String(20), primary_key=True)
    is_active = Column(Boolean, default=True)  # True if passed all filters
    exclusion_reason = Column(String(250), nullable=True)  # Reason if failed
    last_refreshed = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<UniverseStock {self.symbol} Active={self.is_active} Reason={self.exclusion_reason}>"
