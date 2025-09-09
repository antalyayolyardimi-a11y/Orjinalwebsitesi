#!/usr/bin/env python3
# ================== WEB APP LAUNCHER ==================
"""
Trading Bot Web Application
Telegram bot'unu web tabanlı uygulamaya dönüştüren launcher
"""

import sys
import os
import asyncio
import uvicorn
from pathlib import Path

# Trading bot ana dizinini ekle
sys.path.insert(0, str(Path(__file__).parent))

from web.app import app
from config.settings import get_settings

def setup_environment():
    """Ortam değişkenlerini ve gerekli ayarları yap"""
    settings = get_settings()
    
    # Port ve host ayarları
    port = int(os.getenv('PORT', 8000))
    host = os.getenv('HOST', '0.0.0.0')
    
    return host, port, settings

def main():
    """Ana uygulama başlatıcı"""
    print("=" * 50)
    print("🚀 TRADING BOT WEB APPLICATION")
    print("=" * 50)
    
    try:
        host, port, settings = setup_environment()
        
        print(f"📊 Mod: {settings.trading_mode}")
        print(f"🌐 Host: {host}:{port}")
        print(f"📈 Desteklenen çiftler: {len(settings.symbols)}")
        print("-" * 50)
        
        # Web sunucusunu başlat
        uvicorn.run(
            "web.app:app",
            host=host,
            port=port,
            reload=False,
            log_level="info",
            access_log=True
        )
        
    except KeyboardInterrupt:
        print("\n⏹️ Uygulama kapatılıyor...")
    except Exception as e:
        print(f"❌ Hata: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
