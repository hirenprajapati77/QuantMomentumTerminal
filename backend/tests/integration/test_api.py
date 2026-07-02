"""
Integration tests for all FastAPI endpoints.

Run with:
    PYTHONPATH=<project_root> python -m pytest backend/tests/integration/ -v

All imports use the canonical ``backend.app.*`` path (matching the production code).
"""
import datetime
import pytest

# ── 1. Patch init_db and start_scheduler BEFORE importing app.main ─────────────
import backend.app.storage.database as _db_module
import backend.app.services.scheduler as _sched_module

_db_module.init_db = lambda: None       # no DDL on production file during tests

async def _noop_scheduler():
    pass
_sched_module.start_scheduler = _noop_scheduler

# ── 2. Import models first so each registers exactly once on Base.metadata ──────
from backend.app.models.universe import UniverseStock
from backend.app.models.fundamental import CompanyFundamental
from backend.app.models.candle import DailyCandle
from backend.app.models.scan_result import ScanResult
from backend.app.models.backtest import BacktestJob, BacktestTrade

# ── 3. Now import app — models already registered; startup handler is a no-op ───
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.storage.database import Base, get_db

# ── 4. In-memory SQLite with StaticPool so ALL sessions share one connection ───
# Plain sqlite:///:memory: gives each connection its own empty DB.
# StaticPool forces every checkout to reuse the single underlying connection,
# so tables created by the fixture are visible to the request handler.
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
_db_module.SessionLocal = TestingSessionLocal

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# ── 5. Module-scoped fixture: DDL + seed data ──────────────────────────────────
@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=_test_engine)

    db = TestingSessionLocal()

    # Universe
    db.add_all([
        UniverseStock(symbol="RELIANCE", is_active=True),
        UniverseStock(symbol="TCS",      is_active=True),
        UniverseStock(symbol="ZOMATO",   is_active=False,
                      exclusion_reason="Listed history < 2 years"),
    ])

    # Fundamentals
    db.add_all([
        CompanyFundamental(symbol="RELIANCE", sector="Oil & Gas",
                           market_cap=1_800_000.0, promoter_pledge=0.0,
                           under_surveillance=False),
        CompanyFundamental(symbol="TCS", sector="IT Services",
                           market_cap=1_200_000.0, promoter_pledge=0.0,
                           under_surveillance=False),
    ])

    # Historical candles — 110 days so loc_idx >= 100 warmup check passes
    base = datetime.date(2026, 1, 1)
    for i in range(110):
        d = base + datetime.timedelta(days=i)
        db.add(DailyCandle(
            symbol="RELIANCE", date=d,
            open=2000.0 + i, high=2050.0 + i, low=1990.0 + i,
            close=2020.0 + i, volume=1_000_000 + i * 1_000,
            delivery_qty=600_000, delivery_pct=60.0
        ))
        db.add(DailyCandle(
            symbol="TCS", date=d,
            open=3000.0 - i, high=3040.0 - i, low=2980.0 - i,
            close=3020.0 - i, volume=500_000 + i * 500,
            delivery_qty=300_000, delivery_pct=60.0
        ))

    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=_test_engine)


# ── 6. Test client ────────────────────────────────────────────────────────────
client = TestClient(app)


# ── Tests ─────────────────────────────────────────────────────────────────────
def test_read_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_auth_status():
    r = client.get("/api/v1/auth/status")
    assert r.status_code == 200
    assert "authenticated" in r.json()


def test_auth_login_url():
    r = client.get("/api/v1/auth/login-url")
    assert r.status_code == 200
    assert "login_url" in r.json()


def test_universe_constituents():
    r = client.get("/api/v1/universe/constituents")
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["total_constituents"] == 3
    assert data["summary"]["active_constituents"] == 2
    assert data["summary"]["excluded_constituents"] == 1
    by_sym = {c["symbol"]: c for c in data["constituents"]}
    assert by_sym["RELIANCE"]["is_active"] is True
    assert by_sym["ZOMATO"]["is_active"]   is False
    assert by_sym["ZOMATO"]["exclusion_reason"] == "Listed history < 2 years"


def test_scanner_results_empty_initially():
    r = client.get("/api/v1/scanner/results")
    assert r.status_code == 200
    assert r.json() == []


def test_manual_scan_trigger_and_persistence():
    target = (datetime.date(2026, 1, 1) + datetime.timedelta(days=109)).strftime("%Y-%m-%d")

    r = client.post("/api/v1/scanner/scan", json={"date": target})
    assert r.status_code == 200
    results = r.json()
    assert len(results) >= 1

    db = TestingSessionLocal()
    db_rows = db.query(ScanResult).filter(
        ScanResult.date == datetime.datetime.strptime(target, "%Y-%m-%d").date()
    ).all()
    assert len(db_rows) == len(results)
    for row in db_rows:
        assert row.symbol in ("RELIANCE", "TCS")
        assert row.grade in ("Elite", "A+", "A", "Watch", "Reject")
    db.close()


def test_scanner_results_filterable_after_scan():
    r = client.get("/api/v1/scanner/results")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_scanner_results_grade_filter():
    r = client.get("/api/v1/scanner/results?grade=Reject")
    assert r.status_code == 200
    for row in r.json():
        assert row["grade"] == "Reject"


def test_scanner_results_symbol_filter():
    r = client.get("/api/v1/scanner/results?symbol=RELIANCE")
    assert r.status_code == 200
    for row in r.json():
        assert row["symbol"] == "RELIANCE"


def test_backtest_run_job_lifecycle():
    r = client.post("/api/v1/backtest/run", json={
        "score_threshold": 60.0,
        "time_stop_days": 5,
        "initial_capital": 1_000_000.0
    })
    assert r.status_code == 200
    job = r.json()
    assert job["status"] == "PENDING"
    job_id = job["id"]

    r = client.get("/api/v1/backtest/jobs")
    assert r.status_code == 200
    assert any(j["id"] == job_id for j in r.json())

    r = client.get(f"/api/v1/backtest/jobs/{job_id}")
    assert r.status_code == 200
    assert r.json()["id"] == job_id

    r = client.get(f"/api/v1/backtest/jobs/{job_id}/trades")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_backtest_job_not_found():
    r = client.get("/api/v1/backtest/jobs/nonexistent-uuid-1234")
    assert r.status_code == 404


def test_scanner_invalid_date_returns_400():
    r = client.post("/api/v1/scanner/scan", json={"date": "not-a-date"})
    assert r.status_code == 400


def test_get_candles():
    r = client.get("/api/v1/scanner/candles?symbol=RELIANCE&limit=10")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 10
    
    # Check fields
    c = data[0]
    assert "date" in c
    assert "open" in c
    assert "high" in c
    assert "low" in c
    assert "close" in c
    assert "volume" in c
    
    # Check chronological ordering (oldest first)
    date_first = datetime.datetime.strptime(data[0]["date"], "%Y-%m-%d")
    date_last = datetime.datetime.strptime(data[-1]["date"], "%Y-%m-%d")
    assert date_first < date_last


def test_get_last_run():
    # The DB may already have scan results from test_manual_scan_trigger_and_persistence.
    # We don't assert empty state; instead we seed a far-future date (2026-06-20) and
    # confirm that it becomes the MAX — proving the endpoint queries MAX(date) correctly.
    db = TestingSessionLocal()
    db.add(ScanResult(
        date=datetime.date(2026, 6, 20),
        symbol="RELIANCE",
        technical_score=90.0,
        fundamental_score=10.0,
        final_score=100.0,
        grade="Elite",
        entry_triggered=True,
        passes_fundamental=True
    ))
    db.commit()
    db.close()

    import unittest.mock
    with unittest.mock.patch("os.path.exists", return_value=False):
        r = client.get("/api/v1/scanner/last-run")
    assert r.status_code == 200
    ts = r.json()["timestamp"]
    assert ts is not None
    assert ts == 1781913600  # 2026-06-20 UTC midnight timestamp


def test_pending_to_filled_and_stopped_out_transitions():
    db = TestingSessionLocal()
    
    # 1. Seed a scan result that is Pending
    signal_date = datetime.date(2026, 6, 1)
    
    # Add target day candle for close reference
    db.add(DailyCandle(
        symbol="TEST_P", date=signal_date,
        open=100.0, high=105.0, low=98.0, close=102.0,
        volume=10000
    ))
    db.commit()
    
    scan_res = ScanResult(
        date=signal_date,
        symbol="TEST_P",
        technical_score=80.0,
        fundamental_score=10.0,
        final_score=90.0,
        grade="Elite",
        entry_triggered=True,
        passes_fundamental=True,
        sector="IT",
        entry=102.0,  # signal close
        entry_status="Pending",
        stop=102.0 * 0.94,
        target1=102.0 * 1.10,
        target2=102.0 * 1.20,
        target3=None,
        confidence="High",
        remarks="Test Pending",
        holding_days=0
    )
    db.add(scan_res)
    db.commit()
    
    # 2. Case A: Chronological next day candle exists and does NOT breach stop (e.g. Open=103, Low=100, Stop=102*0.94=95.88)
    next_date = datetime.date(2026, 6, 2)
    next_candle = DailyCandle(
        symbol="TEST_P", date=next_date,
        open=103.0, high=106.0, low=100.0, close=104.0,
        volume=12000
    )
    db.add(next_candle)
    db.commit()
    
    # Call resolve_pending_entries via ScannerService
    from backend.app.services.scanner import ScannerService
    scanner_service = ScannerService()
    scanner_service.resolve_pending_entries(db)
    
    # Assert it transitioned to Filled
    db.refresh(scan_res)
    assert scan_res.entry_status == "Filled"
    assert scan_res.entry == 103.0
    assert scan_res.stop == pytest.approx(103.0 * 0.94)
    assert scan_res.target1 == pytest.approx(103.0 * 1.10)
    assert scan_res.holding_days == 1
    
    # 3. Case B: Let's test Stopped Out. Seed another Pending result.
    signal_date_2 = datetime.date(2026, 6, 10)
    db.add(DailyCandle(
        symbol="TEST_S", date=signal_date_2,
        open=200.0, high=205.0, low=198.0, close=202.0,
        volume=10000
    ))
    db.commit()
    
    scan_res_2 = ScanResult(
        date=signal_date_2,
        symbol="TEST_S",
        technical_score=80.0,
        fundamental_score=10.0,
        final_score=90.0,
        grade="Elite",
        entry_triggered=True,
        passes_fundamental=True,
        sector="IT",
        entry=202.0,  # signal close
        entry_status="Pending",
        stop=202.0 * 0.94,
        target1=202.0 * 1.10,
        target2=202.0 * 1.20,
        target3=None,
        confidence="High",
        remarks="Test Stopped Out Pending",
        holding_days=0
    )
    db.add(scan_res_2)
    db.commit()
    
    # Chronological next day candle exists and breaches stop (e.g. Open=190.0, Low=170.0, Stop=190.0*0.94=178.6)
    next_date_2 = datetime.date(2026, 6, 11)
    next_candle_2 = DailyCandle(
        symbol="TEST_S", date=next_date_2,
        open=190.0, high=192.0, low=170.0, close=175.0,
        volume=12000
    )
    db.add(next_candle_2)
    db.commit()
    
    scanner_service.resolve_pending_entries(db)
    
    db.refresh(scan_res_2)
    assert scan_res_2.entry_status == "Stopped Out"
    assert scan_res_2.entry == 190.0
    assert scan_res_2.stop == pytest.approx(190.0 * 0.94)
    assert "Stopped Out on Entry Bar" in scan_res_2.remarks
    assert scan_res_2.holding_days == 1
    
    db.close()


