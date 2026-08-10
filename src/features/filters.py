# ============================================================
# FILTROS - EXPLOSION BOT (VERSIÓN CAZADOR DE EXPLOSIONES)
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
# FILTROS BASE INDIVIDUALES
# ============================================================

def filtrar_volumen(volumen, volumen_minimo=VOLUMEN_MINIMO_USDT):
    pasa = volumen >= volumen_minimo
    return pasa, f"Volumen: ${volumen:,.0f}" if pasa else f"Volumen insuficiente: ${volumen:,.0f} < ${volumen_minimo:,.0f}"


def filtrar_volumen_relativo(df, min_relativo=VOLUMEN_RELATIVO_MINIMO):
    vol_rel = calcular_ultimo_valor(df, 'volumen_relativo')
    pasa = vol_rel >= min_relativo
    return pasa, f"Vol Relativo: {vol_rel:.2f}x" if pasa else f"Vol Relativo bajo: {vol_rel:.2f}x < {min_relativo:.2f}x"


def filtrar_momentum_15m(df, min_momentum=MOMENTUM_15M_MIN):
    momentum = calcular_ultimo_valor(df, 'retorno_15') * 100
    pasa = momentum >= min_momentum
    return pasa, f"Momentum 15m: {momentum:.2f}%" if pasa else f"Momentum bajo: {momentum:.2f}% < {min_momentum:.2f}%"


def filtrar_rango_entrada(cambio):
    pasa = cambio >= RANGO_ENTRADA_MIN  # Se quitó el techo rígido de MAX
    return pasa, f"Cambio: {cambio:.2f}%" if pasa else f"Cambio bajo: {cambio:.2f}% < {RANGO_ENTRADA_MIN}%"


def filtrar_taker_buy_ratio(df, min_ratio=TAKER_BUY_RATIO_MIN):
    ratio = calcular_ultimo_valor(df, 'taker_buy_ratio')
    pasa = ratio >= min_ratio
    return pasa, f"Taker Buy: {ratio:.2%}" if pasa else f"Taker Buy bajo: {ratio:.2%}"


def filtrar_rsi_flexible(df, min_rsi=RSI_MINIMO):
    """RSI solo verifica que no esté totalmente muerto (< 40)"""
    rsi = calcular_ultimo_valor(df, 'rsi')
    pasa = rsi >= min_rsi
    return pasa, f"RSI: {rsi:.2f}" if pasa else f"RSI colapsado: {rsi:.2f}"


def filtrar_estructura_alcista(df):
    """Verifica si el precio está sobre la EMA principal"""
    precio = df['close'].iloc[-1]
    ema = calcular_ultimo_valor(df, 'ema_20') if 'ema_20' in df.columns else df['close'].rolling(20).mean().iloc[-1]
    pasa = precio >= ema
    return pasa, "Precio > EMA" if pasa else "Precio < EMA"


# ============================================================
# FILTRO MAESTRO OPTIMIZADO (4-5 Filtros Críticos)
# ============================================================

def aplicar_todos_los_filtros(df, symbol, ganador_info, book_imbalance, funding_rate, btc_cambio):
    """
    Aplica únicamente los filtros esenciales para no asfixiar el bot.
    """
    
    resultados = {
        'pasa_todos': True,
        'puntuacion': 0,
        'detalles': {},
        'razon': '',
        'max_puntos': 0
    }
    
    # ============================================================
    # 🎯 5 FILTROS OBLIGATORIOS (Los pesos pesados)
    # ============================================================
    
    filtros_obligatorios = [
        ('Volumen 24h', filtrar_volumen, [ganador_info.get('volumen', 0)]),
        ('Volumen Relativo', filtrar_volumen_relativo, [df]),
        ('Momentum 15m', filtrar_momentum_15m, [df]),
        ('Suelo RSI', filtrar_rsi_flexible, [df]),
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
    # ⭐ FILTROS DE PUNTUACIÓN OPTIONALES (Para bonus de confianza)
    # ============================================================
    
    puntos = 0
    max_puntos = 0
    
    filtros_puntuacion = [
        ('Precio > EMA', filtrar_estructura_alcista, [df], 25),
        ('Taker Buy Ratio', filtrar_taker_buy_ratio, [df], 25),
    ]
    
    for nombre, filtro, args, peso in filtros_puntuacion:
        max_puntos += peso
        pasa, mensaje = filtro(*args)
        resultados['detalles'][nombre] = {'pasa': pasa, 'mensaje': mensaje}
        
        if pasa:
            puntos += peso
    
    resultados['puntuacion'] = puntos
    resultados['max_puntos'] = max_puntos
    
    return resultados


def resumen_filtros(resultados):
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
# CONECTOR PARA MAIN.PY
# ============================================================

def pasar_filtros(df, symbol=""):
    """
    Evaluación rápida de un dataframe individual para verificar
    si cumple con la estructura mínima para pasar al modelo.
    """
    if df is None or df.empty or len(df) < 30:
        return False
    return True


def obtener_candidatos(datos_monedas, df_btc=None):
    """
    Recorre el diccionario de monedas analizadas en main.py
    y devuelve la lista de candidatas que pasan la evaluación de filtros.
    """
    candidatos = []
    
    # Calcular cambio de BTC si está disponible
    btc_cambio = 0.0
    if df_btc is not None and not df_btc.empty:
        btc_cambio = ((df_btc['close'].iloc[-1] - df_btc['close'].iloc[0]) / df_btc['close'].iloc[0]) * 100

    for symbol, df in datos_monedas.items():
        if df is None or df.empty:
            continue
            
        # Preparar datos mínimos para aplicar_todos_los_filtros
        precio_actual = df['close'].iloc[-1]
        precio_inicio = df['close'].iloc[0]
        cambio_pct = ((precio_actual - precio_inicio) / precio_inicio) * 100 if precio_inicio > 0 else 0
        volumen_total = df['volume'].sum() * precio_actual
        
        ganador_info = {
            'volumen': volumen_total,
            'cambio': cambio_pct
        }
        
        # Ejecutar tu filtro maestro de 5 capas
        res = aplicar_todos_los_filtros(
            df=df,
            symbol=symbol,
            ganador_info=ganador_info,
            book_imbalance=0.0,
            funding_rate=0.0,
            btc_cambio=btc_cambio
        )
        
        if res['pasa_todos']:
            candidatos.append({
                'symbol': symbol,
                'df': df,
                'puntuacion': res['puntuacion']
            })
            
    return candidatos