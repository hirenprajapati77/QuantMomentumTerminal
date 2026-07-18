"""
Read-only diagnostic: fundamental/sector coverage vs active universe.

Usage (on host with DATABASE_URL, or inside backend container):
    PYTHONPATH=/app python -m backend.scripts.diagnose_zero_signals
    # or
    PYTHONPATH=<repo_root> python backend/scripts/diagnose_zero_signals.py
"""
from backend.app.storage.database import SessionLocal
from backend.app.models.fundamental import CompanyFundamental
from backend.app.models.universe import UniverseStock

db = SessionLocal()
total_universe = db.query(UniverseStock).filter(UniverseStock.is_active == True).count()
funds = db.query(CompanyFundamental).all()

print(f"Active universe symbols: {total_universe}")
print(f"company_fundamentals rows: {len(funds)}")

sector_counts = {}
field_null_counts = {"sector": 0, "sales_growth_qoq": 0, "sales_growth_yoy": 0,
                      "profit_growth_yoy": 0, "roce": 0, "roe": 0,
                      "debt_to_equity": 0, "institutional_holding_qoq_change": 0}
for f in funds:
    sec = f.sector or "NULL"
    sector_counts[sec] = sector_counts.get(sec, 0) + 1
    for k in field_null_counts:
        if getattr(f, k) is None:
            field_null_counts[k] += 1

print("Sector distribution:", sector_counts)
print("Null counts per field (out of", len(funds), "):")
for k, v in field_null_counts.items():
    print(f"  {k}: {v} null")

# symbols in universe with NO fundamentals row at all
fund_symbols = {f.symbol for f in funds}
universe_symbols = {u.symbol for u in db.query(UniverseStock).filter(UniverseStock.is_active == True).all()}
missing = universe_symbols - fund_symbols
print(f"Active symbols with NO fundamentals row: {len(missing)} -> {sorted(missing)[:20]}")

# Help follow-up Screener checks: list symbols whose sector is NULL
null_sector_symbols = sorted(f.symbol for f in funds if f.sector is None)
print(f"Fundamentals rows with sector NULL: {len(null_sector_symbols)} -> {null_sector_symbols[:20]}")
db.close()
