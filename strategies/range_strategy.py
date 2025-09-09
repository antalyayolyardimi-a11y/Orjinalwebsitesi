# ================== RANGE STRATEGY ==================
"""
Range trading stratejisi - Bollinger Bands, RSI, mean reversion
"""

import math
from typing import Optional, Dict, Any
import pandas as pd

from .base import BaseStrategy
from ..indicators.technical import (
    rsi, bollinger, body_strength, ema, atr_wilder
)
from ..utils.risk_management import compute_sl_tp_atr
from ..utils.helpers import sigmoid
from ..config.settings import (
    BB_PERIOD, BB_K, BWIDTH_RANGE, RSI_LONG_TH, RSI_SHORT_TH,
    VOL_MULT_REQ_GLOBAL, ATR_PERIOD
)


class RangeStrategy(BaseStrategy):
    """Range trading stratejisi"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("RANGE", config)
    
    def get_regime(self) -> str:
        return "RANGE"
    
    def analyze(self, df_ltf: pd.DataFrame, df_htf: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
        """Range analizi yap"""
        if not self.validate_data(df_ltf, df_htf):
            return None
        
        # HTF bias
        htf_bias = self._get_htf_bias(df_htf)
        
        # ADX trend kontrolü - range için düşük ADX istiyoruz
        adx1h = self._get_adx_1h(df_htf)
        trend_ok = adx1h >= 18  # config'ten alınabilir
        
        # Trend günlerinde range stratejisi çalışmaz
        if trend_ok:
            return None
        
        # LTF analizi
        o, h, l, c, v = df_ltf['o'], df_ltf['h'], df_ltf['l'], df_ltf['c'], df_ltf['v']
        common_data = self.get_common_data(df_ltf)
        
        close = common_data['close']
        atr_value = common_data['atr_value']
        
        # Bollinger Bands
        ma, bb_upper, bb_lower, bandwidth, _ = bollinger(c, BB_PERIOD, BB_K)
        bw = float(bandwidth.iloc[-1])
        
        # Range koşulu - dar bant
        if math.isnan(bw) or bw > BWIDTH_RANGE:
            return None
        
        # RSI
        rsi14 = float(rsi(c, 14).iloc[-1])
        
        # Bollinger band seviyeleri
        bb_upper_val = float(bb_upper.iloc[-1])
        bb_lower_val = float(bb_lower.iloc[-1])
        
        # Alt banda yakın LONG setup
        near_lower = close <= bb_lower_val * (1 + 0.0010)
        if near_lower and rsi14 < RSI_LONG_TH and htf_bias != "SHORT":
            long_signal = self._check_long_range(
                df_ltf, close, bb_lower_val, rsi14, bw, atr_value, symbol
            )
            if long_signal:
                return long_signal
        
        # Üst banda yakın SHORT setup
        near_upper = close >= bb_upper_val * (1 - 0.0010)
        if near_upper and rsi14 > RSI_SHORT_TH and htf_bias != "LONG":
            short_signal = self._check_short_range(
                df_ltf, close, bb_upper_val, rsi14, bw, atr_value, symbol
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
    
    def _get_adx_1h(self, df_htf: pd.DataFrame) -> float:
        """1H ADX değeri"""
        from ..indicators.technical import adx
        h, l, c = df_htf['h'], df_htf['l'], df_htf['c']
        return float(adx(h, l, c, 14).iloc[-1])
    
    def _check_long_range(self, df_ltf: pd.DataFrame, close: float, bb_lower: float,
                         rsi14: float, bw: float, atr_value: float, symbol: str) -> Optional[Dict[str, Any]]:
        """LONG range setup kontrolü"""
        c, o, h, l, v = df_ltf['c'], df_ltf['o'], df_ltf['h'], df_ltf['l'], df_ltf['v']
        
        # False breakout ve re-enter kontrolü
        re_enter_long = (float(c.iloc[-2]) < bb_lower and float(c.iloc[-1]) > bb_lower)
        
        if not re_enter_long:
            return None
        
        # Body strength kontrolü
        bs_last = float(body_strength(o, c, h, l).iloc[-1])
        if bs_last < 0.62:  # Güçlü mum gerekli
            return None
        
        # Hacim kontrolü
        vol_ok = float(v.iloc[-1]) > float(v.rolling(20).mean().iloc[-1]) * VOL_MULT_REQ_GLOBAL
        if not vol_ok:
            return None
        
        # SL/TP hesaplama
        sl, tps = compute_sl_tp_atr("LONG", close, atr_value)
        
        # Skor hesaplama
        score = (30 + 
                max(0, 38 - rsi14) +  # RSI oversold bonusu
                (1 - bw / max(1e-12, BWIDTH_RANGE)) * 10)  # Dar bant bonusu
        
        reason = f"Bant içi bounce (false breakout→re-enter + güçlü mum + hacim) | RSI={rsi14:.1f}, BW={bw:.4f}"
        
        return self.create_signal_dict(
            symbol, "LONG", close, sl, tps, score, reason
        )
    
    def _check_short_range(self, df_ltf: pd.DataFrame, close: float, bb_upper: float,
                          rsi14: float, bw: float, atr_value: float, symbol: str) -> Optional[Dict[str, Any]]:
        """SHORT range setup kontrolü"""
        c, o, h, l, v = df_ltf['c'], df_ltf['o'], df_ltf['h'], df_ltf['l'], df_ltf['v']
        
        # False breakout ve re-enter kontrolü
        re_enter_short = (float(c.iloc[-2]) > bb_upper and float(c.iloc[-1]) < bb_upper)
        
        if not re_enter_short:
            return None
        
        # Body strength kontrolü
        bs_last = float(body_strength(o, c, h, l).iloc[-1])
        if bs_last < 0.62:  # Güçlü mum gerekli
            return None
        
        # Hacim kontrolü
        vol_ok = float(v.iloc[-1]) > float(v.rolling(20).mean().iloc[-1]) * VOL_MULT_REQ_GLOBAL
        if not vol_ok:
            return None
        
        # SL/TP hesaplama
        sl, tps = compute_sl_tp_atr("SHORT", close, atr_value)
        
        # Skor hesaplama
        score = (30 + 
                max(0, rsi14 - 62) +  # RSI overbought bonusu
                (1 - bw / max(1e-12, BWIDTH_RANGE)) * 10)  # Dar bant bonusu
        
        reason = f"Bant içi bounce (false breakout→re-enter + güçlü mum + hacim) | RSI={rsi14:.1f}, BW={bw:.4f}"
        
        return self.create_signal_dict(
            symbol, "SHORT", close, sl, tps, score, reason
        )
