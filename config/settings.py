# ============================================================
# CONFIGURACIÓN DEL BOT - EXPLOSION BOT
# ============================================================
# config/settings.py
from binance.client import Client
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')

BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')
BINANCE_TESTNET = os.getenv('BINANCE_TESTNET', 'False').lower() in ('true', '1', 't')

# ============================================================
# 🔥 CONFIGURACIÓN DE PROXY DESDE .ENV
# ============================================================
PROXY_USER = os.getenv('PROXY_USER')
PROXY_PASS = os.getenv('PROXY_PASS')
PROXY_IP = os.getenv('PROXY_IP')
PROXY_PORT = os.getenv('PROXY_PORT')

if PROXY_IP and PROXY_PORT:
    if PROXY_USER and PROXY_PASS:
        PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_IP}:{PROXY_PORT}"
    else:
        PROXY_URL = f"http://{PROXY_IP}:{PROXY_PORT}"
        
    PROXY_CONFIG = {
        'http': PROXY_URL,
        'https': PROXY_URL
    }
else:
    PROXY_CONFIG = None

# ============================================================
# MONEDAS Y ESCANEO
# ============================================================
TOP_A_ESCANEAR = 50              # Número de ganadores a escanear
RANGO_ENTRADA_MIN = 3.0          # % mínimo de subida para considerar (3.0%)
RANGO_ENTRADA_MAX = 50.0         # % máximo para permitir agarrar bombas avanzadas
TIMEFRAME = '5m'                 # Timeframe para análisis
HORAS_SUBIDA_MAX = 12            # Edad máxima de la explosión en horas

# ============================================================
# FILTROS FLEXIBILIZADOS (CAZADOR DE EXPLOSIONES)
# ============================================================
VOLUMEN_MINIMO_USDT = 500000    # $500K mínimo
VOLUMEN_RELATIVO_MINIMO = 1.3    # 1.3x su media
ACELERACION_VOLUMEN_MIN = 0.3    # 30% de aceleración
TAKER_BUY_RATIO_MIN = 0.50       # 50% de compras
ORDER_BOOK_IMBALANCE_MIN = 1.1   # 10% más compras que ventas
MOMENTUM_15M_MIN = 0.8           # 0.8% de subida en 15m
RSI_MINIMO = 40                  # Solo filtra si está extremadamente colapsado (<40)
RSI_MAXIMO = 95                  # Permite entrar en sobrecompra alta si hay volumen
FUNDING_RATE_MAX = 0.05          # Permite entrar independientemente del funding

# ============================================================
# FILTROS DE PUNTUACIÓN (Dan puntos extras)
# ============================================================
LIQUIDEZ_MINIMA_PROFUNDIDAD = 3   # 3x el tamaño de mi posición
EDAD_MAXIMA_HORAS = 12           # Menos de 12 horas de subida
BTC_COMPARACION_MIN = 1.2        # Supera a BTC en 1.2x
HORARIO_INICIO = 0               # 24/7 (inicio)
HORARIO_FIN = 23                 # 24/7 (fin)

# ============================================================
# MODELOS (Pesos para la señal final)
# ============================================================
# ============================================================
# MODELOS (Pesos para la señal final)
# ============================================================
# ==============================================================================
# MODELOS (Pesos para la señal final)
# ==============================================================================
PESO_XGBOOST = 0.20
PESO_LSTM = 0.50
PESO_STATSMODELS = 0.30
UMBRAL_COMPRA = 0.60         # Bajamos de 0.70 a 0.55 para aprobar las señales          # 65% de confianza para comprar

# ============================================================
# GESTIÓN DE RIESGO Y TAKE PROFIT
# ============================================================
CAPITAL_INICIAL = 10000          # Capital de prueba
RIESGO_POR_OPERACION = 0.02      # 2% por operación
RIESGO_POR_OPERACION_VOLATIL = 0.01  # 1% si ATR > 5%
MAX_OPERACIONES_SIMULTANEAS = 2
ATR_PERIODO = 14

# Stop Loss y Take Profit (múltiplos de ATR)
SL_ATR = 1.5
TP1_ATR = 2.5
TP2_ATR = 4.5
TP3_ATR = 7.0

# Porcentajes de cierre en cada TP
TP1_CIERRE = 0.30   # 30%
TP2_CIERRE = 0.30   # 30%
TP3_CIERRE = 0.40   # 40%

# Trailing Stop progresivo
TRAILING_ACTIVAR_EN = 0.01       # 1% de ganancia para activar
TRAILING_STEP_1 = 0.005          # 0.5% (Break Even)
TRAILING_STEP_2 = 0.02           # 2%
TRAILING_STEP_3 = 0.05           # 5%
TRAILING_STEP_4 = 0.10           # 10%

# Salida por falta de momentum
MOMENTUM_SALIDA_VELAS = 3        # 3 velas sin nuevo máximo

# ============================================================
# EJECUCIÓN
# ============================================================
INTERVALO_EJECUCION = 300        # 5 minutos (en segundos)
INTERVALO_ESCANEO = 300          # 5 minutos (en segundos)

# ============================================================
# TELEGRAM
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# ============================================================
# TARGET DEL MODELO (Para ML)
# ============================================================
TARGET_UMBRAL = 0.05            # 5% de subida para considerar explosión
TARGET_VENTANA = 12             # 12 velas de 5m = 1 hora