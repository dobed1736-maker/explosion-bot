# ============================================================
# CONFIGURACIÓN DEL BOT - EXPLOSION BOT
# ============================================================
# config/settings.py - VERSIÓN MODIFICADA
from binance.client import Client
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')

# ============================================================
# 🔥 AGREGAS ESTO PARA EL PROXY
# ============================================================
# Configuración del proxy (usa uno de la lista)
PROXY_CONFIG = {
    'http': 'http://212.113.104.29:10801',   # Alemania
    'https': 'https://212.113.104.29:10801'
}

# ============================================================
# 🔥 MODIFICAS EL CLIENTE
# ============================================================
# ANTES:
# client = Client(API_KEY, API_SECRET)

# DESPUÉS:
client = Client(
    API_KEY, 
    API_SECRET,
    requests_params={
        'proxies': PROXY_CONFIG,
        'timeout': 30  # Para que no se cuelgue
    }
)

print("✅ Cliente Binance inicializado con proxy")

# ============================================================
# MONEDAS Y ESCANEO
# ============================================================
TOP_A_ESCANEAR = 50              # Número de ganadores a escanear
RANGO_ENTRADA_MIN = 5.0          # % mínimo de subida para considerar (5%)
RANGO_ENTRADA_MAX = 15.0         # % máximo de subida para considerar (15%)
TIMEFRAME = '5m'                 # Timeframe para análisis
HORAS_SUBIDA_MAX = 6             # Edad máxima de la explosión

# ============================================================
# FILTROS OBLIGATORIOS (Si falla uno, se descarta)
# ============================================================
VOLUMEN_MINIMO_USDT = 1000000    # $1M mínimo
VOLUMEN_RELATIVO_MINIMO = 1.5    # 1.5x su media
ACELERACION_VOLUMEN_MIN = 0.5    # 50% de aceleración
TAKER_BUY_RATIO_MIN = 0.55       # 55% de compras
ORDER_BOOK_IMBALANCE_MIN = 1.2   # 20% más compras que ventas
MOMENTUM_15M_MIN = 1.0           # 1% de subida en 15m
RSI_MINIMO = 40
RSI_MAXIMO = 65
FUNDING_RATE_MAX = -0.01         # -0.01% o más negativo

# ============================================================
# FILTROS DE PUNTUACIÓN (Dan puntos extras)
# ============================================================
LIQUIDEZ_MINIMA_PROFUNDIDAD = 3   # 3x el tamaño de mi posición
EDAD_MAXIMA_HORAS = 6            # Menos de 6 horas de subida
BTC_COMPARACION_MIN = 1.5        # Supera a BTC en 1.5x
HORARIO_INICIO = 2               # 2:00 AM (UTC-3)
HORARIO_FIN = 8                  # 8:00 AM (UTC-3)

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