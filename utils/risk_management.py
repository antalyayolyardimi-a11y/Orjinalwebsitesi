# ================== RISK MANAGEMENT MODULE ==================
"""
Risk yönetimi - Stop Loss, Take Profit, ATR tabanlı hesaplamalar
"""

from typing import Tuple
from ..config.settings import ATR_STOP_MULT, TPS_R


def compute_sl_tp_atr(side: str, entry: float, atr_value: float) -> Tuple[float, Tuple[float, float, float]]:
    """ATR tabanlı SL ve TP hesapla
    
    Args:
        side: "LONG" veya "SHORT"
        entry: Giriş fiyatı
        atr_value: ATR değeri
    
    Returns:
        stop_loss, (tp1, tp2, tp3)
    """
    risk = ATR_STOP_MULT * atr_value
    
    if side == "LONG":
        sl = entry - risk
        tp1 = entry + TPS_R[0] * risk
        tp2 = entry + TPS_R[1] * risk
        tp3 = entry + TPS_R[2] * risk
    else:  # SHORT
        sl = entry + risk
        tp1 = entry - TPS_R[0] * risk
        tp2 = entry - TPS_R[1] * risk
        tp3 = entry - TPS_R[2] * risk
    
    return sl, (tp1, tp2, tp3)


def calculate_risk_reward(side: str, entry: float, tp: float, sl: float) -> float:
    """Risk-ödül oranını hesapla
    
    Args:
        side: "LONG" veya "SHORT"
        entry: Giriş fiyatı
        tp: Take profit fiyatı
        sl: Stop loss fiyatı
    
    Returns:
        Risk-ödül oranı (R)
    """
    if side == "LONG":
        profit = tp - entry
        risk = entry - sl
    else:  # SHORT
        profit = entry - tp
        risk = sl - entry
    
    return profit / max(1e-9, abs(risk))


def calculate_position_size(account_balance: float, risk_percentage: float, entry: float, sl: float) -> float:
    """Pozisyon büyüklüğü hesapla
    
    Args:
        account_balance: Hesap bakiyesi
        risk_percentage: Risk yüzdesi (0.01 = %1)
        entry: Giriş fiyatı
        sl: Stop loss fiyatı
    
    Returns:
        Pozisyon büyüklüğü (miktar)
    """
    risk_amount = account_balance * risk_percentage
    price_difference = abs(entry - sl)
    
    if price_difference == 0:
        return 0.0
    
    return risk_amount / price_difference


def validate_sl_tp_levels(side: str, entry: float, sl: float, tp1: float, tp2: float, tp3: float) -> bool:
    """SL ve TP seviyelerinin doğruluğunu kontrol et
    
    Args:
        side: "LONG" veya "SHORT"
        entry: Giriş fiyatı
        sl: Stop loss
        tp1, tp2, tp3: Take profit seviyeleri
    
    Returns:
        Seviyeler doğru mu?
    """
    if side == "LONG":
        # LONG için: SL < Entry < TP1 < TP2 < TP3
        return (sl < entry < tp1 < tp2 < tp3)
    else:
        # SHORT için: TP3 < TP2 < TP1 < Entry < SL
        return (tp3 < tp2 < tp1 < entry < sl)


def calculate_max_drawdown(price_history: list, entry_price: float, side: str) -> float:
    """Maksimum drawdown hesapla
    
    Args:
        price_history: Fiyat geçmişi listesi
        entry_price: Giriş fiyatı
        side: "LONG" veya "SHORT"
    
    Returns:
        Maksimum drawdown yüzdesi
    """
    if not price_history:
        return 0.0
    
    max_dd = 0.0
    
    for price in price_history:
        if side == "LONG":
            # LONG pozisyon için drawdown
            current_dd = (entry_price - price) / entry_price
        else:
            # SHORT pozisyon için drawdown  
            current_dd = (price - entry_price) / entry_price
        
        max_dd = max(max_dd, current_dd)
    
    return max_dd
