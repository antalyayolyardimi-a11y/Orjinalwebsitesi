# ================== DOCKER CONFIGURATION ==================

FROM python:3.11-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Sistem paketlerini güncelle
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Requirements'ları kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY . .

# Port'u aç
EXPOSE 8000

# Uygulama klasör izinlerini ayarla
RUN chmod +x run_web.py

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Uygulamayı başlat
CMD ["python", "run_web.py"]
