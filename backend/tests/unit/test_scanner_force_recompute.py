import datetime
import unittest.mock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.storage.database import Base
from backend.app.models.universe import UniverseStock
from backend.app.models.fundamental import CompanyFundamental
from backend.app.models.candle import DailyCandle
from backend.app.services.scanner import ScannerService

# ── Setup in-memory SQLite DB ──
_test_engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(bind=_test_engine)

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=_test_engine)
    db = TestingSessionLocal()
    # Seed minimal data for 1 active symbol
    db.add(UniverseStock(symbol="TEST_SYM", is_active=True))
    db.add(CompanyFundamental(symbol="TEST_SYM", sector="IT", market_cap=1000.0, promoter_pledge=0.0, under_surveillance=False))
    
    # Seed 110 candles so candidates fast-filter pass
    # Fast filter: volume_ratio >= 2.0 and close_pct >= 0.85 and upper_wick_pct <= 0.15
    # Let's seed candles where the last day triggers a breakout
    base = datetime.date(2026, 1, 1)
    for i in range(110):
        d = base + datetime.timedelta(days=i)
        if i == 109:
            # Breakout day: High=105, Low=98, Close=104, Open=100
            db.add(DailyCandle(
                symbol="TEST_SYM", date=d,
                open=100.0, high=105.0, low=98.0, close=104.0,
                volume=2500000, delivery_qty=1500000, delivery_pct=60.0
            ))
        else:
            # Baseline day
            db.add(DailyCandle(
                symbol="TEST_SYM", date=d,
                open=100.0, high=102.0, low=99.0, close=100.0,
                volume=1000000, delivery_qty=600000, delivery_pct=60.0
            ))
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=_test_engine)

def test_scanner_force_recompute():
    db = TestingSessionLocal()
    target_date = datetime.date(2026, 1, 1) + datetime.timedelta(days=109)
    
    scanner_service = ScannerService()
    
    # Mock Redis client
    mock_redis = unittest.mock.MagicMock()
    # Cache initially empty
    mock_redis.get.return_value = None
    
    # Mock _get_redis helper function
    with unittest.mock.patch("backend.app.services.scanner._get_redis", return_value=mock_redis):
        # Mock calculate_raw_signals to count calls
        with unittest.mock.patch("backend.app.services.scanner.calculate_raw_signals") as mock_calc:
            mock_calc.return_value = {
                "sector": "IT",
                "trend": {"score": 15, "status": "passed"},
                "vcp": {"score": 20, "status": "passed"},
                "vdu": {"score": 15},
                "rs_raw": {"rel_20": 0.05, "rel_50": 0.10, "rel_100": 0.15},
                "volume": {"score": 10, "ratio": 2.5},
                "breakout": {"score": 10, "close_pct_of_range": 0.90, "upper_wick_pct": 0.05},
                "cpr": {"score": 5},
                "fundamental": {"score": 10, "passes_gate": True}
            }
            
            # --- First Scan: should miss cache, calculate raw signals, and write to cache ---
            scanner_service.run_daily_scan(db, target_date, force_recompute=False)
            assert mock_calc.call_count == 1
            # Verify it wrote to cache
            mock_redis.setex.assert_called_once()
            mock_redis.setex.reset_mock()
            
            # Now simulate cache hit for subsequent calls
            mock_redis.get.return_value = '{"sector": "IT"}'
            
            # --- Second Scan (Normal): should hit cache and NOT call calculate_raw_signals ---
            mock_calc.reset_mock()
            scanner_service.run_daily_scan(db, target_date, force_recompute=False)
            assert mock_calc.call_count == 0
            
            # --- Third Scan (Force Recompute): should bypass cache, call calculate_raw_signals, and overwrite cache ---
            mock_calc.reset_mock()
            scanner_service.run_daily_scan(db, target_date, force_recompute=True)
            assert mock_calc.call_count == 1
            # Verify it set the cache again
            mock_redis.setex.assert_called_once()
            
    db.close()
