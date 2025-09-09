# 🚀 Trading Bot Web Application

Modern web tabanlı kripto para trading bot'u. KuCoin API kullanarak gerçek zamanlı sinyal üretimi ve web arayüzü ile bot yönetimi.

## ✨ Özellikler

### 🎯 Trading Algoritmaları
- **SMC (Smart Money Concept)**: Kurumsal para akışı takibi
- **Trend Following**: Trend yönünde sinyal üretimi  
- **Range Trading**: Yatay piyasalarda range stratejisi
- **Momentum**: Momentuma dayalı işlemler

### 🧠 AI Destekli Sinyal Filtreleme
- Online Logistic Regression ile sinyal kalitesi tahmini
- Geçmiş performansa dayalı öğrenme sistemi
- Adaptif sinyal skorlama

### ⚙️ Modüler Sistem
- **Aggressive Mode**: Yüksek frekanslı sinyal üretimi
- **Balanced Mode**: Orta seviye risk/getiri dengesi  
- **Conservative Mode**: Düşük riskli, seçici sinyaller

### 🌐 Web Arayüzü
- Gerçek zamanlı sinyal görüntüleme
- WebSocket ile canlı veri akışı
- Responsive Bootstrap 5 tasarım
- Bot kontrolü ve mod değiştirme
- Sembol analiz aracı

## 🛠️ Kurulum

### 1. Gereksinimleri Yükle
```bash
pip install -r requirements.txt
```

### 2. Ortam Değişkenlerini Ayarla
```bash
cp .env.example .env
# .env dosyasını düzenleyip API bilgilerinizi girin
```

### 3. Uygulamayı Başlat
```bash
python run_web.py
```

Bot `http://localhost:8000` adresinde çalışmaya başlar.

## 🚀 Kullanım

### Web Arayüzü ile Bot Başlatma
1. Tarayıcıda `http://localhost:8000` adresine git
2. "Bot'u Başlat" butonuna tıkla
3. Gerçek zamanlı sinyalleri izle
4. İhtiyaç halinde trading modunu değiştir

---

**⚠️ Risk Uyarısı**: Bu bot eğitim amaçlıdır. Gerçek trading'de kullanımı kendi riskinizdir.
- **Momentum**: Erken breakout sinyalleri, pre-break tetikleyicileri

### 🧠 Yapay Zeka
- Online Logistic Regression ile özelliklere dayalı öğrenme
- Gerçek zamanlı performance feedback
- Adaptif parametre optimizasyonu

### ⚖️ Risk Yönetimi
- ATR tabanlı Stop Loss ve Take Profit
- Dinamik pozisyon boyutlandırma
- Multi-level TP seviyeleri (1.0R, 1.6R, 2.2R)

### 📊 Teknik Analiz
- 15+ teknik gösterge (RSI, ADX, ATR, Bollinger Bands, Donchian, vb.)
- Multi-timeframe analizi (15m + 1H)
- Swing analizi ve FVG tespiti

### 📱 Telegram Entegrasyonu
- Anlık sinyal bildirimleri
- Interaktif komutlar (/analiz, /mode, /aistats)
- Detaylı teknik analiz raporları

## 🏗️ Modüler Yapı

```
trading_bot/
├── config/          # Konfigürasyon dosyaları
├── strategies/      # Trading stratejileri
├── indicators/      # Teknik göstergeler
├── utils/          # Yardımcı fonksiyonlar
├── ai/             # Yapay zeka modülü
├── telegram/       # Telegram bot
└── main.py         # Ana bot dosyası
```

## 🚀 Kurulum

1. **Gereksinim Kurulumu**:
```bash
pip install kucoin-python aiogram nest_asyncio pandas numpy
```

2. **Konfigürasyon**:
   - `config/settings.py` dosyasında Telegram token'ınızı güncelleyin
   - Trading parametrelerini ihtiyacınıza göre ayarlayın

3. **Çalıştırma**:
```bash
python main.py
```

## ⚙️ Modlar

### 🔥 Aggressive
- Düşük hacim eşiği (700k USDT)
- Düşük minimum skor (52)
- Fazla sinyal sayısı (5 adet)
- Kısa cooldown (15 dakika)

### ⚖️ Balanced (Varsayılan)
- Orta hacim eşiği (2M USDT)
- Orta minimum skor (68)
- Dengeli sinyal sayısı (2 adet)
- Orta cooldown (30 dakika)

### 🛡️ Conservative
- Yüksek hacim eşiği (3M USDT)
- Yüksek minimum skor (72)
- Az sinyal sayısı (2 adet)
- Uzun cooldown (40 dakika)

## 📋 Telegram Komutları

- `/start` - Bot'u başlat
- `/mode [aggressive|balanced|conservative]` - Trading modu değiştir
- `/analiz [SEMBOL]` - Sembol analizi yap (örn: /analiz WIFUSDT)
- `/aistats` - AI istatistiklerini görüntüle
- `/aireset` - AI'yı sıfırla

## 🎯 Sinyal Formatı

```
🔔 WIF-USDT • LONG • SMC • Mode: balanced

Özet
• 1H Bias: LONG
• Neden: Likidite süpürme → CHOCH; FVG/OTE bölgesinden dönüş
• R (TP1'e): 2.1

Seviyeler
• Entry : 2.345600
• SL    : 2.298400
• TP1   : 2.392800
• TP2   : 2.421200
• TP3   : 2.449600

Notlar
- SL (Stop Loss): Zarar durdur.
- TP (Take Profit): Kar al seviyeleri.
- R: ATR_STOP_MULT × ATR; 1.0R = SL mesafesi.
```

## 🔧 Özelleştirme

### Yeni Strateji Ekleme

1. `strategies/` klasöründe yeni strateji dosyası oluşturun
2. `BaseStrategy` sınıfından türetin
3. `analyze()` metodunu implement edin
4. `main.py`'de strategy listesine ekleyin

### Yeni Gösterge Ekleme

1. `indicators/technical.py` dosyasına yeni fonksiyon ekleyin
2. Strateji dosyalarında import edin ve kullanın

### Parametre Ayarlama

Tüm trading parametreleri `config/settings.py` dosyasında merkezi olarak yönetiliyor.

## 📊 Performance Tracking

Bot otomatik olarak performance tracking yapar:
- Win rate hesaplaması
- Adaptif parametre optimizasyonu
- AI tabanlı sürekli öğrenme

## ⚠️ Risk Uyarıları

- Bu bot eğitim amaçlıdır, gerçek para ile kullanmadan önce test edin
- Stop loss seviyelerine mutlaka uyun
- Pozisyon boyutunuzu risk toleransınıza göre ayarlayın
- Piyasa koşullarını sürekli izleyin

## 📞 Destek

Sorularınız için GitHub Issues kullanabilirsiniz.

## 📄 Lisans

MIT License - Detaylar için LICENSE dosyasına bakın.

---

⚡ **Happy Trading!** ⚡
