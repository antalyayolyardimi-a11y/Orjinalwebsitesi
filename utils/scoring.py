# ================== SCORING SYSTEM ==================
"""
Sinyal skorlama ve değerlendirme sistemi
"""

import math
from typing import Dict, Any, Optional
import pandas as pd

from ..config.settings import (
    SCORING_WEIGHTS, SCORING_BASE, PROB_CALIB_A, PROB_CALIB_B,
    ADX_TREND_MIN, BWIDTH_RANGE, FBB_ATR_MIN, FBB_ATR_MAX,
    PENALTY_DECAY
)
from ..indicators.technical import (
    adx, bollinger, atr_wilder
)
from ..ai.predictor import ai_predictor


class ScoringSystem:
    """Sinyal skorlama sistemi"""
    
    def __init__(self):
        self.recent_penalty = {}  # Symbol bazlı penalty tracking
    
    def extract_features(self, symbol: str, df_ltf: pd.DataFrame, df_htf: pd.DataFrame, 
                        candidate: Dict[str, Any], vol_pct: float = 0.5) -> Dict[str, float]:
        """Skorlama için özellikleri çıkar"""
        
        # LTF veriler
        c, h, l = df_ltf['c'], df_ltf['h'], df_ltf['l']
        close = float(c.iloc[-1])
        
        # ADX değeri
        adx_value = float(adx(h, l, c, 14).iloc[-1])
        
        # Entry, TP, SL
        entry = float(candidate['entry'])
        tp1 = float(candidate['tps'][0])
        sl = float(candidate['sl'])
        
        # Risk-ödül oranı
        if candidate['side'] == "LONG":
            rr1 = (tp1 - entry) / max(1e-9, entry - sl)
        else:
            rr1 = (entry - tp1) / max(1e-9, sl - entry)
        
        # Bollinger Bands genişliği
        _, _, _, bwidth, _ = bollinger(c, 20, 2.0)
        bw_last = float(bwidth.iloc[-1]) if pd.notna(bwidth.iloc[-1]) else float('nan')
        
        # HTF alignment
        htf_bias = self._get_htf_bias(df_htf)
        htf_align = (htf_bias == candidate['side'])
        
        # LTF momentum
        ltf_momentum = self._check_ltf_momentum(df_ltf, candidate['side'])
        
        # Retest veya FVG varlığı
        has_retest_or_fvg = (
            "Retest" in candidate.get('reason', '') or 
            candidate.get('regime') == 'SMC'
        )
        
        # ATR sweet spot
        atr_value = float(atr_wilder(h, l, c, 14).iloc[-1])
        atr_pct = atr_value / (close + 1e-12)
        
        # Features dictionary
        features = {
            'htf_align': 1.0 if htf_align else 0.0,
            'adx_norm': self._normalize_adx(adx_value),
            'ltf_momo': 1.0 if ltf_momentum else 0.0,
            'rr_norm': self._normalize_rr(rr1),
            'bw_adv': self._bandwidth_advantage(bw_last),
            'retest_or_fvg': 1.0 if has_retest_or_fvg else 0.0,
            'atr_sweet': self._atr_sweet_spot(atr_pct),
            'vol_pct': max(0.0, min(1.0, vol_pct)),
            'recent_penalty': self._get_recent_penalty(symbol)
        }
        
        return features
    
    def calculate_score(self, features: Dict[str, float]) -> float:
        """Özelliklerden skor hesapla"""
        score = SCORING_BASE
        
        for feature_name, weight in SCORING_WEIGHTS.items():
            feature_value = features.get(feature_name, 0.0)
            score += weight * float(feature_value)
        
        return max(0.0, score)
    
    def apply_hard_rules(self, score: float, features: Dict[str, float], 
                        candidate: Dict[str, Any]) -> float:
        """Sert kuralları uygula"""
        
        # HTF alignment yoksa büyük ceza
        if features.get('htf_align', 0.0) < 1.0:
            score -= 10.0
        
        # ADX çok düşükse eleriz
        if features.get('adx_norm', 0.0) < 0.10:
            score = 0.0
        
        # Range rejiminde bandwidth çok genişse ceza
        if (candidate.get('regime') == 'RANGE' and 
            features.get('bw_adv', 0.0) < 0.20):
            score -= 6.0
        
        # Erken tetikleyici bonusu
        if candidate.get('regime') == 'PREMO':
            early_bonus = candidate.get('_early_bonus', 0.0)
            score += float(early_bonus)
        
        return max(0.0, score)
    
    def score_to_probability(self, score: float) -> float:
        """Skoru olasılığa çevir"""
        return 1.0 / (1.0 + math.exp(-(PROB_CALIB_A * score + PROB_CALIB_B)))
    
    def evaluate_candidate(self, symbol: str, df_ltf: pd.DataFrame, df_htf: pd.DataFrame,
                          candidate: Dict[str, Any], vol_pct: float = 0.5) -> Dict[str, Any]:
        """Adayı tam değerlendir"""
        
        # Özellik çıkarımı
        features = self.extract_features(symbol, df_ltf, df_htf, candidate, vol_pct)
        
        # Skor hesaplama
        score = self.calculate_score(features)
        
        # Sert kurallar
        score = self.apply_hard_rules(score, features, candidate)
        
        # Olasılık
        traditional_prob = self.score_to_probability(score)
        
        # AI ile zenginleştir
        final_prob = ai_predictor.get_enhanced_probability(traditional_prob, features)
        
        # Candidate'ı güncelle
        candidate['score'] = score
        candidate['p'] = traditional_prob
        candidate['p_final'] = final_prob
        candidate['_features'] = features
        
        # Ek bilgiler
        candidate['_explain'] = {
            'rr1': (candidate['tps'][0] - candidate['entry']) / max(1e-9, candidate['entry'] - candidate['sl'])
                   if candidate['side'] == "LONG" else
                   (candidate['entry'] - candidate['tps'][0]) / max(1e-9, candidate['sl'] - candidate['entry']),
            'adx': float(adx(df_ltf['h'], df_ltf['l'], df_ltf['c'], 14).iloc[-1]),
            'bw': features.get('bw_adv', 0.0),
            'atr_pct': float(atr_wilder(df_ltf['h'], df_ltf['l'], df_ltf['c'], 14).iloc[-1]) / 
                      (float(df_ltf['c'].iloc[-1]) + 1e-12),
            'b1h': self._get_htf_bias(df_htf)
        }
        
        return candidate
    
    def mark_outcome(self, symbol: str, result: str) -> None:
        """Sinyal sonucunu işaretle"""
        if result == "SL":
            self.recent_penalty[symbol] = PENALTY_DECAY
    
    def _get_htf_bias(self, df_htf: pd.DataFrame) -> str:
        """HTF bias belirle"""
        from ..indicators.technical import ema
        
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
    
    def _check_ltf_momentum(self, df_ltf: pd.DataFrame, side: str) -> bool:
        """LTF momentum kontrol"""
        from ..indicators.technical import ema, body_strength
        
        c, o = df_ltf['c'], df_ltf['o']
        ema9 = ema(c, 9)
        ema21 = ema(c, 21)
        
        bs = body_strength(o, c, df_ltf['h'], df_ltf['l']).iloc[-1]
        
        if side == "LONG":
            return (ema9.iloc[-1] > ema21.iloc[-1] and 
                   float(c.iloc[-1]) >= float(c.iloc[-2]) and 
                   bs >= 0.60)
        else:
            return (ema9.iloc[-1] < ema21.iloc[-1] and 
                   float(c.iloc[-1]) <= float(c.iloc[-2]) and 
                   bs >= 0.60)
    
    def _normalize_adx(self, adx_value: float) -> float:
        """ADX normalleştir"""
        return max(0.0, min(1.0, (adx_value - ADX_TREND_MIN) / 20.0))
    
    def _normalize_rr(self, rr_value: float) -> float:
        """Risk-ödül oranını normalleştir"""
        return max(0.0, min(1.0, (rr_value - 0.8) / 1.6))
    
    def _bandwidth_advantage(self, bandwidth: float) -> float:
        """Bandwidth avantajı"""
        if math.isnan(bandwidth):
            return 0.0
        return max(0.0, 1.0 - (bandwidth / max(1e-6, BWIDTH_RANGE)))
    
    def _atr_sweet_spot(self, atr_pct: float) -> float:
        """ATR sweet spot kontrolü"""
        return 1.0 if FBB_ATR_MIN <= atr_pct <= FBB_ATR_MAX else 0.0
    
    def _get_recent_penalty(self, symbol: str) -> float:
        """Son penalty durumu"""
        penalty = self.recent_penalty.get(symbol, 0)
        if penalty > 0:
            self.recent_penalty[symbol] = penalty - 1
            return 1.0
        return 0.0


# Global scoring system instance
scoring_system = ScoringSystem()
