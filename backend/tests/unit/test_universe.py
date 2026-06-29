import pytest
import pandas as pd
from unittest.mock import MagicMock
from app.services.universe import UniverseService

def test_check_listing_history_2y_below_boundary():
    service = UniverseService()
    # Mock fetch_fyers_ohlcv to return 390 days (below the 400-day threshold)
    mock_df = pd.DataFrame([{"close": 100.0}] * 390)
    service.market_data_service.fetch_fyers_ohlcv = MagicMock(return_value=mock_df)
    
    assert service.check_listing_history_2y("TEST_SYM") is False

def test_check_listing_history_2y_above_boundary():
    service = UniverseService()
    # Mock fetch_fyers_ohlcv to return 410 days (above the 400-day threshold)
    mock_df = pd.DataFrame([{"close": 100.0}] * 410)
    service.market_data_service.fetch_fyers_ohlcv = MagicMock(return_value=mock_df)
    
    assert service.check_listing_history_2y("TEST_SYM") is True

def test_check_listing_history_2y_exact_boundary():
    service = UniverseService()
    # The check is: len(df) >= 400.
    # Therefore, exactly 400 days should return True.
    mock_df = pd.DataFrame([{"close": 100.0}] * 400)
    service.market_data_service.fetch_fyers_ohlcv = MagicMock(return_value=mock_df)
    
    assert service.check_listing_history_2y("TEST_SYM") is True
