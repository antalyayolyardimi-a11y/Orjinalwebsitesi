# ================== TELEGRAM BOT ==================
"""
Telegram bot - komutlar ve mesaj gönderme
"""

import asyncio
import math
import pandas as pd
from typing import Optional, Dict, Any
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from ..config.settings import TELEGRAM_TOKEN, MODE_CONFIGS
from ..utils.helpers import log, fmt, SymbolManager, get_ohlcv
from ..ai.predictor import ai_predictor
from ..utils.scoring import scoring_system


class TradingTelegramBot:
    """Trading Telegram Bot sınıfı"""
    
    def __init__(self, kucoin_client):
        self.bot = Bot(token=TELEGRAM_TOKEN)
        self.dp = Dispatcher()
        self.client = kucoin_client
        self.symbol_manager = SymbolManager(kucoin_client)
        
        # Bot state
        self.cached_chat_id: Optional[int] = None
        self.current_mode = "balanced"
        self.signal_counter = 0
        self.signals_store = {}
        
        # Register handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Komut handler'larını kaydet"""
        
        @self.dp.message(Command("start"))
        async def start_handler(message: Message):
            await self._handle_start(message)
        
        @self.dp.message(Command("mode"))
        async def mode_handler(message: Message):
            await self._handle_mode(message)
        
        @self.dp.message(Command("analiz"))
        async def analysis_handler(message: Message):
            await self._handle_analysis(message)
        
        @self.dp.message(Command("aistats"))
        async def ai_stats_handler(message: Message):
            await self._handle_ai_stats(message)
        
        @self.dp.message(Command("aireset"))
        async def ai_reset_handler(message: Message):
            await self._handle_ai_reset(message)
    
    async def _handle_start(self, message: Message):
        """Start komutu"""
        self.cached_chat_id = message.chat.id
        
        text = (
            "✅ Bot hazır!\n"
            f"Mode: *{self.current_mode}*\n"
            "• 5 dakikada bir tarar, sinyaller 15m grafiğe göre üretilir.\n"
            "• Komutlar: /mode | /analiz <Sembol> | /aistats | /aireset"
        )
        
        await message.answer(text, parse_mode="Markdown")
    
    async def _handle_mode(self, message: Message):
        """Mode değiştirme komutu"""
        parts = message.text.strip().split()
        
        if len(parts) < 2:
            await message.answer("Kullanım: /mode aggressive | balanced | conservative")
            return
        
        target_mode = parts[1].lower()
        
        if target_mode not in MODE_CONFIGS:
            await message.answer("Geçersiz mod. Seçenekler: aggressive | balanced | conservative")
            return
        
        # Mode'u güncelle (bu ana bot'ta yapılacak)
        self.current_mode = target_mode
        
        # Config bilgilerini göster
        config = MODE_CONFIGS[target_mode]
        
        text = (
            f"⚙️ Mode: *{target_mode}*\n"
            f"MinScore={config['BASE_MIN_SCORE']}, "
            f"ADXmin={config['ADX_TREND_MIN']}, "
            f"BWmax={config['BWIDTH_RANGE']}, "
            f"VolMin≈{config['MIN_VOLVALUE_USDT']}, "
            f"ATR_STOP_MULT={config['ATR_STOP_MULT']}"
        )
        
        await message.answer(text, parse_mode="Markdown")
    
    async def _handle_analysis(self, message: Message):
        """Analiz komutu"""
        parts = message.text.strip().split()
        
        if len(parts) < 2:
            await message.answer("Kullanım: /analiz WIFUSDT veya /analiz WIF-USDT")
            return
        
        raw_symbol = parts[1].upper()
        normalized_symbol = self.symbol_manager.normalize_symbol(raw_symbol)
        
        if not normalized_symbol:
            await message.answer(f"❗ '{raw_symbol}' KuCoin'de bulunamadı. Örn: WIFUSDT → WIF-USDT")
            return
        
        await message.answer(f"⏳ Analiz ediliyor: {normalized_symbol}")
        
        try:
            analysis_text = self._analyze_symbol(normalized_symbol)
            await message.answer(analysis_text, parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"Analiz hatası ({normalized_symbol}): {e}")
    
    async def _handle_ai_stats(self, message: Message):
        """AI istatistikleri"""
        stats = ai_predictor.get_stats()
        
        if not stats.get('enabled', False):
            await message.answer("AI kapalı.")
            return
        
        lines = [f"AI seen: #{stats['samples_seen']} | bias={stats['bias']:.3f}"]
        
        for key in sorted(stats['weights'].keys()):
            weight = stats['weights'][key]
            lines.append(f"{key:14s}: {weight:6.3f}")
        
        text = "```\n" + "\n".join(lines) + "\n```"
        await message.answer(text, parse_mode="Markdown")
    
    async def _handle_ai_reset(self, message: Message):
        """AI sıfırla"""
        ai_predictor.reset()
        await message.answer("AI ağırlıkları sıfırlandı.")
    
    async def send_signal(self, signal: Dict[str, Any]) -> bool:
        """Sinyal gönder"""
        if self.cached_chat_id is None:
            log("Chat yok → /start bekleniyor.")
            return False
        
        signal_id = str(self.signal_counter)
        self.signal_counter += 1
        
        # Sinyal store'a kaydet
        self.signals_store[signal_id] = {
            'signal': signal,
            'timestamp': asyncio.get_event_loop().time()
        }
        
        # Mesaj formatla
        text = self._format_signal_message(signal)
        
        try:
            await self.bot.send_message(
                chat_id=self.cached_chat_id, 
                text=text, 
                parse_mode="Markdown"
            )
            return True
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            log("Telegram hatası:", e)
            return False
    
    def _format_signal_message(self, signal: Dict[str, Any]) -> str:
        """Sinyal mesajını formatla"""
        symbol = signal['symbol']
        side = signal['side']
        regime = signal.get('regime', '-')
        entry = signal['entry']
        sl = signal['sl']
        tps = signal['tps']
        
        # Risk-ödül hesapla
        if side == "LONG":
            rr1 = (tps[0] - entry) / max(1e-9, entry - sl)
        else:
            rr1 = (entry - tps[0]) / max(1e-9, sl - entry)
        
        # HTF bias
        explain = signal.get('_explain', {})
        htf_bias = explain.get('b1h', '-')
        
        # Reason
        reason = self._get_human_reason(signal)
        
        title = f"🔔 {symbol} • {side} • {regime} • Mode: {self.current_mode}"
        
        levels = (
            f"• Entry : `{fmt(entry)}`\n"
            f"• SL    : `{fmt(sl)}`\n"
            f"• TP1   : `{fmt(tps[0])}`\n"
            f"• TP2   : `{fmt(tps[1])}`\n"
            f"• TP3   : `{fmt(tps[2])}`"
        )
        
        quick = (
            f"• 1H Bias: *{htf_bias}*\n"
            f"• Neden: {reason}\n"
            f"• R (TP1'e): *{rr1:.2f}*"
        )
        
        notes = (
            "- *SL (Stop Loss)*: Zarar durdur.\n"
            "- *TP (Take Profit)*: Kar al seviyeleri.\n"
            "- *R*: ATR_STOP_MULT × ATR; *1.0R* = SL mesafesi."
        )
        
        return (
            f"*{title}*\n\n"
            f"*Özet*\n{quick}\n\n"
            f"*Seviyeler*\n{levels}\n\n"
            f"*Notlar*\n{notes}"
        )
    
    def _get_human_reason(self, signal: Dict[str, Any]) -> str:
        """İnsan dostu sebep açıklaması"""
        regime = signal.get('regime', '-')
        
        if regime == "TREND":
            return "1H trend yönünde kırılım; retest veya güçlü momentum teyidi"
        elif regime == "RANGE":
            return "Dar bantta false-break sonrası içeri dönüş + güçlü mum + hacim"
        elif regime == "SMC":
            return "Likidite süpürme → CHOCH; FVG/OTE bölgesinden dönüş"
        elif regime == "MO":
            return "Momentum + DC/EMA kırılımı"
        elif regime == "PREMO":
            return "Erken tetik: DC kırılımına çok yakın + momentum onayı"
        else:
            return signal.get('reason', '-')
    
    def _analyze_symbol(self, symbol: str) -> str:
        """Sembol analizi yap"""
        from ..config.settings import TF_LTF, TF_HTF, LOOKBACK_LTF, LOOKBACK_HTF
        from ..indicators.technical import rsi, adx, atr_wilder, bollinger, donchian, swing_high, swing_low, ema
        
        # Veri al
        df_ltf = get_ohlcv(self.client, symbol, TF_LTF, LOOKBACK_LTF)
        df_htf = get_ohlcv(self.client, symbol, TF_HTF, LOOKBACK_HTF)
        
        if df_ltf is None or len(df_ltf) < 80 or df_htf is None or len(df_htf) < 60:
            return "Veri alınamadı ya da yetersiz."
        
        # Hesaplamalar
        o, h, l, c, v = df_ltf['o'], df_ltf['h'], df_ltf['l'], df_ltf['c'], df_ltf['v']
        close = float(c.iloc[-1])
        
        # Göstergeler
        rsi14 = float(rsi(c, 14).iloc[-1])
        adx15 = float(adx(h, l, c, 14).iloc[-1])
        atr_val = float(atr_wilder(h, l, c, 14).iloc[-1])
        atr_pct = atr_val / (close + 1e-12)
        
        # Bollinger
        ma, bb_upper, bb_lower, bandwidth, _ = bollinger(c, 20, 2.0)
        bw = float(bandwidth.iloc[-1]) if pd.notna(bandwidth.iloc[-1]) else float('nan')
        bb_upper_val = float(bb_upper.iloc[-1])
        bb_lower_val = float(bb_lower.iloc[-1])
        
        # Donchian
        dc_high, dc_low = donchian(h, l, 20)
        dc_high_val = float(dc_high.iloc[-1])
        dc_low_val = float(dc_low.iloc[-1])
        
        # HTF analiz
        adx1h = float(adx(df_htf['h'], df_htf['l'], df_htf['c'], 14).iloc[-1])
        ema50_1h = ema(df_htf['c'], 50)
        
        bias = "NEUTRAL"
        if pd.notna(ema50_1h.iloc[-1]) and pd.notna(ema50_1h.iloc[-2]):
            if ema50_1h.iloc[-1] > ema50_1h.iloc[-2]:
                bias = "LONG"
            elif ema50_1h.iloc[-1] < ema50_1h.iloc[-2]:
                bias = "SHORT"
        
        trend_ok = adx1h >= 18
        
        # Swing seviyeleri
        sw_high = float(swing_high(h, 10))
        sw_low = float(swing_low(l, 10))
        
        # Rejim tahmini
        regime = "TREND" if trend_ok else ("RANGE" if (not math.isnan(bw) and bw <= 0.055) else "NEUTRAL")
        
        # Pozisyon
        pos_bb = ("Alt banda yakın" if close <= bb_lower_val * (1 + 0.001) else 
                 ("Üst banda yakın" if close >= bb_upper_val * (1 - 0.001) else "Band içi"))
        
        pos_dc = ("Üst kırılım yakın" if close >= dc_high_val * (1 - 0.001) else 
                 ("Alt kırılım yakın" if close <= dc_low_val * (1 + 0.001) else "Orta"))
        
        # ATR+R örnek SL
        atr_mult = MODE_CONFIGS[self.current_mode]['ATR_STOP_MULT']
        risk = atr_mult * atr_val
        sl_long = close - risk
        sl_short = close + risk
        
        text = (
            f"📊 *{symbol}* — Teknik Analiz (15m + 1H)\n"
            f"• Fiyat: `{fmt(close)}` | ATR%≈`{atr_pct:.4f}` | BW≈`{bw:.4f}`\n"
            f"• RSI14(15m): `{rsi14:.1f}` | ADX(15m): `{adx15:.1f}`\n"
            f"• 1H Bias: *{bias}* | ADX(1H): `{adx1h:.1f}` | Trend_OK: *{str(trend_ok)}*\n"
            f"• BB Pozisyon: {pos_bb} | Donchian: {pos_dc}\n"
            f"• Donchian Üst/Alt: `{fmt(dc_high_val)}` / `{fmt(dc_low_val)}` | "
            f"Swing H/L(10): `{fmt(sw_high)}` / `{fmt(sw_low)}`\n"
            f"• Rejim Tahmini: *{regime}*\n\n"
            f"🎯 *Plan İpuçları*\n"
            f"- TREND gününde (ADX1H yüksek): kırılım + retest/momentum kovala.\n"
            f"- RANGE gününde: alt/üst banda sarkıp *içeri dönüş + güçlü mum + hacim* varsa bounce denenir.\n"
            f"- ATR+R Stop/TP: LONG SL `{fmt(sl_long)}` | SHORT SL `{fmt(sl_short)}`. "
            f"TP'ler (1.0R, 1.6R, 2.2R). R = ATR_STOP_MULT × ATR.\n"
        )
        
        return text
    
    async def start_polling(self):
        """Polling başlat"""
        await self.dp.start_polling(self.bot)
    
    def get_current_mode(self) -> str:
        """Mevcut modu döndür"""
        return self.current_mode
