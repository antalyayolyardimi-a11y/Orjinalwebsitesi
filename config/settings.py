# ================== TRADING BOT CONFIGURATION ==================
"""
Trading bot ayarları - Tüm parametreler tek bir yerden yönetiliyor
"""

# ================== TELEGRAM TOKEN ==================
TELEGRAM_TOKEN = "7571593882:AAGLDc09Cw1BulQZqM4ab8N2JGb6FXFe2UQ"

# ================== TIMEFRAMES ==================
TF_LTF = "15min"              # Lower timeframe
TF_HTF = "1hour"              # Higher timeframe
LOOKBACK_LTF = 320            # LTF veri sayısı
LOOKBACK_HTF = 180            # HTF veri sayısı

# ================== TARAMA AYARLARI ==================
SLEEP_SECONDS = 300           # 5 dakikada bir tarama
SYMBOL_CONCURRENCY = 8        # Eşzamanlı sembol sayısı
SCAN_LIMIT = 260             # Maksimum tarama sayısı

# ================== MOD AYARLARI (base - balanced+) ==================
MIN_VOLVALUE_USDT = 2_000_000
BASE_MIN_SCORE = 68
FALLBACK_MIN_SCORE = 62
TOP_N_PER_SCAN = 2
COOLDOWN_SEC = 1800
OPPOSITE_MIN_BARS = 2

# ================== TEKNIK ANALİZ AYARLARI ==================
ADX_TREND_MIN = 18
ONEH_DISP_BODY_MIN = 0.55
ONEH_DISP_LOOKBACK = 2

BB_PERIOD = 20
BB_K = 2.0
BWIDTH_RANGE = 0.055
DONCHIAN_WIN = 20
BREAK_BUFFER = 0.0008
RETEST_TOL_ATR = 0.25

# ================== SMC AYARLARI ==================
SWING_LEFT = 2
SWING_RIGHT = 2
SWEEP_EPS = 0.0005
BOS_EPS = 0.0005
FVG_LOOKBACK = 20
OTE_LOW, OTE_HIGH = 0.62, 0.79
SMC_REQUIRE_FVG = True

# ================== RISK YÖNETİMİ ==================
ATR_PERIOD = 14
SWING_WIN = 10
MAX_SL_ATRx = 2.0
MIN_SL_ATRx = 0.30
TPS_R = (1.0, 1.6, 2.2)        # TP seviyeleri (R multipliers)

# ===== ATR+R risk ayarları =====
USE_ATR_R_RISK = True           # SL/TP swing yerine ATR+R kullan
ATR_STOP_MULT = 1.2             # ATR çarpanı

# ===== Momentum onay ayarları =====
MOMO_CONFIRM_MODE = "hybrid"    # "off", "strict3", "2of3", "net_body", "ema_rv", "hybrid"
MOMO_BODY_MIN = 0.50           # gövde/oran tabanı
MOMO_REL_VOL = 1.35            # relatif hacim eşiği
MOMO_NET_BODY_TH = 0.80        # net gövde eşiği

# ===== Erken tetikleyici (pre-break) =====
EARLY_TRIGGERS_ON = True        # erken sinyal aç/kapat
PREBREAK_ATR_X = 0.25          # Donchian kırılımına ATR*0.25 kadar yaklaşınca tetikle
EARLY_MOMO_BODY_MIN = 0.45     # erken modda gövde/menzil eşiği
EARLY_REL_VOL = 1.20           # erken modda relatif hacim eşiği
EARLY_ADX_BONUS = 2.0          # 1H ADX trend bölgesindeyse küçük skor bonusu

# ================== FALLBACK AYARLARI ==================
FALLBACK_ENABLE = False
FBB_EPS = 0.0003
FBB_ATR_MIN = 0.0010
FBB_ATR_MAX = 0.028

# ================== PERFORMANS TESPİT AYARLARI ==================
EVAL_BARS_AHEAD = 12
ADAPT_MIN_SAMPLES = 20
ADAPT_WINDOW = 60
ADAPT_UP_THRESH = 0.55
ADAPT_DN_THRESH = 0.35
ADAPT_STEP = 2
MIN_SCORE_FLOOR = 58
MIN_SCORE_CEIL = 78

# ================== LOG AYARLARI ==================
PRINT_PREFIX = "📟"
VERBOSE_SCAN = True
SHOW_SYMBOL_LIST_AT_START = True
SHOW_SKIP_REASONS = True
CHUNK_PRINT = 20

# ================== SCORING WEIGHTS ==================
SCORING_WEIGHTS = {
    "htf_align": 18.0,
    "adx_norm": 14.0,
    "ltf_momo": 10.0,
    "rr_norm": 0.0,              # RR puanı devre dışı (manuel SL yönetimi)
    "bw_adv": 5.0,
    "retest_or_fvg": 8.0,
    "atr_sweet": 3.0,
    "vol_pct": 8.0,
    "recent_penalty": -3.0,
}
SCORING_BASE = 20.0
PROB_CALIB_A = 0.10
PROB_CALIB_B = -7.0

# ===== SELF-LEARN / AUTO-TUNER =====
AUTO_TUNER_ON = True
WR_TARGET = 0.52               # hedef başarı oranı
WIN_MIN_SAMPLES = 20
TUNE_WINDOW = 80
TUNE_COOLDOWN_SEC = 900

# Sınır korumaları
BOUNDS = {
    "BASE_MIN_SCORE": (56, 80),
    "ADX_TREND_MIN": (12, 26),
    "BWIDTH_RANGE": (0.045, 0.090),
    "VOL_MULT_REQ": (1.10, 1.80),
}

# ================== AI AYARLARI ==================
AI_ENABLED = True
AI_LR = 0.02
AI_L2 = 1e-4
AI_INIT_BIAS = -2.0

# ================== MOD AYARLARI ==================
MODE_CONFIGS = {
    "aggressive": {
        "MIN_VOLVALUE_USDT": 700_000,
        "BASE_MIN_SCORE": 52,
        "FALLBACK_MIN_SCORE": 55,
        "TOP_N_PER_SCAN": 5,
        "COOLDOWN_SEC": 900,
        "ADX_TREND_MIN": 14,
        "ONEH_DISP_BODY_MIN": 0.45,
        "BWIDTH_RANGE": 0.080,
        "BREAK_BUFFER": 0.0006,
        "RETEST_TOL_ATR": 0.50,
        "SMC_REQUIRE_FVG": False,
        "FBB_ATR_MIN": 0.0007,
        "FBB_ATR_MAX": 0.030,
        "FALLBACK_ENABLE": False,
        "ATR_STOP_MULT": 1.0
    },
    "balanced": {
        "MIN_VOLVALUE_USDT": 2_000_000,
        "BASE_MIN_SCORE": 68,
        "FALLBACK_MIN_SCORE": 62,
        "TOP_N_PER_SCAN": 2,
        "COOLDOWN_SEC": 1800,
        "ADX_TREND_MIN": 18,
        "ONEH_DISP_BODY_MIN": 0.55,
        "BWIDTH_RANGE": 0.055,
        "BREAK_BUFFER": 0.0008,
        "RETEST_TOL_ATR": 0.25,
        "SMC_REQUIRE_FVG": True,
        "FBB_ATR_MIN": 0.0010,
        "FBB_ATR_MAX": 0.028,
        "FALLBACK_ENABLE": False,
        "ATR_STOP_MULT": 1.2
    },
    "conservative": {
        "MIN_VOLVALUE_USDT": 3_000_000,
        "BASE_MIN_SCORE": 72,
        "FALLBACK_MIN_SCORE": 65,
        "TOP_N_PER_SCAN": 2,
        "COOLDOWN_SEC": 2400,
        "ADX_TREND_MIN": 20,
        "ONEH_DISP_BODY_MIN": 0.60,
        "BWIDTH_RANGE": 0.045,
        "BREAK_BUFFER": 0.0012,
        "RETEST_TOL_ATR": 0.20,
        "SMC_REQUIRE_FVG": True,
        "FBB_ATR_MIN": 0.0012,
        "FBB_ATR_MAX": 0.020,
        "FALLBACK_ENABLE": False,
        "ATR_STOP_MULT": 1.5
    }
}

# ================== RANGE AYARLARI ==================
VOL_MULT_REQ_GLOBAL = 1.40
RSI_LONG_TH = 36
RSI_SHORT_TH = 64

# Adaptif gevşetme (sinyal çıkmayan turlarda)
EMPTY_LIMIT = 3
RELAX_STEP = 2
RELAX_MAX = 6

# Penalty decay
PENALTY_DECAY = 2

# Known quote currencies for symbol normalization
KNOWN_QUOTES = ["USDT", "USDC", "BTC", "ETH", "TUSD", "EUR", "KCS"]
