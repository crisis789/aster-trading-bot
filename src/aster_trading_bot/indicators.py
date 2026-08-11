"""
Technical indicators — pure functions, no network I/O.
Used by example strategies and unit tests.

All functions accept a list of floats and return a list aligned with
the input (leading values are None where the window is not full).
"""
from typing import List, Optional, Tuple


def ema_series(vals: List[float], n: int) -> Optional[List[Optional[float]]]:
    """Exponential moving average series (EMA), seeded with SMA of first n values."""
    if len(vals) < n or n <= 0:
        return None
    k = 2.0 / (n + 1)
    out: List[Optional[float]] = [None] * (n - 1)
    e = sum(vals[:n]) / n
    out.append(e)
    for v in vals[n:]:
        e = v * k + e * (1 - k)
        out.append(e)
    return out


def sma_series(vals: List[float], n: int) -> Optional[List[Optional[float]]]:
    """Simple moving average series."""
    if len(vals) < n or n <= 0:
        return None
    out: List[Optional[float]] = [None] * (n - 1)
    for i in range(n - 1, len(vals)):
        out.append(sum(vals[i - n + 1:i + 1]) / n)
    return out


def rsi_series(vals: List[float], period: int = 14) -> Optional[List[Optional[float]]]:
    """Relative Strength Index (Wilder's smoothing). Range 0-100."""
    if len(vals) < period + 1 or period <= 0:
        return None
    out: List[Optional[float]] = [None] * period
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        diff = vals[i] - vals[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    out.append(100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss))
    for i in range(period + 1, len(vals)):
        diff = vals[i] - vals[i - 1]
        gain = diff if diff > 0 else 0.0
        loss = -diff if diff < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out.append(100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss))
    return out


def bollinger_bands(vals: List[float], period: int = 20,
                    mult: float = 2.0) -> Optional[Tuple[List[Optional[float]], ...]]:
    """Bollinger Bands: (upper, middle, lower). Middle = SMA(period)."""
    mid = sma_series(vals, period)
    if mid is None:
        return None
    upper: List[Optional[float]] = []
    lower: List[Optional[float]] = []
    for i in range(len(vals)):
        m = mid[i]
        if m is None:
            upper.append(None)
            lower.append(None)
            continue
        window = vals[i - period + 1:i + 1]
        var = sum((x - m) ** 2 for x in window) / period
        sd = var ** 0.5
        upper.append(m + mult * sd)
        lower.append(m - mult * sd)
    return (upper, mid, lower)


def atr_series(highs: List[float], lows: List[float],
               closes: List[float], period: int = 14) -> Optional[List[Optional[float]]]:
    """Average True Range (Wilder's smoothing)."""
    n = len(closes)
    if n < period + 1 or period <= 0:
        return None
    trs: List[float] = []
    for i in range(1, n):
        h, l, pc = highs[i], lows[i], closes[i - 1]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    # TR[j] corresponds to candle j+1 (closes[j+1]); first valid ATR at index `period`
    out: List[Optional[float]] = [None] * n
    if len(trs) < period:
        return out
    atr = sum(trs[:period]) / period
    out[period] = atr
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
        out[i + 1] = atr
    return out
