"""Unit tests for scan-date fallback and catch-up helpers."""
import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.storage.database import Base
from backend.app.models.universe import UniverseStock
from backend.app.models.candle import DailyCandle
from backend.app.services.scanner import ScannerService
from backend.app.services.scheduler import (
    iter_weekdays,
    get_short_history_symbols,
    MIN_HISTORY_CANDLES,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_iter_weekdays_skips_weekends():
    days = list(iter_weekdays(datetime.date(2026, 7, 3), datetime.date(2026, 7, 7)))
    assert days == [
        datetime.date(2026, 7, 3),  # Fri
        datetime.date(2026, 7, 6),  # Mon
        datetime.date(2026, 7, 7),  # Tue
    ]


def test_resolve_effective_scan_date_falls_back_when_target_missing(db):
    db.add(UniverseStock(symbol="AAA", is_active=True))
    db.add(DailyCandle(
        symbol="AAA", date=datetime.date(2026, 7, 3),
        open=10, high=11, low=9, close=10.5, volume=1000
    ))
    db.commit()

    effective = ScannerService.resolve_effective_scan_date(db, datetime.date(2026, 7, 17))
    assert effective == datetime.date(2026, 7, 3)


def test_resolve_effective_scan_date_keeps_target_when_present(db):
    db.add(UniverseStock(symbol="AAA", is_active=True))
    for d in (datetime.date(2026, 7, 2), datetime.date(2026, 7, 3)):
        db.add(DailyCandle(
            symbol="AAA", date=d,
            open=10, high=11, low=9, close=10.5, volume=1000
        ))
    db.commit()

    effective = ScannerService.resolve_effective_scan_date(db, datetime.date(2026, 7, 3))
    assert effective == datetime.date(2026, 7, 3)


def test_get_short_history_symbols(db):
    db.add_all([
        UniverseStock(symbol="LONG", is_active=True),
        UniverseStock(symbol="SHORT", is_active=True),
        UniverseStock(symbol="EMPTY", is_active=True),
    ])
    base = datetime.date(2026, 1, 1)
    for i in range(MIN_HISTORY_CANDLES):
        db.add(DailyCandle(
            symbol="LONG", date=base + datetime.timedelta(days=i),
            open=1, high=2, low=1, close=1.5, volume=100
        ))
    for i in range(26):
        db.add(DailyCandle(
            symbol="SHORT", date=base + datetime.timedelta(days=i),
            open=1, high=2, low=1, close=1.5, volume=100
        ))
    db.commit()

    short = get_short_history_symbols(db, ["LONG", "SHORT", "EMPTY"])
    assert set(short) == {"SHORT", "EMPTY"}
