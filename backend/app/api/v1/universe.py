from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.storage.database import get_db
from backend.app.models.universe import UniverseStock

router = APIRouter()

@router.get("/constituents")
def get_constituents(db: Session = Depends(get_db)):
    """
    Get all Nifty 500 constituents with their active status and exclusion reasons.
    """
    stocks = db.query(UniverseStock).order_by(UniverseStock.symbol.asc()).all()
    
    total = len(stocks)
    active = sum(1 for s in stocks if s.is_active)
    excluded = total - active
    
    constituents = [
        {
            "symbol": s.symbol,
            "is_active": s.is_active,
            "exclusion_reason": s.exclusion_reason,
            "last_refreshed": s.last_refreshed
        }
        for s in stocks
    ]
    
    return {
        "summary": {
            "total_constituents": total,
            "active_constituents": active,
            "excluded_constituents": excluded
        },
        "constituents": constituents
    }
