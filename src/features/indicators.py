# ============================================================
# INDICADORES TÉCNICOS - EXPLOSION BOT
# ============================================================

import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import ATR_PERIODO

def calcular_rsi(df, periodo=14):
    """
    Calcula el RSI (Relative Strength Index)
    
    Args:
        df: DataFrame con columna 'close'
        periodo: Período para el cálculo (default: 14)
    
    Returns:
        Serie con el RSI
    """
    delta = df['close'].diff()
    ganancia = (delta.where(delta > 0, 0)).rolling(window=periodo).mean()
    perdida = (-delta.where(delta < 0, 0)).rolling(window=periodo).mean()
    
    # Evitar división por cero
    perdida = perdida.replace(0, np.nan)
    rs = ganancia / perdida
    rsi = 100 - (100 / (1 + rs))
    
    # Rellenar NaN con 50 (zona neutral)
    rsi = rsi.fillna(50)
    
    return rsi

def calcular_atr(df, periodo=14):
    """
    Calcula el ATR (Average True Range)
    
    Args:
        df: DataFrame con columnas 'high', 'low', 'close'
        periodo: Período para el cálculo (default: 14)
    
    Returns:
        Serie con el ATR
    """
    high = df['high']
    low = df['low']
    close = df['close'].shift(1)
    
    tr1 = high - low
    tr2 = (high - close).abs()
    tr3 = (low - close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=periodo).mean()
    
    return atr

def calcular_macd(df, fast=12, slow=26, signal=9):
    """
    Calcula el MACD (Moving Average Convergence Divergence)
    
    Args:
        df: DataFrame con columna 'close'
        fast: EMA rápida (default: 12)
        slow: EMA lenta (default: 26)
        signal: EMA de señal (default: 9)
    
    Returns:
        tuple: (macd_line, signal_line, histogram)
    """
    exp_fast = df['close'].ewm(span=fast, adjust=False).mean()
    exp_slow = df['close'].ewm(span=slow, adjust=False).mean()
    
    macd_line = exp_fast - exp_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram

def calcular_bb(df, periodo=20, desviaciones=2):
    """
    Calcula las Bandas de Bollinger
    
    Args:
        df: DataFrame con columna 'close'
        periodo: Período para la media móvil (default: 20)
        desviaciones: Número de desviaciones (default: 2)
    
    Returns:
        tuple: (superior, inferior, ancho, %B)
    """
    media = df['close'].rolling(window=periodo).mean()
    std = df['close'].rolling(window=periodo).std()
    
    bb_superior = media + (std * desviaciones)
    bb_inferior = media - (std * desviaciones)
    bb_ancho = (bb_superior - bb_inferior) / media
    bb_porcentaje = (df['close'] - bb_inferior) / (bb_superior - bb_inferior)
    
    return bb_superior, bb_inferior, bb_ancho, bb_porcentaje

def calcular_ema(df, periodos=[9, 21, 50]):
    """
    Calcula EMAs para múltiples periodos
    
    Args:
        df: DataFrame con columna 'close'
        periodos: Lista de periodos para EMA
    
    Returns:
        dict: {periodo: serie_ema}
    """
    emas = {}
    for p in periodos:
        emas[f'ema_{p}'] = df['close'].ewm(span=p, adjust=False).mean()
    
    return emas

def calcular_volumen_relativo(df, periodo=20):
    """
    Calcula el volumen relativo (actual vs media)
    
    Args:
        df: DataFrame con columna 'volume'
        periodo: Período para la media (default: 20)
    
    Returns:
        Serie con el volumen relativo
    """
    media_volumen = df['volume'].rolling(window=periodo).mean()
    volumen_relativo = df['volume'] / media_volumen
    
    return volumen_relativo

def calcular_volumen_aceleracion(df, ventanas=[1, 3]):
    """
    Calcula la aceleración del volumen
    
    Args:
        df: DataFrame con columna 'volume'
        ventanas: [actual, hace_n] para comparar
    
    Returns:
        Serie con la aceleración
    """
    vol_actual = df['volume']
    vol_pasado = df['volume'].shift(ventanas[1])
    
    aceleracion = (vol_actual - vol_pasado) / vol_pasado
    aceleracion = aceleracion.replace([np.inf, -np.inf], 0).fillna(0)
    
    return aceleracion

def calcular_taker_buy_ratio(df):
    """
    Calcula el ratio de compras de taker (Taker Buy Ratio)
    
    Args:
        df: DataFrame con columna 'taker_buy_base_asset_volume'
    
    Returns:
        Serie con el ratio
    """
    total_volume = df['volume']
    taker_buy = df['taker_buy_base_asset_volume']
    
    ratio = taker_buy / total_volume
    ratio = ratio.replace([np.inf, -np.inf], 0).fillna(0.5)
    
    return ratio

def calcular_rango(df):
    """
    Calcula el rango de precio (high - low) / close
    """
    rango = (df['high'] - df['low']) / df['close']
    return rango

def calcular_todos_indicadores(df):
    """
    Calcula TODOS los indicadores de una vez
    
    Args:
        df: DataFrame con columnas OHLCV + taker_buy
    
    Returns:
        DataFrame con los indicadores añadidos
    """
    df = df.copy()
    
    # RSI
    df['rsi'] = calcular_rsi(df, 14)
    
    # ATR
    df['atr'] = calcular_atr(df, 14)
    
    # MACD
    df['macd'], df['macd_signal'], df['macd_hist'] = calcular_macd(df)
    
    # Bandas de Bollinger
    df['bb_superior'], df['bb_inferior'], df['bb_ancho'], df['bb_porcentaje'] = calcular_bb(df, 20, 2)
    
    # EMAs
    emas = calcular_ema(df, [9, 21, 50])
    for key, value in emas.items():
        df[key] = value
    
    # Volumen relativo
    df['volumen_relativo'] = calcular_volumen_relativo(df, 20)
    
    # Aceleración de volumen
    df['volumen_aceleracion'] = calcular_volumen_aceleracion(df, [1, 3])
    
    # Taker Buy Ratio
    df['taker_buy_ratio'] = calcular_taker_buy_ratio(df)
    
    # Retornos
    df['retorno_1'] = df['close'].pct_change()
    df['retorno_5'] = df['close'].pct_change(periods=5)
    df['retorno_10'] = df['close'].pct_change(periods=10)
    df['retorno_15'] = df['close'].pct_change(periods=15)
    
    # Rango
    df['rango'] = calcular_rango(df)
    
    # ATR% (volatilidad relativa)
    df['atr_porcentaje'] = (df['atr'] / df['close']) * 100
    
    return df

def calcular_ultimo_valor(df, columna):
    """
    Obtiene el último valor de una columna, manejando NaN
    """
    valor = df[columna].iloc[-1]
    if pd.isna(valor) or np.isinf(valor):
        return 0
    return valor


if __name__ == "__main__":
    # Prueba rápida
    print("🧪 Probando indicadores...")
    
    # Crear datos de prueba
    np.random.seed(42)
    datos = pd.DataFrame({
        'close': 100 + np.cumsum(np.random.randn(100) * 0.5),
        'high': 100 + np.cumsum(np.random.randn(100) * 0.5) + 0.5,
        'low': 100 + np.cumsum(np.random.randn(100) * 0.5) - 0.5,
        'volume': np.random.randint(1000, 10000, 100),
        'taker_buy_base_asset_volume': np.random.randint(500, 5000, 100)
    })
    
    df = calcular_todos_indicadores(datos)
    print("✅ Indicadores calculados:", df.columns.tolist())