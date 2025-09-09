# ================== MAIN TRADING BOT ==================
"""
Ana trading bot - tüm modülleri bir araya getiren ana dosya
Web uygulaması ile entegre edilmiş versiyon
"""

import asyncio
import time
import random
import nest_asyncio
from typing import List, Dict, Any, Optional, Callable
from kucoin.client import Market

# Konfigürasyon
from config.settings import *

# Utilities
from utils.helpers import log, get_ohlcv, chunked, build_vol_pct_cache, SymbolManager
from utils.scoring import scoring_system
from utils.risk_management import compute_sl_tp_atr

# Strategies
from strategies.smc import SMCStrategy
from strategies.trend import TrendStrategy
from strategies.range_strategy import RangeStrategy
from strategies.momentum import MomentumStrategy

# AI
from ai.predictor import ai_predictor


class TradingBot:
    """Ana Trading Bot sınıfı - Web uygulaması entegreli"""
    
    def __init__(self):
        # KuCoin client
        self.client = Market(url="https://api.kucoin.com")
        
        # Signal callback (web uygulaması tarafından ayarlanacak)
        self.signal_callback: Optional[Callable] = None
        
        # Symbol manager
        self.symbol_manager = SymbolManager(self.client)
        
        # Strategies
        self.strategies = [
            SMCStrategy(),
            TrendStrategy(),
            RangeStrategy(),
            MomentumStrategy()
        ]
        
        # Performance tracker
        self.performance = PerformanceTracker()
        
        # Bot state
        self.last_signal_ts = {}  # Symbol bazlı son sinyal zamanları
        self.position_state = {}  # Symbol bazlı pozisyon durumları
        self.vol_pct_cache = {}   # Hacim yüzdelik cache
        
        # Dynamic settings
        self.dynamic_min_score = BASE_MIN_SCORE
        self.empty_scans = 0
        self.relax_accumulator = 0
        
        # Auto-tuner
        self.last_tune_timestamp = 0
        
        # Current mode
        self.current_mode = 'balanced'
        
        log(f"🚀 Trading Bot başlatıldı. Mode: {self.current_mode}")
    
    def set_signal_callback(self, callback: Callable):
        """Sinyal callback'ini ayarla"""
        self.signal_callback = callback
    
    def get_current_mode(self) -> str:
        """Mevcut modu getir"""
        return self.current_mode
    
    def apply_mode_config(self, mode: str) -> None:
        """Mode konfigürasyonunu uygula"""
        if mode not in MODE_CONFIGS:
            log(f"❗ Geçersiz mod: {mode}")
            return
        
        config = MODE_CONFIGS[mode]
        self.current_mode = mode
        
        # Global değişkenleri güncelle
        globals().update(config)
        
        # Dynamic score'u güncelle
        self.dynamic_min_score = config['BASE_MIN_SCORE']
        
        log(f"📝 Mode '{mode}' uygulandı.")
    
    async def scan_symbol(self, symbol: str, semaphore: asyncio.Semaphore) -> Optional[Dict[str, Any]]:
        """Tek bir sembolü tara"""
        async with semaphore:
            if VERBOSE_SCAN:
                log(f"🔎 Taranıyor: {symbol}")
            
            now = time.time()
            
            # Cooldown kontrolü
            if symbol in self.last_signal_ts and now - self.last_signal_ts[symbol] < COOLDOWN_SEC:
                if SHOW_SKIP_REASONS:
                    log(f"⏳ (cooldown) atlanıyor: {symbol}")
                return None
            
            # Veri al
            df_ltf = get_ohlcv(self.client, symbol, TF_LTF, LOOKBACK_LTF)
            df_htf = get_ohlcv(self.client, symbol, TF_HTF, LOOKBACK_HTF)
            
            if df_ltf is None or len(df_ltf) < 80 or df_htf is None or len(df_htf) < 60:
                if SHOW_SKIP_REASONS:
                    log(f"— Veri yok/az: {symbol}")
                return None
            
            # Bar tekrarı kontrolü
            last_bar_ts = int(df_ltf["time"].iloc[-1].timestamp())
            
            if (symbol in self.position_state and 
                self.position_state[symbol].get("last_bar_ts") == last_bar_ts):
                if SHOW_SKIP_REASONS:
                    log(f"— Aynı bar, atlanıyor: {symbol}")
                return None
            
            # Strateji analizleri
            best_candidate = None
            best_score = 0
            
            for strategy in self.strategies:
                try:
                    candidate = strategy.analyze(df_ltf, df_htf, symbol)
                    if candidate:
                        # Skorla
                        vol_pct = self.vol_pct_cache.get(symbol, 0.5)
                        scored_candidate = scoring_system.evaluate_candidate(
                            symbol, df_ltf, df_htf, candidate, vol_pct
                        )
                        
                        if scored_candidate['score'] > best_score:
                            best_candidate = scored_candidate
                            best_score = scored_candidate['score']
                
                except Exception as e:
                    log(f"Strateji hatası ({strategy.name}, {symbol}): {e}")
            
            if not best_candidate:
                if SHOW_SKIP_REASONS:
                    log(f"— Aday yok: {symbol}")
                return None
            
            # Emit kontrolü (ters yön koruması)
            if not self._can_emit_signal(symbol, best_candidate['side'], df_ltf):
                if SHOW_SKIP_REASONS:
                    log(f"— Aday blok (flip): {symbol}")
                return None
            
            if VERBOSE_SCAN:
                log(f"✓ Aday: {symbol} {best_candidate['side']} | Skor={int(best_candidate['score'])}")
            
            # Ek bilgileri ekle
            best_candidate["_bar_idx"] = len(df_ltf) - 1
            best_candidate["_last_bar_ts"] = last_bar_ts
            
            return best_candidate
    
    def _can_emit_signal(self, symbol: str, side: str, df_ltf) -> bool:
        """Sinyal emit edilebilir mi kontrolü"""
        position_state = self.position_state.get(symbol)
        
        if position_state is None:
            return True
        
        # Aynı yönde ise engeleme
        if side == position_state['side']:
            return False
        
        # Ters yön için minimum bar bekleme
        bars_since = (len(df_ltf) - 1) - position_state['bar_idx']
        return bars_since >= OPPOSITE_MIN_BARS
    
    async def run_scanner(self) -> None:
        """Ana tarama döngüsü"""
        while True:
            try:
                await self._scan_iteration()
                await asyncio.sleep(SLEEP_SECONDS)
            except Exception as e:
                log(f"❌ Tarama hatası: {e}")
                await asyncio.sleep(30)  # Hata durumunda kısa bekle
    
    async def _scan_iteration(self) -> None:
        """Tek bir tarama iterasyonu"""
        
        # Performance tracking güncelle
        self.performance.update()
        
        # Auto-tuning
        self._auto_tune()
        
        # Symbol listesi al
        symbols = self.symbol_manager.get_usdt_pairs(MIN_VOLVALUE_USDT)
        
        if not symbols:
            log("❗ Uygun sembol bulunamadı")
            return
        
        # Rastgele karıştır ve sınırla
        random.shuffle(symbols)
        symbols = symbols[:SCAN_LIMIT]
        
        # Hacim cache güncelle
        try:
            tickers = self.client.get_all_tickers().get("ticker", [])
            volmap = {t.get("symbol"): float(t.get("volValue", 0.0)) for t in tickers}
            self.vol_pct_cache = build_vol_pct_cache(symbols, volmap)
        except Exception as e:
            log(f"Hacim cache hatası: {e}")
        
        log(f"Taranacak sembol sayısı: {len(symbols)} | Mode: {self.telegram_bot.get_current_mode()}")
        
        if SHOW_SYMBOL_LIST_AT_START:
            for chunk in chunked(symbols, CHUNK_PRINT):
                log("Taranacak: " + "  ".join(chunk))
        
        # Paralel tarama
        start_time = time.time()
        semaphore = asyncio.Semaphore(SYMBOL_CONCURRENCY)
        
        tasks = [self.scan_symbol(symbol, semaphore) for symbol in symbols]
        results = await asyncio.gather(*tasks)
        
        # Sonuçları işle
        candidates = [r for r in results if r]
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        # Sinyal gönderimi
        sent_count = await self._process_candidates(candidates)
        
        scan_time = time.time() - start_time
        log(f"♻️ Tarama tamam ({scan_time:.1f}s). Gönderilen: {sent_count}. "
            f"DynMinScore={self.dynamic_min_score} | Mode={self.current_mode}")
        
        # Adaptif gevşetme
        self._adaptive_relaxation(len([c for c in candidates if c["score"] >= self.dynamic_min_score]))
    
    async def _process_candidates(self, candidates: List[Dict[str, Any]]) -> int:
        """Adayları işle ve sinyal gönder"""
        sent_count = 0
        strong_count = sum(1 for c in candidates if c["score"] >= self.dynamic_min_score)
        
        for candidate in candidates:
            if sent_count >= TOP_N_PER_SCAN:
                break
            
            # Skor kontrolü
            should_send = (
                candidate["score"] >= self.dynamic_min_score or
                (strong_count == 0 and candidate["score"] >= FALLBACK_MIN_SCORE)
            )
            
            if should_send:
                # AI ile zenginleştir
                features = candidate.get('_features', {})
                candidate = ai_predictor.enrich_candidate(candidate, features)
                
                # Log
                symbol = candidate["symbol"]
                side = candidate["side"]
                entry = candidate["entry"]
                tps = candidate["tps"]
                sl = candidate["sl"]
                score = candidate["score"]
                reason = candidate["reason"]
                
                log(f"✅ {symbol} {side} | Entry={entry:.6f} "
                    f"TP1={tps[0]:.6f} TP2={tps[1]:.6f} TP3={tps[2]:.6f} "
                    f"SL={sl:.6f} | Skor={int(score)} | {reason}")
                
                # Web callback'e gönder
                success = await self._send_signal_web(candidate)
                
                if success:
                    # State güncelle
                    self.last_signal_ts[symbol] = time.time()
                    self.position_state[symbol] = {
                        'side': side,
                        'bar_idx': candidate["_bar_idx"],
                        'last_bar_ts': candidate["_last_bar_ts"]
                    }
                    
                    # Performance tracking'e ekle
                    self.performance.add_signal(candidate)
                    
                    sent_count += 1
        
        return sent_count
    
    def _adaptive_relaxation(self, strong_count: int) -> None:
        """Adaptif gevşetme sistemi"""
        if strong_count == 0:
            self.empty_scans += 1
            
            if self.empty_scans >= EMPTY_LIMIT and self.relax_accumulator < RELAX_MAX:
                self.dynamic_min_score = max(MIN_SCORE_FLOOR, 
                                           self.dynamic_min_score - RELAX_STEP)
                self.relax_accumulator += RELAX_STEP
                self.empty_scans = 0
                log(f"🔄 Adaptif gevşetme: MinScore -> {self.dynamic_min_score}")
        else:
            self.empty_scans = 0
            # Normale dön
            self.dynamic_min_score = max(self.dynamic_min_score, BASE_MIN_SCORE)
    
    def _auto_tune(self) -> None:
        """Otomatik ayar sistemi"""
        if not AUTO_TUNER_ON:
            return
        
        now = time.time()
        
        if now - self.last_tune_timestamp < TUNE_COOLDOWN_SEC:
            return
        
        # Performance analizi
        stats = self.performance.get_stats()
        
        if stats['total_signals'] < WIN_MIN_SAMPLES:
            return
        
        recent_wr = stats.get('recent_win_rate', 0.5)
        
        # Auto-tuning logic burada implementa edilebilir
        # Şimdilik basit bir yaklaşım
        if recent_wr < WR_TARGET - 0.05:
            # Win rate düşükse daha muhafazakar ol
            self.dynamic_min_score = min(MIN_SCORE_CEIL, self.dynamic_min_score + 2)
            log(f"🛠️ AutoTune: WR={recent_wr:.2f} < hedef, MinScore -> {self.dynamic_min_score}")
        elif recent_wr > WR_TARGET + 0.05:
            # Win rate yüksekse daha agresif ol
            self.dynamic_min_score = max(MIN_SCORE_FLOOR, self.dynamic_min_score - 1)
            log(f"🛠️ AutoTune: WR={recent_wr:.2f} > hedef, MinScore -> {self.dynamic_min_score}")
        
        self.last_tune_timestamp = now
    
    async def _send_signal_web(self, signal: Dict[str, Any]) -> bool:
        """Web uygulaması aracılığıyla sinyal gönder"""
        try:
            if self.signal_callback:
                # Format signal for web
                web_signal = {
                    'symbol': signal['symbol'],
                    'side': signal['side'],
                    'entry': float(signal['entry']),
                    'sl': float(signal['sl']),
                    'tp1': float(signal['tps'][0]),
                    'tp2': float(signal['tps'][1]),
                    'tp3': float(signal['tps'][2]),
                    'score': int(signal['score']),
                    'regime': signal.get('regime', 'UNKNOWN'),
                    'reason': signal.get('reason', ''),
                    'timestamp': time.time()
                }
                
                # Callback'i çağır
                await self.signal_callback(web_signal)
                return True
            else:
                log("⚠️ Web callback tanımlı değil")
                return False
                
        except Exception as e:
            log(f"❌ Web sinyal gönderme hatası: {e}")
            return False
    
    async def run_scanner(self) -> None:
        """Scanner döngüsünü çalıştır"""
        log("🔍 Scanner başlatıldı")
        
        while True:
            try:
                await self._scan_iteration()
                # Mode'a göre scan interval kullan
                scan_interval = MODE_CONFIGS[self.current_mode].get('SCAN_INTERVAL', 60)
                await asyncio.sleep(scan_interval)
            except Exception as e:
                log(f"❌ Scanner hatası: {e}")
                await asyncio.sleep(10)  # Hata durumunda kısa bekle


class PerformanceTracker:
    """Performans takip sınıfı"""
    
    def __init__(self):
        self.signals_history = []
        self.last_update = 0
    
    def add_signal(self, signal: Dict[str, Any]) -> None:
        """Sinyal ekle"""
        self.signals_history.append({
            'symbol': signal['symbol'],
            'side': signal['side'],
            'entry': signal['entry'],
            'sl': signal['sl'],
            'tp1': signal['tps'][0],
            'timestamp': time.time(),
            'resolved': False,
            'result': None,
            'features': signal.get('_features', {})
        })
    
    def update(self) -> None:
        """Performansı güncelle"""
        now = time.time()
        
        # 5 dakikada bir güncelle
        if now - self.last_update < 300:
            return
        
        self._resolve_signals()
        self.last_update = now
    
    def _resolve_signals(self) -> None:
        """Açık sinyalleri çöz"""
        # Bu fonksiyon gerçek fiyat verilerini kontrol ederek
        # TP veya SL seviyelerine ulaşılıp ulaşılmadığını kontrol eder
        # Şimdilik basit bir implementasyon
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """İstatistikleri döndür"""
        resolved_signals = [s for s in self.signals_history if s['resolved']]
        
        if not resolved_signals:
            return {'total_signals': 0, 'win_rate': 0.0, 'recent_win_rate': 0.0}
        
        wins = sum(1 for s in resolved_signals if s['result'] == 'TP')
        total = len(resolved_signals)
        
        # Son 50 sinyal
        recent = resolved_signals[-50:]
        recent_wins = sum(1 for s in recent if s['result'] == 'TP')
        recent_total = len(recent)
        
        return {
            'total_signals': total,
            'wins': wins,
            'win_rate': wins / total if total > 0 else 0.0,
            'recent_win_rate': recent_wins / recent_total if recent_total > 0 else 0.0
        }


async def main():
    """Ana fonksiyon - Web uygulaması olmadan test için"""
    nest_asyncio.apply()
    
    bot = TradingBot()
    
    # Test callback
    async def test_callback(signal):
        print(f"Test Signal: {signal['symbol']} {signal['side']}")
    
    bot.set_signal_callback(test_callback)
    await bot.run_scanner()


if __name__ == "__main__":
    # Sadece test için - normalde web uygulaması tarafından çağrılır
    asyncio.run(main())
