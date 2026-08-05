# ============================================================
# CONFIGURACIÓN DEL BOT - EXPLOSION BOT
# ============================================================
# config/settings.py - VERSIÓN OPTIMIZADA
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
RANGO_ENTRADA_MIN = 3.0          # Capturar desde el +3% de subida inicial
RANGO_ENTRADA_MAX = 50.0         # Permitir bombas en desarrollo
TIMEFRAME = '5m'                 # Timeframe para análisis
HORAS_SUBIDA_MAX = 6             # Edad máxima de la explosión

# ============================================================
# FILTROS OBLIGATORIOS Y BÁSICOS (Ajustados para no asfixiar)
# ============================================================
VOLUMEN_MINIMO_USDT = 500000      # $500k mínimo (más flexible)
VOLUMEN_RELATIVO_MINIMO = 1.3    # 1.3x su media
ACELERACION_VOLUMEN_MIN = 0.3    # 30% de aceleración
TAKER_BUY_RATIO_MIN = 0.50       # 50% de compras
ORDER_BOOK_IMBALANCE_MIN = 1.1   # 10% más compras que ventas
MOMENTUM_15M_MIN = 0.8           # 0.8% de subida en 15m
RSI_MINIMO = 40                  # Solo descarta si está colapsado por debajo de 40
RSI_MAXIMO = 95                  # Permite entrar en impulsos fuertes
FUNDING_RATE_MAX = 0.05          # Permite funding normal/positivo moderado

# ============================================================
# FILTROS DE PUNTUACIÓN (Dan puntos extras)
# ============================================================
LIQUIDEZ_MINIMA_PROFUNDIDAD = 3   # 3x el tamaño de mi posición
EDAD_MAXIMA_HORAS = 6            # Menos de 6 horas de subida
BTC_COMPARACION_MIN = 1.2        # Supera a BTC en 1.2x
HORARIO_INICIO = 0               # Sin restricción rígida de hora (0-24)
HORARIO_FIN = 24

# ============================================================
# MODELOS (Pesos para la señal final)
# ============================================================
PESO_XGBOOST = 0.60
PESO_LSTM = 0.30
PESO_STATSMODELS = 0.10
UMBRAL_COMPRA = 0.70             # 70% de confianza para comprar

# ============================================================
# GESTIÓN DE RIESGO
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
# ============================================================
# EJECUCIÓN
# ============================================================
INTERVALO_EJECUCION = 300        # 5 minutos (en segundos)
INTERVALO_ESCANEO = 300          # Por si main.py la busca con este nombre