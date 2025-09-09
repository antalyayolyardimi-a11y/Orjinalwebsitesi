# ================== MOMENTUM STRATEGY ==================
"""
Momentum stratejisi - Erken breakout, pre-break sinyalleri
"""

import math
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np

from .base import BaseStrategy
from ..indicators.technical import (
    donchian, ema, atr_wilder, adx, body_strength
)
from ..utils.risk_management import compute_sl_tp_atr
from ..utils.helpers import sigmoid
from ..config.settings import (
    EARLY_TRIGGERS_ON, PREBREAK_ATR_X, EARLY_MOMO_BODY_MIN,
    EARLY_REL_VOL, EARLY_ADX_BONUS, DONCHIAN_WIN, BREAK_BUFFER,
    MOMO_CONFIRM_MODE, MOMO_BODY_MIN, MOMO_REL_VOL, MOMO_NET_BODY_TH,
    ATR_PERIOD, ADX_TREND_MIN
)


class MomentumStrategy(BaseStrategy):
    """Momentum stratejisi"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("MOMENTUM", config)
    
    def get_regime(self) -> str:
        return "MO"
    
    def analyze(self, df_ltf: pd.DataFrame, df_htf: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
        """Momentum analizi yap"""
        if not self.validate_data(df_ltf, df_htf):
            return None
        
        if len(df_ltf) < 50 or len(df_htf) < 50:
            return None
        
        # HTF bias
        htf_bias = self._get_htf_bias(df_htf)
        
        # LTF veriler
        o, h, l, c, v = df_ltf['o'], df_ltf['h'], df_ltf['l'], df_ltf['c'], df_ltf['v']
        common_data = self.get_common_data(df_ltf)
        
        close = common_data['close']
        atr_value = common_data['atr_value']
        
        # ATR koruması
        atr_pct = atr_value / (close + 1e-12)
        if atr_pct > 0.05:  # Aşırı volatilite
            return None
        
        # EMA21'den aşırı uzaklık kontrolü
        ema21 = ema(c, 21)
        if abs(close - float(ema21.iloc[-1])) > 1.8 * atr_value:
            return None
        
        # Donchian/EMA kapıları
        dc_high, dc_low = donchian(h, l, DONCHIAN_WIN)
        
        long_gate = (close > float(dc_high.shift(1).iloc[-1]) * (1 + BREAK_BUFFER) and
                    close > float(ema21.iloc[-1]))
        
        short_gate = (close < float(dc_low.shift(1).iloc[-1]) * (1 - BREAK_BUFFER) and
                     close < float(ema21.iloc[-1]))
        
        # Normal momentum breakout
        if long_gate and htf_bias != "SHORT" and self._confirm_momentum(df_ltf, "LONG"):
            sl, tps = compute_sl_tp_atr("LONG", close, atr_value)
            reason = f"Momentum onay ({MOMO_CONFIRM_MODE}) + DC/EMA breakout"
            return self.create_signal_dict(symbol, "LONG", close, sl, tps, 50, reason)
        
        if short_gate and htf_bias != "LONG" and self._confirm_momentum(df_ltf, "SHORT"):
            sl, tps = compute_sl_tp_atr("SHORT", close, atr_value)
            reason = f"Momentum onay ({MOMO_CONFIRM_MODE}) + DC/EMA breakdown"
            return self.create_signal_dict(symbol, "SHORT", close, sl, tps, 50, reason)
        
        # Erken tetikleyiciler
        if EARLY_TRIGGERS_ON:
            early_signal = self._check_early_triggers(
                df_ltf, df_htf, close, atr_value, htf_bias, symbol
            )
            if early_signal:
                return early_signal
        
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
    
    def _confirm_momentum(self, df15: pd.DataFrame, side: str, early: bool = False) -> bool:
        """Momentum onayı - esnek kurallar"""
        o, c, h, l, v = df15['o'], df15['c'], df15['h'], df15['l'], df15['v']
        
        # Parametreler (erken modda gevşetilmiş)
        body_min = EARLY_MOMO_BODY_MIN if early else MOMO_BODY_MIN
        rel_vol_th = EARLY_REL_VOL if early else MOMO_REL_VOL
        
        # Son 3 mumun body/range oranları
        body_ratios = []
        directions = []
        
        for i in [-1, -2, -3]:
            range_val = float(h.iloc[i] - l.iloc[i])
            if range_val <= 0:
                continue
            
            body_ratio = abs(float(c.iloc[i] - o.iloc[i])) / range_val
            body_ratios.append(body_ratio)
            
            if c.iloc[i] > o.iloc[i]:
                directions.append(1)  # Yeşil
            elif c.iloc[i] < o.iloc[i]:
                directions.append(-1)  # Kırmızı
            else:
                directions.append(0)  # Doji
        
        if len(body_ratios) < 3:
            return False
        
        # Güçlü mumlar
        up_count = sum(1 for d, b in zip(directions, body_ratios) 
                      if d == 1 and b >= body_min)
        down_count = sum(1 for d, b in zip(directions, body_ratios) 
                        if d == -1 and b >= body_min)
        
        # Net body gücü
        net_body = sum(d * b for d, b in zip(directions, body_ratios))
        
        # Relatif hacim
        rel_vol = float(v.iloc[-1]) > float(v.rolling(20).mean().iloc[-1]) * rel_vol_th
        
        # EMA21 üzerinde/altında
        ema21 = ema(c, 21)
        above_ema21 = float(c.iloc[-1]) > float(ema21.iloc[-1])
        
        # Mod kontrolü
        mode = MOMO_CONFIRM_MODE.lower()
        
        if mode == "off":
            return True
        
        if mode == "strict3":
            all_green = all(c.iloc[i] > o.iloc[i] for i in [-1, -2, -3])
            all_red = all(c.iloc[i] < o.iloc[i] for i in [-1, -2, -3])
            strong_enough = (body_ratios[0] >= body_min and body_ratios[1] >= body_min)
            
            if side == "LONG":
                return all_green and strong_enough
            else:
                return all_red and strong_enough
        
        if mode == "2of3":
            return (up_count >= 2) if side == "LONG" else (down_count >= 2)
        
        if mode == "net_body":
            threshold = MOMO_NET_BODY_TH * (0.85 if early else 1.0)
            return (net_body >= threshold) if side == "LONG" else (net_body <= -threshold)
        
        if mode == "ema_rv":
            return (above_ema21 and rel_vol) if side == "LONG" else ((not above_ema21) and rel_vol)
        
        if mode == "hybrid":
            condition1 = (up_count >= 2) if side == "LONG" else (down_count >= 2)
            condition2 = (above_ema21 and rel_vol) if side == "LONG" else ((not above_ema21) and rel_vol)
            return condition1 or condition2
        
        return True  # Default
    
    def _check_early_triggers(self, df_ltf: pd.DataFrame, df_htf: pd.DataFrame, 
                             close: float, atr_value: float, htf_bias: str, 
                             symbol: str) -> Optional[Dict[str, Any]]:
        """Erken tetikleyici kontrolü (pre-break)"""
        h, l, c = df_ltf['h'], df_ltf['l'], df_ltf['c']
        
        # Donchian seviyeleri
        dc_high, dc_low = donchian(h, l, DONCHIAN_WIN)
        dc_high_prev = float(dc_high.shift(1).iloc[-1])
        dc_low_prev = float(dc_low.shift(1).iloc[-1])
        
        # EMA21
        ema21 = ema(c, 21)
        
        # Yakınlık kontrolü
        near_upper = (dc_high_prev - close) <= (PREBREAK_ATR_X * atr_value)
        near_lower = (close - dc_low_prev) <= (PREBREAK_ATR_X * atr_value)
        
        # LONG erken tetik
        if (near_upper and htf_bias != "SHORT" and 
            close > float(ema21.iloc[-1]) and
            self._confirm_momentum(df_ltf, "LONG", early=True)):
            
            sl, tps = compute_sl_tp_atr("LONG", close, atr_value)
            
            # ADX bonusu
            adx1h = float(adx(df_htf['h'], df_htf['l'], df_htf['c'], 14).iloc[-1])
            early_bonus = EARLY_ADX_BONUS if adx1h >= ADX_TREND_MIN else 0.0
            
            reason = f"Erken: DC üstüne yakın (≤{PREBREAK_ATR_X:.2f}×ATR), MOMO onay (erken)"
            
            signal = self.create_signal_dict(symbol, "LONG", close, sl, tps, 45, reason)
            signal["regime"] = "PREMO"
            signal["_early_bonus"] = early_bonus
            return signal
        
        # SHORT erken tetik
        if (near_lower and htf_bias != "LONG" and 
            close < float(ema21.iloc[-1]) and
            self._confirm_momentum(df_ltf, "SHORT", early=True)):
            
            sl, tps = compute_sl_tp_atr("SHORT", close, atr_value)
            
            # ADX bonusu
            adx1h = float(adx(df_htf['h'], df_htf['l'], df_htf['c'], 14).iloc[-1])
            early_bonus = EARLY_ADX_BONUS if adx1h >= ADX_TREND_MIN else 0.0
            
            reason = f"Erken: DC altına yakın (≤{PREBREAK_ATR_X:.2f}×ATR), MOMO onay (erken)"
            
            signal = self.create_signal_dict(symbol, "SHORT", close, sl, tps, 45, reason)
            signal["regime"] = "PREMO"
            signal["_early_bonus"] = early_bonus
            return signal
        
        return None
