from sqlalchemy import Column, String, Numeric, DateTime, Boolean
from backend.app.storage.database import Base
import datetime

class CompanyFundamental(Base):
    __tablename__ = "company_fundamentals"
    __table_args__ = {'extend_existing': True}

    symbol = Column(String(20), primary_key=True)
    sector = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)
    market_cap = Column(Numeric(precision=15, scale=2), nullable=True)  # in Cr
    sales_growth_qoq = Column(Numeric(precision=6, scale=2), nullable=True)
    sales_growth_yoy = Column(Numeric(precision=6, scale=2), nullable=True)
    profit_growth_yoy = Column(Numeric(precision=6, scale=2), nullable=True)
    roce = Column(Numeric(precision=6, scale=2), nullable=True)
    roe = Column(Numeric(precision=6, scale=2), nullable=True)
    debt_to_equity = Column(Numeric(precision=6, scale=2), nullable=True)
    institutional_holding = Column(Numeric(precision=6, scale=2), nullable=True)
    institutional_holding_qoq_change = Column(Numeric(precision=6, scale=2), nullable=True)
    promoter_pledge = Column(Numeric(precision=6, scale=2), nullable=True)
    under_surveillance = Column(Boolean, default=False)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<CompanyFundamental {self.symbol} Sector={self.sector} MC={self.market_cap} Cr>"
