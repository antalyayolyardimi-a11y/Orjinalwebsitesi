# ================== WEB APPLICATION ==================
"""
FastAPI tabanlı web uygulaması - Trading sinyalleri için modern web arayüzü
"""

import asyncio
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
from kucoin.client import Market

from config.settings import get_settings, MODE_CONFIGS
from utils.helpers import log, get_ohlcv
from indicators.technical import get_technical_data
from web.bot_manager import bot_manager

# FastAPI uygulaması
app = FastAPI(title="Trading Bot Web App", version="2.0.0")

# Templates ve static files
templates = Jinja2Templates(directory="web/templates")
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# Settings
settings = get_settings()
client = Market(url="https://api.kucoin.com")


# ================== ROUTES ==================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Ana dashboard sayfası"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "modes": list(MODE_CONFIGS.keys()),
        "current_mode": settings.trading_mode
    })

@app.get("/signals", response_class=HTMLResponse) 
async def signals_page(request: Request):
    """Sinyal geçmişi sayfası"""
    signals = bot_manager.get_recent_signals(50)
    return templates.TemplateResponse("signals.html", {
        "request": request,
        "signals": signals
    })

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/stats")
async def get_stats():
    """Bot istatistiklerini getir"""
    return bot_manager.get_stats()

@app.post("/bot/start")
async def start_bot():
    """Bot'u başlat"""
    success = await bot_manager.start_bot()
    
    if success:
        return {"message": "Bot başarıyla başlatıldı"}
    else:
        raise HTTPException(status_code=400, detail="Bot zaten çalışıyor veya başlatılamadı")

@app.post("/bot/stop")
async def stop_bot():
    """Bot'u durdur"""
    success = await bot_manager.stop_bot()
    
    if success:
        return {"message": "Bot başarıyla durduruldu"}
    else:
        raise HTTPException(status_code=400, detail="Bot zaten durmuş veya durdurulamadı")

@app.post("/mode")
async def change_mode(mode: str = Form(...)):
    """Trading modunu değiştir"""
    if mode not in MODE_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Geçersiz mod: {mode}")
    
    success = await bot_manager.change_mode(mode)
    
    if success:
        return {"message": f"Mod başarıyla değiştirildi: {mode}"}
    else:
        raise HTTPException(status_code=500, detail="Mod değiştirilemedi")

@app.get("/analysis/{symbol}")
async def analyze_symbol(symbol: str):
    """Tek sembol analizi"""
    try:
        # Sembol formatını kontrol et
        if not symbol.endswith('-USDT'):
            symbol = f"{symbol}-USDT"
        
        # Teknik veriyi al
        data = get_technical_data(client, symbol)
        
        if not data:
            raise HTTPException(status_code=404, detail="Sembol verisi bulunamadı")
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            **data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ================== WEBSOCKET ==================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint - gerçek zamanlı veri akışı"""
    await websocket.accept()
    
    try:
        # Bot manager'a WebSocket'i ekle
        await bot_manager.add_websocket(websocket)
        
        # Bağlantıyı canlı tut
        while True:
            try:
                # Ping-pong için message bekle
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # Heartbeat mesajı
                if data == "ping":
                    await websocket.send_text("pong")
                    
            except asyncio.TimeoutError:
                # Timeout durumunda ping gönder
                await websocket.send_text(json.dumps({"type": "ping"}))
                
    except WebSocketDisconnect:
        # Bağlantı kesildiğinde bot manager'dan kaldır
        await bot_manager.remove_websocket(websocket)
        
    except Exception as e:
        log(f"WebSocket hatası: {e}")
        await bot_manager.remove_websocket(websocket)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
