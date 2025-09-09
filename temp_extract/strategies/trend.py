# ================== TREND STRATEGY ==================
"""
Trend takip stratejisi - Donchian kırılımları, retest, momentum
"""

import math
from typing import Optional, Dict, Any
import pandas as pd

from .base import BaseStrategy
from ..indicators.technical import (
    atr_wilder, adx, body_strength, bollinger, donchian, ema
)
from ..utils.risk_management import compute_sl_tp_atr
from ..utils.helpers import sigmoid
from ..config.settings import (
    ADX_TREND_MIN, ONEH_DISP_BODY_MIN, ONEH_DISP_LOOKBACK,
    DONCHIAN_WIN, BREAK_BUFFER, RETEST_TOL_ATR, ATR_PERIOD
)


class TrendStrategy(BaseStrategy):
    """Trend takip stratejisi"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("TREND", config)
    
    def get_regime(self) -> str:
        return "TREND"
    
    def analyze(self, df_ltf: pd.DataFrame, df_htf: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
        """Trend analizi yap"""
        if not self.validate_data(df_ltf, df_htf):
            return None
        
        # HTF kapı kontrolü
        htf_bias, disp_ok, adx1h, trend_ok = self._htf_gate_and_bias(df_htf)
        
        if not (trend_ok and disp_ok):
            return None
        
        # LTF analizi
        o, h, l, c, v = df_ltf['o'], df_ltf['h'], df_ltf['l'], df_ltf['c'], df_ltf['v']
        common_data = self.get_common_data(df_ltf)
        
        close = common_data['close']
        prev_close = float(c.iloc[-2])
        atr_value = common_data['atr_value']
        
        # Donchian kanalları
        dc_high, dc_low = donchian(h, l, DONCHIAN_WIN)
        dc_high_prev = float(dc_high.shift(1).iloc[-1])
        dc_low_prev = float(dc_low.shift(1).iloc[-1])
        
        # Body strength
        bs = body_strength(o, c, h, l)
        
        # LONG setup
        if htf_bias == "LONG":
            long_break = (prev_close > dc_high_prev * (1 + BREAK_BUFFER) and 
                         close >= prev_close)
            
            if long_break:
                has_retest = self._retest_ok_long(dc_high_prev, df_ltf, atr_value)
                has_momentum = self._momentum_ok(df_ltf, "LONG")
                
                if has_retest or has_momentum:
                    sl, tps = compute_sl_tp_atr("LONG", close, atr_value)
                    
                    rr1 = (tps[0] - close) / max(1e-9, close - sl)
                    score = 40 + min(20, (adx1h - ADX_TREND_MIN) * 1.2) + (bs.iloc[-1] * 10)
                    
                    if rr1 < 1.0:
                        score -= 4
                    
                    confirmation = "Retest" if has_retest else "Momentum"
                    reason = f"Trend kırılımı + {confirmation} | 1H ADX={adx1h:.1f}"
                    
                    return self.create_signal_dict(
                        symbol, "LONG", close, sl, tps, score, reason
                    )
        
        # SHORT setup
        elif htf_bias == "SHORT":
            short_break = (prev_close < dc_low_prev * (1 - BREAK_BUFFER) and 
                          close <= prev_close)
            
            if short_break:
                has_retest = self._retest_ok_short(dc_low_prev, df_ltf, atr_value)
                has_momentum = self._momentum_ok(df_ltf, "SHORT")
                
                if has_retest or has_momentum:
                    sl, tps = compute_sl_tp_atr("SHORT", close, atr_value)
                    
                    rr1 = (close - tps[0]) / max(1e-9, sl - close)
                    score = 40 + min(20, (adx1h - ADX_TREND_MIN) * 1.2) + (bs.iloc[-1] * 10)
                    
                    if rr1 < 1.0:
                        score -= 4
                    
                    confirmation = "Retest" if has_retest else "Momentum"
                    reason = f"Trend kırılımı + {confirmation} | 1H ADX={adx1h:.1f}"
                    
                    return self.create_signal_dict(
                        symbol, "SHORT", close, sl, tps, score, reason
                    )
        
        return None
    
    def _htf_gate_and_bias(self, df1h: pd.DataFrame) -> tuple:
        """HTF kapı ve bias kontrolü"""
        c, h, l, o = df1h['c'], df1h['h'], df1h['l'], df1h['o']
        
        # EMA50 bias
        ema50 = ema(c, 50)
        bias = "NEUTRAL"
        
        if pd.notna(ema50.iloc[-1]) and pd.notna(ema50.iloc[-2]):
            if ema50.iloc[-1] > ema50.iloc[-2]:
                bias = "LONG"
            elif ema50.iloc[-1] < ema50.iloc[-2]:
                bias = "SHORT"
        
        # Displacement kontrolü
        disp_ok = False
        for i in range(1, ONEH_DISP_LOOKBACK + 1):
            range_val = float(h.iloc[-i] - l.iloc[-i])
            body = abs(float(c.iloc[-i] - o.iloc[-i]))
            
            if range_val > 0 and (body / range_val) >= ONEH_DISP_BODY_MIN:
                disp_ok = True
                break
        
        # ADX trend gücü
        adx1h = float(adx(h, l, c, 14).iloc[-1])
        trend_ok = adx1h >= ADX_TREND_MIN
        
        return bias, disp_ok, adx1h, trend_ok
    
    def _retest_ok_long(self, dc_break_level: float, df15: pd.DataFrame, atr_value: float) -> bool:
        """LONG retest kontrolü"""
        low = float(df15['l'].iloc[-1])
        close = float(df15['c'].iloc[-1])
        open_price = float(df15['o'].iloc[-1])
        high = float(df15['h'].iloc[-1])
        
        tolerance = RETEST_TOL_ATR * atr_value
        touched = (low <= dc_break_level + tolerance)
        
        range_val = high - df15['l'].iloc[-1]
        strong = (close > open_price and 
                 (close - open_price) / max(1e-12, range_val) > 0.55)
        
        return touched and strong
    
    def _retest_ok_short(self, dc_break_level: float, df15: pd.DataFrame, atr_value: float) -> bool:
        """SHORT retest kontrolü"""
        high = float(df15['h'].iloc[-1])
        close = float(df15['c'].iloc[-1])
        open_price = float(df15['o'].iloc[-1])
        low = float(df15['l'].iloc[-1])
        
        tolerance = RETEST_TOL_ATR * atr_value
        touched = (high >= dc_break_level - tolerance)
        
        range_val = df15['h'].iloc[-1] - low
        strong = (close < open_price and 
                 (open_price - close) / max(1e-12, range_val) > 0.55)
        
        return touched and strong
    
    def _momentum_ok(self, df15: pd.DataFrame, side: str) -> bool:
        """Momentum kontrolü"""
        c, o = df15['c'], df15['o']
        ema9 = ema(c, 9)
        ema21 = ema(c, 21)
        
        bs = body_strength(o, c, df15['h'], df15['l']).iloc[-1]
        
        if side == "LONG":
            return (ema9.iloc[-1] > ema21.iloc[-1] and 
                   float(c.iloc[-1]) >= float(c.iloc[-2]) and 
                   bs >= 0.60)
        else:
            return (ema9.iloc[-1] < ema21.iloc[-1] and 
                   float(c.iloc[-1]) <= float(c.iloc[-2]) and 
                   bs >= 0.60)
