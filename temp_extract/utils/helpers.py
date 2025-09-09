# ================== UTILITY FUNCTIONS ==================
"""
Yardımcı fonksiyonlar - veri işleme, formatlama, matematik
"""

import math
import sys
import datetime as dt
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any
from kucoin.client import Market

from ..config.settings import KNOWN_QUOTES, PRINT_PREFIX


def log(*args) -> None:
    """Log mesajı yazdır"""
    print(PRINT_PREFIX, *args)
    sys.stdout.flush()


def now_utc() -> dt.datetime:
    """Şu anki UTC zamanı"""
    return dt.datetime.now(dt.timezone.utc)


def fmt(x: float) -> str:
    """Sayıyı 6 haneli string olarak formatla"""
    return f"{x:.6f}"


def sigmoid(x: float) -> float:
    """Sigmoid fonksiyonu"""
    return 1 / (1 + math.exp(-x))


def to_df_klines(raw: List) -> Optional[pd.DataFrame]:
    """KuCoin raw kline verisini DataFrame'e çevir
    
    KuCoin format: [time, open, close, high, low, volume, turnover]
    """
    if not raw:
        return None
    
    df = pd.DataFrame(raw, columns=["time", "o", "c", "h", "l", "v", "turnover"])
    
    # Numeric conversion
    for col in ["time", "o", "c", "h", "l", "v", "turnover"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    
    df.dropna(inplace=True)
    
    # Timestamp conversion
    df["time"] = pd.to_datetime(df["time"].astype(np.int64), unit="ms", utc=True)
    df.sort_values("time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    return df


def get_ohlcv(client: Market, symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
    """OHLCV verisi al"""
    try:
        raw = client.get_kline(symbol, interval, limit=limit)
        return to_df_klines(raw)
    except Exception as e:
        msg = str(e)
        if "Unsupported trading pair" in msg or '"code":"400100"' in msg:
            log(f"❗ Desteklenmeyen parite: {symbol} (KuCoin formatı 'BASE-QUOTE' olmalı, örn. WIF-USDT)")
        else:
            log(f"{symbol} {interval} veri hatası:", e)
        return None


def normalize_symbol_to_kucoin(user_sym: str, symbols_set: set) -> Optional[str]:
    """Sembol adını KuCoin formatına normalize et
    
    Examples:
        WIFUSDT -> WIF-USDT
        wif-usdt -> WIF-USDT
        WIF/USDT -> WIF-USDT
    """
    if not user_sym:
        return None
    
    # Basic cleanup
    s = user_sym.strip().upper().replace(" ", "").replace("_", "-").replace("/", "-")
    
    # If already has dash, try it
    if "-" in s:
        candidate = s
    else:
        # Try to find quote currency
        candidate = None
        for quote in KNOWN_QUOTES:
            if s.endswith(quote):
                base = s[:-len(quote)]
                if base:
                    candidate = f"{base}-{quote}"
                    break
        if candidate is None:
            candidate = s
    
    # Check if exists
    if candidate in symbols_set:
        return candidate
    
    # Try alternatives
    alternatives = [candidate.replace("--", "-")]
    
    # Try with USDT if no dash and no known quote
    if "-" not in s:
        for quote in KNOWN_QUOTES:
            if s.endswith(quote):
                base = s[:-len(quote)]
                if base:
                    alternatives.append(f"{base}-{quote}")
    
    if "-" not in candidate and all(not candidate.endswith(q) for q in KNOWN_QUOTES):
        alternatives.append(f"{candidate}-USDT")
    
    for alt in alternatives:
        if alt in symbols_set:
            return alt
    
    return None


def chunked(sequence: List, n: int):
    """Liste parçalara böl"""
    for i in range(0, len(sequence), n):
        yield sequence[i:i+n]


def build_vol_pct_cache(symbols: List[str], volmap: Dict[str, float]) -> Dict[str, float]:
    """Hacim yüzdelik cache oluştur"""
    vals = [volmap.get(s, 0.0) for s in symbols]
    if not vals:
        return {}
    
    sorted_vals = sorted(vals)
    n = len(sorted_vals)
    cache = {}
    
    for s in symbols:
        v = volmap.get(s, 0.0)
        rank = sum(1 for x in sorted_vals if x <= v)
        cache[s] = rank / n
    
    return cache


def clip_value(value: float, min_val: float, max_val: float) -> float:
    """Değeri min-max arasında sınırla"""
    return max(min_val, min(max_val, value))


class SymbolManager:
    """Sembol yönetimi için yardımcı sınıf"""
    
    def __init__(self, client: Market):
        self.client = client
        self._symbols_set: Optional[set] = None
    
    def load_symbols_set(self) -> None:
        """Sembol listesini yükle"""
        try:
            symbols = self.client.get_symbol_list()
            self._symbols_set = set(s["symbol"].upper() for s in symbols)
        except Exception as e:
            log("Sembol listesi alınamadı:", e)
            self._symbols_set = set()
    
    def normalize_symbol(self, user_symbol: str) -> Optional[str]:
        """Sembolu normalize et"""
        if self._symbols_set is None:
            self.load_symbols_set()
        
        return normalize_symbol_to_kucoin(user_symbol, self._symbols_set)
    
    def get_usdt_pairs(self, min_volume: float = 0) -> List[str]:
        """USDT paritelerini al"""
        try:
            symbols = self.client.get_symbol_list()
            pairs = [s["symbol"] for s in symbols if s.get("quoteCurrency") == "USDT"]
            
            if min_volume > 0:
                tickers = self.client.get_all_tickers().get("ticker", [])
                volmap = {t.get("symbol"): float(t.get("volValue", 0.0)) for t in tickers}
                pairs = [s for s in pairs if volmap.get(s, 0.0) >= min_volume]
            
            return pairs
        except Exception as e:
            log("USDT pariteler alınamadı:", e)
            return []
