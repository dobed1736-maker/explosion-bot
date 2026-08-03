# ============================================================
# FILTROS - EXPLOSION BOT
# ============================================================

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import (
    VOLUMEN_MINIMO_USDT,
    VOLUMEN_RELATIVO_MINIMO,
    ACELERACION_VOLUMEN_MIN,
    TAKER_BUY_RATIO_MIN,
    ORDER_BOOK_IMBALANCE_MIN,
    MOMENTUM_15M_MIN,
    RSI_MINIMO,
    RSI_MAXIMO,
    FUNDING_RATE_MAX,
    RANGO_ENTRADA_MIN,
    RANGO_ENTRADA_MAX,
    EDAD_MAXIMA_HORAS,
    BTC_COMPARACION_MIN,
    HORARIO_INICIO,
    HORARIO_FIN
)

from src.features.indicators import calcular_ultimo_valor


# ============================================================
# FILTROS OBLIGATORIOS (9 filtros críticos)
# ============================================================

def filtrar_volumen(volumen, volumen_minimo=VOLUMEN_MINIMO_USDT):
    """
    Filtro 1: Volumen 24h > mínimo
    """
    pasa = volumen >= volumen_minimo
    return pasa, f"Volumen: ${volumen:,.0f}" if pasa else f"Volumen insuficiente: ${volumen:,.0f} < ${volumen_minimo:,.0f}"


def filtrar_volumen_relativo(df, min_relativo=VOLUMEN_RELATIVO_MINIMO):
    """
    Filtro 2: Volumen relativo > mínimo
    """
    vol_rel = calcular_ultimo_valor(df, 'volumen_relativo')
    pasa = vol_rel >= min_relativo
    return pasa, f"Vol Relativo: {vol_rel:.2f}x" if pasa else f"Vol Relativo bajo: {vol_rel:.2f}x < {min_relativo:.2f}x"


def filtrar_aceleracion_volumen(df, min_aceleracion=ACELERACION_VOLUMEN_MIN):
    """
    Filtro 3: Aceleración de volumen > mínimo
    """
    aceleracion = calcular_ultimo_valor(df, 'volumen_aceleracion')
    pasa = aceleracion >= min_aceleracion
    return pasa, f"Aceleración: {aceleracion:.2%}" if pasa else f"Aceleración baja: {aceleracion:.2%} < {min_aceleracion:.2%}"


def filtrar_taker_buy_ratio(df, min_ratio=TAKER_BUY_RATIO_MIN):
    """
    Filtro 4: Taker Buy Ratio > mínimo
    """
    ratio = calcular_ultimo_valor(df, 'taker_buy_ratio')
    pasa = ratio >= min_ratio
    return pasa, f"Taker Buy: {ratio:.2%}" if pasa else f"Taker Buy bajo: {ratio:.2%} < {min_ratio:.2%}"


def filtrar_order_book_imbalance(book_imbalance, min_imbalance=ORDER_BOOK_IMBALANCE_MIN):
    """
    Filtro 5: Order Book Imbalance > mínimo
    """
    pasa = book_imbalance >= min_imbalance
    return pasa, f"Order Book: {book_imbalance:.2f}x" if pasa else f"Order Book bajo: {book_imbalance:.2f}x < {min_imbalance:.2f}x"


def filtrar_momentum_15m(df, min_momentum=MOMENTUM_15M_MIN):
    """
    Filtro 6: Momentum en 15m > mínimo
    """
    momentum = calcular_ultimo_valor(df, 'retorno_15') * 100
    pasa = momentum >= min_momentum
    return pasa, f"Momentum 15m: {momentum:.2f}%" if pasa else f"Momentum bajo: {momentum:.2f}% < {min_momentum:.2f}%"


def filtrar_rsi(df, min_rsi=RSI_MINIMO, max_rsi=RSI_MAXIMO):
    """
    Filtro 7: RSI en rango neutral-alcista
    """
    rsi = calcular_ultimo_valor(df, 'rsi')
    pasa = min_rsi <= rsi <= max_rsi
    return pasa, f"RSI: {rsi:.2f}" if pasa else f"RSI fuera de rango: {rsi:.2f}"


def filtrar_funding_rate(funding_rate, max_rate=FUNDING_RATE_MAX):
    """
    Filtro 8: Funding Rate < máximo (negativo)
    """
    pasa = funding_rate <= max_rate
    return pasa, f"Funding: {funding_rate:.4f}%" if pasa else f"Funding alto: {funding_rate:.4f}% > {max_rate:.4f}%"


def filtrar_rango_entrada(cambio):
    """
    Filtro 9: La moneda está en rango de entrada (5%-15%)
    """
    pasa = RANGO_ENTRADA_MIN <= cambio <= RANGO_ENTRADA_MAX
    return pasa, f"Cambio: {cambio:.2f}%" if pasa else f"Cambio fuera de rango: {cambio:.2f}%"


# ============================================================
# FILTROS DE PUNTUACIÓN (Dan puntos extras)
# ============================================================

def filtrar_edad_explosion(tiempo_inicio, max_horas=EDAD_MAXIMA_HORAS):
    """
    Filtro 10: Edad de la explosión < máximo
    """
    if tiempo_inicio is None:
        return False, "No se pudo determinar edad"
    
    horas = (datetime.now() - tiempo_inicio).total_seconds() / 3600
    pasa = horas <= max_horas
    return pasa, f"Edad: {horas:.1f}h" if pasa else f"Edad alta: {horas:.1f}h > {max_horas:.1f}h"


def filtrar_comparacion_btc(moneda_cambio, btc_cambio, min_ratio=BTC_COMPARACION_MIN):
    """
    Filtro 11: La moneda supera a BTC en rendimiento
    """
    if btc_cambio == 0:
        ratio = 999
    else:
        ratio = moneda_cambio / btc_cambio
    
    pasa = ratio >= min_ratio
    return pasa, f"Ratio vs BTC: {ratio:.2f}x" if pasa else f"Ratio bajo: {ratio:.2f}x < {min_ratio:.2f}x"


def filtrar_estructura_alcista(df):
    """
    Filtro 12: Máximos y mínimos crecientes (Estructura Alcista)
    """
    max_10 = df['high'].rolling(10).max()
    min_5 = df['low'].rolling(5).min()
    
    # Últimos valores
    max_actual = df['high'].iloc[-1]
    max_anterior = max_10.iloc[-2]
    min_actual = df['low'].iloc[-1]
    min_anterior = min_5.iloc[-2]
    
    # Máximo creciente: el último máximo es mayor que el anterior
    max_creciente = max_actual > max_anterior
    # Mínimo creciente: el último mínimo es mayor que el anterior
    min_creciente = min_actual > min_anterior
    
    pasa = max_creciente and min_creciente
    return pasa, "Estructura Alcista" if pasa else "Sin estructura alcista"


def filtrar_breakout_bb(df):
    """
    Filtro 13: Breakout de Bandas de Bollinger (compresión + ruptura)
    """
    # Ancho de la banda (actual vs media)
    ancho = calcular_ultimo_valor(df, 'bb_ancho')
    media_ancho = df['bb_ancho'].rolling(20).mean().iloc[-1]
    
    # Compresión: el ancho actual es menor que la media
    compresion = ancho < media_ancho * 0.8
    
    # Ruptura: el precio cerró por encima de la banda superior
    precio = df['close'].iloc[-1]
    bb_sup = df['bb_superior'].iloc[-1]
    ruptura = precio > bb_sup
    
    pasa = compresion and ruptura
    return pasa, "Breakout BB" if pasa else "Sin breakout BB"


def filtrar_horario():
    """
    Filtro 14: Horario óptimo (2:00 AM - 8:00 AM UTC-3)
    """
    hora_actual = datetime.now().hour
    pasa = HORARIO_INICIO <= hora_actual <= HORARIO_FIN
    return pasa, f"Horario: {hora_actual}h" if pasa else f"Horario subóptimo: {hora_actual}h"


# ============================================================
# FILTRO MAESTRO (Combina todos los filtros)
# ============================================================

def aplicar_todos_los_filtros(df, symbol, ganador_info, book_imbalance, funding_rate, btc_cambio):
    """
    Aplica todos los filtros a una moneda
    
    Args:
        df: DataFrame con velas e indicadores
        symbol: Símbolo de la moneda
        ganador_info: Dict con info del ganador (cambio, volumen, etc.)
        book_imbalance: Imbalance del order book
        funding_rate: Tasa de financiación
        btc_cambio: Cambio de BTC en 24h
    
    Returns:
        dict: {pasa_todos, puntuacion, detalles, razon}
    """
    
    resultados = {
        'pasa_todos': True,
        'puntuacion': 0,
        'detalles': {},
        'razon': '',
        'max_puntos': 0
    }
    
    # ============================================================
    # FILTROS OBLIGATORIOS (Si falla uno, NO PASA)
    # ============================================================
    
    filtros_obligatorios = [
        ('Volumen', filtrar_volumen, [ganador_info.get('volumen', 0)]),
        ('Volumen Relativo', filtrar_volumen_relativo, [df]),
        ('Aceleración Volumen', filtrar_aceleracion_volumen, [df]),
        ('Taker Buy Ratio', filtrar_taker_buy_ratio, [df]),
        ('Order Book', filtrar_order_book_imbalance, [book_imbalance]),
        ('Momentum 15m', filtrar_momentum_15m, [df]),
        ('RSI', filtrar_rsi, [df]),
        ('Funding Rate', filtrar_funding_rate, [funding_rate]),
        ('Rango Entrada', filtrar_rango_entrada, [ganador_info.get('cambio', 0)]),
    ]
    
    for nombre, filtro, args in filtros_obligatorios:
        pasa, mensaje = filtro(*args)
        resultados['detalles'][nombre] = {'pasa': pasa, 'mensaje': mensaje}
        
        if not pasa:
            resultados['pasa_todos'] = False
            resultados['razon'] = mensaje
            resultados['puntuacion'] = 0
            resultados['max_puntos'] = 0
            return resultados
    
    # ============================================================
    # FILTROS DE PUNTUACIÓN (Dan puntos extras)
    # ============================================================
    
    puntos = 0
    max_puntos = 0
    
    filtros_puntuacion = [
        ('Estructura Alcista', filtrar_estructura_alcista, [df], 15),
        ('Breakout BB', filtrar_breakout_bb, [df], 15),
        ('Comparación BTC', filtrar_comparacion_btc, [ganador_info.get('cambio', 0), btc_cambio], 10),
        ('Horario', filtrar_horario, [], 5),
    ]
    
    for nombre, filtro, args, peso in filtros_puntuacion:
        max_puntos += peso
        pasa, mensaje = filtro(*args) if args else filtro()
        resultados['detalles'][nombre] = {'pasa': pasa, 'mensaje': mensaje}
        
        if pasa:
            puntos += peso
    
    resultados['puntuacion'] = puntos
    resultados['max_puntos'] = max_puntos
    
    return resultados


def resumen_filtros(resultados):
    """
    Genera un resumen legible de los filtros
    """
    if resultados['pasa_todos']:
        estado = "✅ PASA TODOS LOS FILTROS"
    else:
        estado = f"❌ NO PASA: {resultados['razon']}"
    
    resumen = f"\n{estado}"
    resumen += f"\n   Puntuación: {resultados['puntuacion']}/{resultados['max_puntos']}"
    
    for nombre, detalle in resultados['detalles'].items():
        icono = "✅" if detalle['pasa'] else "❌"
        resumen += f"\n   {icono} {nombre}: {detalle['mensaje']}"
    
    return resumen


# ============================================================
# PRUEBA RÁPIDA
# ============================================================

if __name__ == "__main__":
    print("🧪 Probando filtros...")
    
    # Crear datos de prueba
    np.random.seed(42)
    df = pd.DataFrame({
        'close': 100 + np.cumsum(np.random.randn(50) * 0.5),
        'high': 100 + np.cumsum(np.random.randn(50) * 0.5) + 0.5,
        'low': 100 + np.cumsum(np.random.randn(50) * 0.5) - 0.5,
        'volume': np.random.randint(1000, 10000, 50),
        'taker_buy_base_asset_volume': np.random.randint(500, 5000, 50)
    })
    
    from src.features.indicators import calcular_todos_indicadores
    df = calcular_todos_indicadores(df)
    
    # Simular info de ganador
    ganador_info = {
        'symbol': 'TESTUSDT',
        'cambio': 8.5,
        'volumen': 2000000,
        'precio': 105.0
    }
    
    # Simular otros datos
    book_imbalance = 1.5
    funding_rate = -0.02
    btc_cambio = 2.0
    
    # Aplicar filtros
    resultado = aplicar_todos_los_filtros(df, 'TESTUSDT', ganador_info, book_imbalance, funding_rate, btc_cambio)
    
    print(resumen_filtros(resultado))
    
    print("\n✅ Prueba completada")