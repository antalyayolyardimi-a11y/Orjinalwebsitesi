# ================== WEB BOT MANAGER ==================
"""
Web uygulaması için bot yöneticisi
Ana trading bot'u web uygulaması ile entegre eder
"""

import asyncio
import time
import json
from typing import Dict, Any, Optional, List
from fastapi import WebSocket
from datetime import datetime

from main import TradingBot
from config.settings import get_settings


class WebBotManager:
    """Web uygulaması için bot yöneticisi"""
    
    def __init__(self):
        self.bot: Optional[TradingBot] = None
        self.is_running = False
        self.websocket_connections: List[WebSocket] = []
        self.stats = {
            'total_scans': 0,
            'signals_sent': 0,
            'last_scan': None,
            'start_time': None
        }
        self.current_signals = []
        self.settings = get_settings()
        
    async def start_bot(self) -> bool:
        """Bot'u başlat"""
        if self.is_running:
            return False
            
        try:
            self.bot = TradingBot()
            # Signal callback'i ayarla
            self.bot.set_signal_callback(self.handle_new_signal)
            
            self.is_running = True
            self.stats['start_time'] = time.time()
            
            # Bot'u arka planda çalıştır
            asyncio.create_task(self.run_bot_loop())
            
            # WebSocket'e durum gönder
            await self.broadcast_status_update('started')
            
            return True
            
        except Exception as e:
            print(f"Bot başlatma hatası: {e}")
            return False
    
    async def stop_bot(self) -> bool:
        """Bot'u durdur"""
        if not self.is_running:
            return False
            
        try:
            self.is_running = False
            self.bot = None
            
            # WebSocket'e durum gönder
            await self.broadcast_status_update('stopped')
            
            return True
            
        except Exception as e:
            print(f"Bot durdurma hatası: {e}")
            return False
    
    async def run_bot_loop(self):
        """Ana bot döngüsü"""
        while self.is_running and self.bot:
            try:
                # Bot tarama işlemini çalıştır
                await self.bot._scan_iteration()
                
                self.stats['total_scans'] += 1
                self.stats['last_scan'] = datetime.now().isoformat()
                
                # İstatistikleri güncelle
                await self.broadcast_stats_update()
                
                # Mode'a göre dinlenme süresi
                from config.settings import MODE_CONFIGS
                scan_interval = MODE_CONFIGS[self.settings.trading_mode].get('SCAN_INTERVAL', 60)
                await asyncio.sleep(scan_interval)
                
            except Exception as e:
                print(f"Bot döngü hatası: {e}")
                await asyncio.sleep(10)  # Hata durumunda kısa bekle
    
    async def handle_new_signal(self, signal: Dict[str, Any]):
        """Yeni sinyal geldiğinde çağrılır"""
        try:
            # Sinyal listesine ekle
            self.current_signals.insert(0, signal)
            
            # Son 50 sinyali tut
            if len(self.current_signals) > 50:
                self.current_signals = self.current_signals[:50]
            
            # İstatistikleri güncelle
            self.stats['signals_sent'] += 1
            
            # WebSocket'lere gönder
            await self.broadcast_new_signal(signal)
            
        except Exception as e:
            print(f"Sinyal işleme hatası: {e}")
    
    async def add_websocket(self, websocket: WebSocket):
        """Yeni WebSocket bağlantısı ekle"""
        self.websocket_connections.append(websocket)
        
        # İlk bağlantıda mevcut durumu gönder
        await self.send_initial_state(websocket)
    
    async def remove_websocket(self, websocket: WebSocket):
        """WebSocket bağlantısını kaldır"""
        if websocket in self.websocket_connections:
            self.websocket_connections.remove(websocket)
    
    async def send_initial_state(self, websocket: WebSocket):
        """WebSocket'e başlangıç durumunu gönder"""
        try:
            data = {
                'type': 'initial_state',
                'is_running': self.is_running,
                'stats': self.stats,
                'current_mode': self.settings.trading_mode,
                'current_signals': self.current_signals[-10:]  # Son 10 sinyal
            }
            
            await websocket.send_text(json.dumps(data))
            
        except Exception as e:
            print(f"Initial state gönderme hatası: {e}")
    
    async def broadcast_new_signal(self, signal: Dict[str, Any]):
        """Tüm WebSocket bağlantılarına yeni sinyal gönder"""
        if not self.websocket_connections:
            return
            
        data = {
            'type': 'new_signal',
            'signal': signal
        }
        
        message = json.dumps(data)
        
        # Bağlantı kopmalarını handle et
        disconnected = []
        
        for websocket in self.websocket_connections:
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.append(websocket)
        
        # Kopan bağlantıları temizle
        for ws in disconnected:
            await self.remove_websocket(ws)
    
    async def broadcast_stats_update(self):
        """Tüm WebSocket bağlantılarına istatistik güncelleme gönder"""
        if not self.websocket_connections:
            return
            
        data = {
            'type': 'stats_update',
            'stats': self.stats
        }
        
        message = json.dumps(data)
        
        disconnected = []
        
        for websocket in self.websocket_connections:
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.append(websocket)
        
        for ws in disconnected:
            await self.remove_websocket(ws)
    
    async def broadcast_status_update(self, status: str):
        """Tüm WebSocket bağlantılarına durum güncelleme gönder"""
        if not self.websocket_connections:
            return
            
        data = {
            'type': 'bot_status',
            'status': status
        }
        
        message = json.dumps(data)
        
        disconnected = []
        
        for websocket in self.websocket_connections:
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.append(websocket)
        
        for ws in disconnected:
            await self.remove_websocket(ws)
    
    async def change_mode(self, mode: str) -> bool:
        """Trading modunu değiştir"""
        try:
            if self.bot:
                self.bot.apply_mode_config(mode)
            
            # Settings'i güncelle
            self.settings.trading_mode = mode
            
            # WebSocket'e bildir
            data = {
                'type': 'mode_changed',
                'mode': mode
            }
            
            message = json.dumps(data)
            
            for websocket in self.websocket_connections:
                try:
                    await websocket.send_text(message)
                except Exception:
                    pass
            
            return True
            
        except Exception as e:
            print(f"Mod değiştirme hatası: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Mevcut istatistikleri getir"""
        return {
            **self.stats,
            'is_running': self.is_running,
            'current_mode': self.settings.trading_mode,
            'signal_count': len(self.current_signals)
        }
    
    def get_recent_signals(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Son sinyalleri getir"""
        return self.current_signals[:limit]


# Global bot manager instance
bot_manager = WebBotManager()
