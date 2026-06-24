import math
from typing import Any


def get_safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert a value to float, returning default on None/NaN/error."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default
