# ================== BASE STRATEGY CLASS ==================
"""
Temel strateji sınıfı - tüm stratejiler bu sınıftan türetilir
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import pandas as pd


class BaseStrategy(ABC):
    """Temel strateji sınıfı"""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
    
    @abstractmethod
    def analyze(self, df_ltf: pd.DataFrame, df_htf: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
        """Strateji analizi yap
        
        Args:
            df_ltf: Alt zaman dilimi verisi (15m)
            df_htf: Üst zaman dilimi verisi (1h)
            symbol: Sembol adı
            
        Returns:
            Sinyal dict'i veya None
        """
        pass
    
    @abstractmethod
    def get_regime(self) -> str:
        """Strateji rejimini döndür (TREND, RANGE, SMC, vb.)"""
        pass
    
    def validate_data(self, df_ltf: pd.DataFrame, df_htf: pd.DataFrame) -> bool:
        """Veri validasyonu"""
        if df_ltf is None or df_htf is None:
            return False
        
        if len(df_ltf) < 80 or len(df_htf) < 60:
            return False
            
        required_columns = ['o', 'h', 'l', 'c', 'v']
        
        for col in required_columns:
            if col not in df_ltf.columns or col not in df_htf.columns:
                return False
        
        return True
    
    def get_common_data(self, df_ltf: pd.DataFrame) -> Dict[str, Any]:
        """Ortak veri hesaplamaları"""
        from ..indicators.technical import atr_wilder
        from ..utils.risk_management import compute_sl_tp_atr
        
        o, h, l, c, v = df_ltf['o'], df_ltf['h'], df_ltf['l'], df_ltf['c'], df_ltf['v']
        
        close = float(c.iloc[-1])
        atr_value = float(atr_wilder(h, l, c, 14).iloc[-1])
        
        return {
            'close': close,
            'atr_value': atr_value,
            'ohlcv': (o, h, l, c, v)
        }
    
    def create_signal_dict(self, symbol: str, side: str, entry: float, 
                          sl: float, tps: tuple, score: float, reason: str) -> Dict[str, Any]:
        """Standard sinyal dict'i oluştur"""
        return {
            'symbol': symbol,
            'side': side,
            'entry': entry,
            'sl': sl,
            'tps': tps,
            'score': score,
            'p': 0.5,  # Başlangıç olasılığı, skorlama sisteminde güncellenecek
            'regime': self.get_regime(),
            'reason': reason
        }
