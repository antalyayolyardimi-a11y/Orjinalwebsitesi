# ================== SMC STRATEGY ==================
"""
Smart Money Concept (SMC) stratejisi - Likidite süpürme, CHOCH, FVG
"""

import math
from typing import Optional, Dict, Any, List, Tuple
import pandas as pd
import numpy as np

from .base import BaseStrategy
from ..indicators.technical import find_swings, find_fvgs, ema
from ..utils.risk_management import compute_sl_tp_atr
from ..utils.helpers import sigmoid
from ..config.settings import (
    SWING_LEFT, SWING_RIGHT, SWEEP_EPS, BOS_EPS, FVG_LOOKBACK,
    OTE_LOW, OTE_HIGH, SMC_REQUIRE_FVG, ATR_PERIOD
)


class SMCStrategy(BaseStrategy):
    """Smart Money Concept stratejisi"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("SMC", config)
    
    def get_regime(self) -> str:
        return "SMC"
    
    def analyze(self, df_ltf: pd.DataFrame, df_htf: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
        """SMC analizi yap"""
        if not self.validate_data(df_ltf, df_htf):
            return None
        
        # HTF bias kontrolü
        htf_bias = self._get_htf_bias(df_htf)
        if htf_bias == "NEUTRAL":
            return None
        
        # Swing analizi
        o, h, l, c, v = df_ltf['o'], df_ltf['h'], df_ltf['l'], df_ltf['c'], df_ltf['v']
        swing_highs, swing_lows = find_swings(h, l, SWING_LEFT, SWING_RIGHT)
        
        if len(swing_highs) < 2 and len(swing_lows) < 2:
            return None
        
        last_close = float(c.iloc[-1])
        common_data = self.get_common_data(df_ltf)
        atr_value = common_data['atr_value']
        
        # LONG setup kontrolü
        if len(swing_lows) >= 2 and htf_bias == "LONG":
            long_signal = self._check_long_smc(
                h, l, c, swing_highs, swing_lows, last_close, atr_value, symbol
            )
            if long_signal:
                return long_signal
        
        # SHORT setup kontrolü
        if len(swing_highs) >= 2 and htf_bias == "SHORT":
            short_signal = self._check_short_smc(
                h, l, c, swing_highs, swing_lows, last_close, atr_value, symbol
            )
            if short_signal:
                return short_signal
        
        return None
    
    def _get_htf_bias(self, df_htf: pd.DataFrame) -> str:
        """HTF bias belirle"""
        c = df_htf['c']
        ema50 = ema(c, 50)
        
        if pd.isna(ema50.iloc[-1]) or pd.isna(ema50.iloc[-2]):
            return "NEUTRAL"
        
        if ema50.iloc[-1] > ema50.iloc[-2]:
            return "LONG"
        elif ema50.iloc[-1] < ema50.iloc[-2]:
            return "SHORT"
        else:
            return "NEUTRAL"
    
    def _check_long_smc(self, h: pd.Series, l: pd.Series, c: pd.Series,
                       swing_highs: List[int], swing_lows: List[int],
                       last_close: float, atr_value: float, symbol: str) -> Optional[Dict[str, Any]]:
        """LONG SMC setup kontrolü"""
        
        # Likidite süpürme kontrolü
        ref_low = l.iloc[swing_lows[-2]]
        swept_low = (
            l.iloc[swing_lows[-1]] < ref_low * (1 - SWEEP_EPS) and
            c.iloc[swing_lows[-1]] > ref_low * (1 - SWEEP_EPS)
        )
        
        if not swept_low:
            return None
        
        # CHOCH kontrolü (Change of Character)
        minor_swing_high = None
        for idx in reversed(swing_highs):
            if idx >= swing_lows[-1]:
                minor_swing_high = idx
                break
        
        if minor_swing_high is None and swing_highs:
            minor_swing_high = swing_highs[-1]
        
        if minor_swing_high is None:
            return None
        
        choch_up = last_close > h.iloc[minor_swing_high] * (1 + BOS_EPS)
        
        if not choch_up:
            return None
        
        # FVG kontrolü (isteğe bağlı)
        bull_fvg, _ = find_fvgs(h, l, FVG_LOOKBACK)
        
        if SMC_REQUIRE_FVG and not bull_fvg:
            return None
        
        # Entry seviyesi hesaplama
        leg_low = l.iloc[swing_lows[-1]]
        leg_high = max(last_close, h.iloc[minor_swing_high])
        leg = abs(leg_high - leg_low)
        
        # Minimum leg büyüklüğü kontrolü
        if leg / (last_close + 1e-12) < 0.004:
            return None
        
        # OTE (Optimal Trade Entry) veya FVG seviyesi
        if bull_fvg:
            entry_a, entry_b = bull_fvg[0], bull_fvg[1]
        else:
            ote_a = leg_low + (leg_high - leg_low) * OTE_LOW
            ote_b = leg_low + (leg_high - leg_low) * OTE_HIGH
            entry_a, entry_b = ote_a, ote_b
        
        entry_mid = (entry_a + entry_b) / 2
        
        # SL/TP hesaplama
        sl, tps = compute_sl_tp_atr("LONG", entry_mid, atr_value)
        
        # Skor hesaplama
        rr1 = (tps[0] - entry_mid) / max(1e-9, entry_mid - sl)
        score = 45 + min(15, rr1 * 10)
        
        reason = "SMC: likidite süpürme → CHOCH (+FVG/OTE)"
        
        return self.create_signal_dict(
            symbol, "LONG", entry_mid, sl, tps, score, reason
        )
    
    def _check_short_smc(self, h: pd.Series, l: pd.Series, c: pd.Series,
                        swing_highs: List[int], swing_lows: List[int],
                        last_close: float, atr_value: float, symbol: str) -> Optional[Dict[str, Any]]:
        """SHORT SMC setup kontrolü"""
        
        # Likidite süpürme kontrolü
        ref_high = h.iloc[swing_highs[-2]]
        swept_high = (
            h.iloc[swing_highs[-1]] > ref_high * (1 + SWEEP_EPS) and
            c.iloc[swing_highs[-1]] < ref_high * (1 + SWEEP_EPS)
        )
        
        if not swept_high:
            return None
        
        # CHOCH kontrolü (Change of Character)
        minor_swing_low = None
        for idx in reversed(swing_lows):
            if idx >= swing_highs[-1]:
                minor_swing_low = idx
                break
        
        if minor_swing_low is None and swing_lows:
            minor_swing_low = swing_lows[-1]
        
        if minor_swing_low is None:
            return None
        
        choch_down = last_close < l.iloc[minor_swing_low] * (1 - BOS_EPS)
        
        if not choch_down:
            return None
        
        # FVG kontrolü (isteğe bağlı)
        _, bear_fvg = find_fvgs(h, l, FVG_LOOKBACK)
        
        if SMC_REQUIRE_FVG and not bear_fvg:
            return None
        
        # Entry seviyesi hesaplama
        leg_high = h.iloc[swing_highs[-1]]
        leg_low = min(last_close, l.iloc[minor_swing_low])
        leg = abs(leg_high - leg_low)
        
        # Minimum leg büyüklüğü kontrolü
        if leg / (last_close + 1e-12) < 0.004:
            return None
        
        # OTE (Optimal Trade Entry) veya FVG seviyesi
        if bear_fvg:
            entry_a, entry_b = bear_fvg[0], bear_fvg[1]
        else:
            ote_a = leg_high - (leg_high - leg_low) * OTE_LOW
            ote_b = leg_high - (leg_high - leg_low) * OTE_HIGH
            entry_a, entry_b = ote_a, ote_b
        
        entry_mid = (entry_a + entry_b) / 2
        
        # SL/TP hesaplama
        sl, tps = compute_sl_tp_atr("SHORT", entry_mid, atr_value)
        
        # Skor hesaplama
        rr1 = (entry_mid - tps[0]) / max(1e-9, sl - entry_mid)
        score = 45 + min(15, rr1 * 10)
        
        reason = "SMC: likidite süpürme → CHOCH (+FVG/OTE)"
        
        return self.create_signal_dict(
            symbol, "SHORT", entry_mid, sl, tps, score, reason
        )
