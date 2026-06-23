class ScannerException(Exception):
    """Base exception for NSE Momentum Scanner"""
    pass

class FyersAuthException(ScannerException):
    """Exception raised when Fyers API authentication fails"""
    pass

class FyersTokenExpiredException(FyersAuthException):
    """Exception raised when the Fyers access token is expired or missing"""
    pass

class IngestionException(ScannerException):
    """Exception raised when data ingestion fails"""
    pass
