# ================== TECHNICAL INDICATORS MODULE ==================
"""
Teknik analiz göstergeleri - RSI, ADX, ATR, Bollinger Bands, vb.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average hesapla"""
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index hesapla"""
    delta = series.diff()
    up = delta.clip(lower=0.0)
    down = (-delta).clip(lower=0.0)
    
    roll_up = up.rolling(period).mean()
    roll_down = down.rolling(period).mean()
    
    rs = roll_up / (roll_down + 1e-12)
    return 100 - (100 / (1 + rs))


def atr_wilder(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's Average True Range hesapla"""
    prev_close = close.shift(1)
    
    tr1 = np.abs((high - low).to_numpy())
    tr2 = np.abs((high - prev_close).to_numpy())
    tr3 = np.abs((low - prev_close).to_numpy())
    
    tr = pd.Series(np.maximum.reduce([tr1, tr2, tr3]), index=close.index)
    return tr.ewm(alpha=1/period, adjust=False).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average Directional Index hesapla"""
    up = high.diff()
    down = -low.diff()
    
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    
    atr = atr_wilder(high, low, close, period)
    
    plus_di = 100 * pd.Series(plus_dm, index=close.index).ewm(
        alpha=1/period, adjust=False
    ).mean() / (atr + 1e-12)
    
    minus_di = 100 * pd.Series(minus_dm, index=close.index).ewm(
        alpha=1/period, adjust=False
    ).mean() / (atr + 1e-12)
    
    dx = (np.abs(plus_di - minus_di) / ((plus_di + minus_di) + 1e-12)) * 100
    
    return pd.Series(dx, index=close.index).ewm(alpha=1/period, adjust=False).mean()


def bollinger(close: pd.Series, period: int = 20, k: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands hesapla
    
    Returns:
        middle, upper, lower, bandwidth, std
    """
    middle = close.rolling(period).mean()
    std = close.rolling(period).std(ddof=0)
    
    upper = middle + k * std
    lower = middle - k * std
    
    bandwidth = (upper - lower) / (middle + 1e-12)
    
    return middle, upper, lower, bandwidth, std


def donchian(high: pd.Series, low: pd.Series, window: int = 20) -> Tuple[pd.Series, pd.Series]:
    """Donchian Channel hesapla
    
    Returns:
        upper_channel, lower_channel
    """
    upper = high.rolling(window).max()
    lower = low.rolling(window).min()
    
    return upper, lower


def body_strength(open_prices: pd.Series, close: pd.Series, high: pd.Series, low: pd.Series) -> pd.Series:
    """Mum gövde gücü hesapla (body/range oranı)"""
    def _series_like(x, idx):
        return x if isinstance(x, pd.Series) else pd.Series(x, index=idx)
    
    open_prices = _series_like(open_prices, close.index)
    high = _series_like(high, close.index)
    low = _series_like(low, close.index)
    
    body = np.abs(close.to_numpy() - open_prices.to_numpy())
    range_val = np.abs(high.to_numpy() - low.to_numpy())
    
    range_val[range_val == 0] = np.nan
    val = body / range_val
    
    return pd.Series(np.nan_to_num(val, nan=0.0), index=close.index)


def swing_high(highs: pd.Series, window: int = 10) -> float:
    """Swing high hesapla"""
    return float(highs.iloc[-window:].max())


def swing_low(lows: pd.Series, window: int = 10) -> float:
    """Swing low hesapla"""
    return float(lows.iloc[-window:].min())


def find_swings(high: pd.Series, low: pd.Series, left: int = 2, right: int = 2) -> Tuple[list, list]:
    """Swing high ve low noktalarını bul"""
    swing_highs_idx = []
    swing_lows_idx = []
    
    for i in range(left, len(high) - right):
        window_high = high.iloc[i-left:i+right+1]
        window_low = low.iloc[i-left:i+right+1]
        
        if high.iloc[i] == window_high.max() and (window_high.idxmax() == high.index[i]):
            swing_highs_idx.append(i)
            
        if low.iloc[i] == window_low.min() and (window_low.idxmin() == low.index[i]):
            swing_lows_idx.append(i)
    
    return swing_highs_idx, swing_lows_idx


def find_fvgs(high: pd.Series, low: pd.Series, lookback: int = 20) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
    """Fair Value Gap (FVG) bul
    
    Returns:
        bull_fvg, bear_fvg
    """
    bulls = []
    bears = []
    
    start = max(2, len(high) - lookback)
    
    for i in range(start, len(high)):
        try:
            # Bullish FVG: current low > high 2 bars ago
            if low.iloc[i] > high.iloc[i-2]:
                bulls.append((high.iloc[i-2], low.iloc[i]))
                
            # Bearish FVG: current high < low 2 bars ago
            if high.iloc[i] < low.iloc[i-2]:
                bears.append((high.iloc[i], low.iloc[i-2]))
        except:
            pass
    
    bull_fvg = bulls[-1] if bulls else None
    bear_fvg = bears[-1] if bears else None
    
    return bull_fvg, bear_fvg
