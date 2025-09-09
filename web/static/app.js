// ================== TRADING BOT JAVASCRIPT ==================

class TradingBotApp {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        this.init();
    }
    
    init() {
        this.connectWebSocket();
        this.setupEventListeners();
        this.updateUptime();
        this.setupModeInfo();
        
        // Her 10 saniyede bir uptime güncelle
        setInterval(() => this.updateUptime(), 10000);
    }
    
    // ================== WEBSOCKET ==================
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket bağlantısı kuruldu');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus(true);
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket bağlantısı kapandı');
                this.isConnected = false;
                this.updateConnectionStatus(false);
                this.attemptReconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket hatası:', error);
                this.isConnected = false;
                this.updateConnectionStatus(false);
            };
            
        } catch (error) {
            console.error('WebSocket oluşturma hatası:', error);
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Yeniden bağlanma denemesi ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
            
            setTimeout(() => {
                this.connectWebSocket();
            }, 3000 * this.reconnectAttempts);
        }
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'initial_state':
                this.updateDashboard(data);
                break;
                
            case 'new_signal':
                this.addNewSignal(data.signal);
                break;
                
            case 'stats_update':
                this.updateStats(data.stats);
                break;
                
            case 'bot_status':
                this.updateBotStatus(data.status);
                break;
                
            case 'mode_changed':
                this.updateMode(data.mode);
                break;
        }
    }
    
    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            statusElement.textContent = connected ? 'Bağlı' : 'Bağlantı Kesildi';
            statusElement.className = connected ? 'text-success' : 'text-danger';
        }
    }
    
    // ================== UI UPDATES ==================
    updateDashboard(data) {
        // Bot status
        this.updateBotStatus(data.is_running ? 'started' : 'stopped');
        
        // Stats
        this.updateStats(data.stats);
        
        // Mode
        document.getElementById('current-mode').textContent = data.current_mode.charAt(0).toUpperCase() + data.current_mode.slice(1);
        
        // Signals
        if (data.current_signals && data.current_signals.length > 0) {
            data.current_signals.forEach(signal => this.addSignalToDOM(signal));
        }
    }
    
    updateBotStatus(status) {
        const statusText = document.getElementById('bot-status');
        const statusIcon = document.getElementById('status-icon');
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        
        if (status === 'started') {
            statusText.textContent = 'Çalışıyor';
            statusIcon.classList.add('text-success');
            statusIcon.classList.remove('text-danger');
            document.body.classList.add('status-running');
            document.body.classList.remove('status-stopped');
            
            startBtn.disabled = true;
            stopBtn.disabled = false;
        } else {
            statusText.textContent = 'Durdurulmuş';
            statusIcon.classList.add('text-danger');
            statusIcon.classList.remove('text-success');
            document.body.classList.add('status-stopped');
            document.body.classList.remove('status-running');
            
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }
    }
    
    updateStats(stats) {
        document.getElementById('total-scans').textContent = stats.total_scans || 0;
        document.getElementById('signals-sent').textContent = stats.signals_sent || 0;
        
        if (stats.last_scan) {
            const lastScanDate = new Date(stats.last_scan);
            document.getElementById('last-scan').textContent = lastScanDate.toLocaleString('tr-TR');
        }
    }
    
    updateMode(mode) {
        document.getElementById('current-mode').textContent = mode.charAt(0).toUpperCase() + mode.slice(1);
        document.getElementById('mode-select').value = mode;
        this.showModeInfo(mode);
    }
    
    addNewSignal(signal) {
        this.addSignalToDOM(signal, true);
        this.updateSignalCount();
        this.showNotification(`Yeni sinyal: ${signal.symbol} ${signal.side}`, 'success');
    }
    
    addSignalToDOM(signal, isNew = false) {
        const container = document.getElementById('signals-container');
        const noSignalsDiv = document.getElementById('no-signals');
        
        if (noSignalsDiv) {
            noSignalsDiv.style.display = 'none';
        }
        
        const signalElement = this.createSignalElement(signal, isNew);
        container.insertBefore(signalElement, container.firstChild);
        
        // Son 20 sinyali tut
        const signals = container.querySelectorAll('.signal-card');
        if (signals.length > 20) {
            signals[signals.length - 1].remove();
        }
    }
    
    createSignalElement(signal, isNew = false) {
        const div = document.createElement('div');
        div.className = `signal-card mb-3 ${isNew ? 'new-signal' : ''}`;
        
        const rr = signal.side === 'LONG' 
            ? (signal.tp1 - signal.entry) / (signal.entry - signal.sl)
            : (signal.entry - signal.tp1) / (signal.sl - signal.entry);
        
        div.innerHTML = `
            <div class="signal-header">
                <span class="signal-symbol">${signal.symbol}</span>
                <span class="signal-side ${signal.side.toLowerCase()}">${signal.side}</span>
                <span class="signal-regime">${signal.regime}</span>
                <small class="signal-time">${new Date(signal.timestamp).toLocaleString('tr-TR')}</small>
            </div>
            <div class="signal-levels">
                <div class="row">
                    <div class="col-3">
                        <small class="text-muted">Entry</small>
                        <div class="level-value">${signal.entry.toFixed(6)}</div>
                    </div>
                    <div class="col-3">
                        <small class="text-muted">SL</small>
                        <div class="level-value">${signal.sl.toFixed(6)}</div>
                    </div>
                    <div class="col-6">
                        <small class="text-muted">TP1 / TP2 / TP3</small>
                        <div class="level-value">
                            ${signal.tp1.toFixed(6)} / 
                            ${signal.tp2.toFixed(6)} / 
                            ${signal.tp3.toFixed(6)}
                        </div>
                    </div>
                </div>
            </div>
            <div class="signal-footer">
                <small class="text-muted">
                    Skor: ${Math.round(signal.score)} | R: ${rr.toFixed(2)} | ${signal.reason}
                </small>
            </div>
        `;
        
        return div;
    }
    
    updateSignalCount() {
        const signalCount = document.querySelectorAll('.signal-card').length;
        const countElement = document.getElementById('signal-count');
        if (countElement) {
            countElement.textContent = signalCount;
        }
    }
    
    // ================== EVENT LISTENERS ==================
    setupEventListeners() {
        // Mode form
        const modeForm = document.getElementById('mode-form');
        if (modeForm) {
            modeForm.addEventListener('submit', this.handleModeChange.bind(this));
        }
        
        // Mode selector change
        const modeSelect = document.getElementById('mode-select');
        if (modeSelect) {
            modeSelect.addEventListener('change', (e) => {
                this.showModeInfo(e.target.value);
            });
        }
    }
    
    async handleModeChange(event) {
        event.preventDefault();
        
        const formData = new FormData(event.target);
        const mode = formData.get('mode');
        
        try {
            const response = await fetch('/mode', {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                this.showNotification(`Mod başarıyla değiştirildi: ${mode}`, 'success');
            } else {
                throw new Error('Mod değiştirme başarısız');
            }
        } catch (error) {
            console.error('Mod değiştirme hatası:', error);
            this.showNotification('Mod değiştirme başarısız', 'error');
        }
    }
    
    // ================== BOT CONTROLS ==================
    async startBot() {
        try {
            const response = await fetch('/bot/start', { method: 'POST' });
            if (response.ok) {
                this.showNotification('Bot başlatıldı', 'success');
            } else {
                throw new Error('Bot başlatma başarısız');
            }
        } catch (error) {
            console.error('Bot başlatma hatası:', error);
            this.showNotification('Bot başlatma başarısız', 'error');
        }
    }
    
    async stopBot() {
        try {
            const response = await fetch('/bot/stop', { method: 'POST' });
            if (response.ok) {
                this.showNotification('Bot durduruldu', 'info');
            } else {
                throw new Error('Bot durdurma başarısız');
            }
        } catch (error) {
            console.error('Bot durdurma hatası:', error);
            this.showNotification('Bot durdurma başarısız', 'error');
        }
    }
    
    // ================== UTILITIES ==================
    updateUptime() {
        const uptimeElement = document.getElementById('uptime');
        if (uptimeElement) {
            const startTime = new Date().getTime() - 3600000; // Örnek başlangıç zamanı
            const uptime = Math.floor((new Date().getTime() - startTime) / 1000);
            
            const hours = Math.floor(uptime / 3600);
            const minutes = Math.floor((uptime % 3600) / 60);
            const seconds = uptime % 60;
            
            uptimeElement.textContent = `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
    }
    
    showModeInfo(mode) {
        document.querySelectorAll('.mode-info').forEach(info => {
            info.classList.remove('active');
        });
        
        const modeInfo = document.querySelector(`[data-mode="${mode}"]`);
        if (modeInfo) {
            modeInfo.classList.add('active');
        }
    }
    
    showNotification(message, type = 'info') {
        // Basit notification sistemi
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // 5 saniye sonra otomatik kapat
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }
    
    async analyzeSymbol() {
        const symbolInput = document.getElementById('symbol-input');
        const resultDiv = document.getElementById('analysis-result');
        const symbol = symbolInput.value.trim().toUpperCase();
        
        if (!symbol) {
            this.showNotification('Lütfen bir sembol girin', 'error');
            return;
        }
        
        resultDiv.innerHTML = '<div class="analysis-loading"><i class="fas fa-spinner fa-spin me-2"></i>Analiz ediliyor...</div>';
        
        try {
            const response = await fetch(`/analysis/${symbol}`);
            const data = await response.json();
            
            if (response.ok) {
                this.displayAnalysisResult(data, resultDiv);
            } else {
                throw new Error(data.detail || 'Analiz hatası');
            }
        } catch (error) {
            console.error('Analiz hatası:', error);
            resultDiv.innerHTML = `<div class="analysis-error">Hata: ${error.message}</div>`;
        }
    }
    
    displayAnalysisResult(data, container) {
        const html = `
            <div class="analysis-success">
                <h6><i class="fas fa-chart-line me-2"></i>${data.symbol} Analizi</h6>
                <div class="row mt-3">
                    <div class="col-md-6">
                        <p><strong>Fiyat:</strong> ${data.price.toFixed(6)}</p>
                        <p><strong>RSI:</strong> ${data.rsi.toFixed(2)}</p>
                        <p><strong>ADX:</strong> ${data.adx.toFixed(2)}</p>
                        <p><strong>ATR %:</strong> ${data.atr_percent.toFixed(4)}%</p>
                    </div>
                    <div class="col-md-6">
                        <p><strong>BB Genişlik:</strong> ${data.bandwidth.toFixed(4)}</p>
                        <p><strong>BB Üst:</strong> ${data.bb_upper.toFixed(6)}</p>
                        <p><strong>BB Alt:</strong> ${data.bb_lower.toFixed(6)}</p>
                        <p><strong>DC Aralık:</strong> ${data.dc_low.toFixed(6)} - ${data.dc_high.toFixed(6)}</p>
                    </div>
                </div>
                <small class="text-muted">Son güncelleme: ${new Date(data.timestamp).toLocaleString('tr-TR')}</small>
            </div>
        `;
        
        container.innerHTML = html;
    }
}

// ================== GLOBAL FUNCTIONS ==================
function startBot() {
    app.startBot();
}

function stopBot() {
    app.stopBot();
}

function analyzeSymbol() {
    app.analyzeSymbol();
}

// Initialize app
const app = new TradingBotApp();
