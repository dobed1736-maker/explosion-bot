# ============================================================
# GENERADOR DE SEÑALES - EXPLOSION BOT
# ============================================================

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import (
    PESO_XGBOOST,
    PESO_LSTM,
    PESO_STATSMODELS,
    UMBRAL_COMPRA,
    CAPITAL_INICIAL,
    RIESGO_POR_OPERACION,
    SL_ATR,
    TP1_ATR,
    TP2_ATR,
    TP3_ATR,
    TP1_CIERRE,
    TP2_CIERRE,
    TP3_CIERRE
)


class GeneradorSenales:
    """
    Genera señales de trading combinando XGBoost, LSTM y Statsmodels
    """
    
    def __init__(self, modelo_xgb=None, modelo_lstm=None, modelo_regimen=None):
        self.modelo_xgb = modelo_xgb
        self.modelo_lstm = modelo_lstm
        self.modelo_regimen = modelo_regimen
        self.ultima_senal = None
    
    def calcular_puntuacion(self, df, modelo_override=None):
        """
        Calcula la puntuación combinada de todos los modelos
        """
        resultados = {
            'xgb': 0.5,
            'lstm': 0.5,
            'regimen': 0.5,
            'ponderada': 0.5,
            'detalles': {}
        }
        
        # Asignar modelo si viene por parámetro
        xgb_model = modelo_override if modelo_override is not None else self.modelo_xgb
        
        # 1. XGBoost
        if xgb_model is not None:
            try:
                # Intenta llamar predecir_probabilidad o predecir_ultima según lo tenga el modelo
                if hasattr(xgb_model, 'predecir_probabilidad'):
                    prob_xgb = xgb_model.predecir_probabilidad(df)
                elif hasattr(xgb_model, 'predecir_ultima'):
                    prob_xgb = xgb_model.predecir_ultima(df)
                else:
                    prob_xgb = None

                if prob_xgb is not None:
                    resultados['xgb'] = float(prob_xgb)
                    resultados['detalles']['XGBoost'] = f"{resultados['xgb']:.2%}"
            except Exception as e:
                print(f"⚠️ Error al predecir en XGBoost: {e}")
        
        # 2. LSTM
        if self.modelo_lstm is not None:
            try:
                prob_lstm = self.modelo_lstm.predecir(df)
                if prob_lstm is not None:
                    resultados['lstm'] = float(prob_lstm)
                    resultados['detalles']['LSTM'] = f"{resultados['lstm']:.2%}"
            except Exception as e:
                print(f"⚠️ Error al predecir en LSTM: {e}")
        
        # 3. Statsmodels (régimen)
        if self.modelo_regimen is not None:
            try:
                regimen = self.modelo_regimen.analizar_regimen(df)
                if 'ALCISTA' in regimen.get('regimen', ''):
                    resultados['regimen'] = 0.7 + (0.2 * regimen.get('confianza', 0.5))
                elif 'BAJISTA' in regimen.get('regimen', ''):
                    resultados['regimen'] = 0.3 - (0.2 * regimen.get('confianza', 0.5))
                else:
                    resultados['regimen'] = 0.5
                
                if regimen.get('volatilidad') == 'ALTA':
                    resultados['regimen'] *= 0.9
                elif regimen.get('volatilidad') == 'BAJA':
                    resultados['regimen'] *= 1.1
                
                resultados['regimen'] = max(0, min(1, resultados['regimen']))
                resultados['detalles']['Régimen'] = f"{resultados['regimen']:.2%} ({regimen.get('regimen', 'NEUTRO')})"
            except Exception as e:
                print(f"⚠️ Error en Statsmodels: {e}")
        
        # 4. Ponderación final
        resultados['ponderada'] = (
            resultados['xgb'] * PESO_XGBOOST +
            resultados['lstm'] * PESO_LSTM +
            resultados['regimen'] * PESO_STATSMODELS
        )
        
        return resultados
    
    def generar_senal(self, df, modelo_o_symbol, symbol_o_precio=None, precio_actual=None):
        """
        Genera una señal de trading adaptándose a los parámetros recibidos.
        Maneja llamadas flexibles: 
        - (df, modelo, symbol, precio_actual)
        - (df, symbol, precio_actual)
        """
        modelo = None
        symbol = "ALTCOIN"
        
        # Adaptador flexible de argumentos
        if isinstance(modelo_o_symbol, str):
            symbol = modelo_o_symbol
            precio_actual = symbol_o_precio
        else:
            modelo = modelo_o_symbol
            if isinstance(symbol_o_precio, str):
                symbol = symbol_o_precio
            elif precio_actual is None and isinstance(symbol_o_precio, (int, float)):
                precio_actual = symbol_o_precio

        print(f"\n🎯 GENERANDO SEÑAL PARA {symbol}")
        print("-" * 40)
        
        # 1. Calcular puntuación pasando el modelo
        resultados = self.calcular_puntuacion(df, modelo_override=modelo)
        
        print(f"📊 XGBoost: {resultados['xgb']:.2%}")
        print(f"📊 LSTM: {resultados['lstm']:.2%}")
        print(f"📊 Régimen: {resultados['regimen']:.2%}")
        print(f"📊 Ponderada: {resultados['ponderada']:.2%}")
        
        close = df['close'].iloc[-1]
        entrada = precio_actual if precio_actual is not None else close
        
        # 2. Verificar umbral
        if resultados['ponderada'] < UMBRAL_COMPRA:
            mensaje = f"Puntuación baja: {resultados['ponderada']:.2%} < {UMBRAL_COMPRA:.0%}"
            return {
                'comprar': False,
                'razon': mensaje,
                'probabilidad': resultados['ponderada'],
                'detalles': resultados['detalles']
            }, mensaje
        
        # 3. Niveles con ATR
        atr = df['atr'].iloc[-1] if 'atr' in df.columns else (entrada * 0.02)
        stop_loss = entrada - (atr * SL_ATR)
        tp1 = entrada + (atr * TP1_ATR)
        tp2 = entrada + (atr * TP2_ATR)
        tp3 = entrada + (atr * TP3_ATR)
        
        # 4. Tamaño de posición
        riesgo = min(CAPITAL_INICIAL * RIESGO_POR_OPERACION, CAPITAL_INICIAL * 0.05)
        tamanio = riesgo / (entrada - stop_loss) if (entrada - stop_loss) > 0 else 0
        
        # 5. Crear señal completa
        senal = {
            'comprar': True,
            'symbol': symbol,
            'precio_entrada': entrada,
            'stop_loss': stop_loss,
            'take_profit_1': tp1,
            'take_profit_2': tp2,
            'take_profit_3': tp3,
            'tamanio': tamanio,
            'probabilidad': resultados['ponderada'],
            'detalles': resultados['detalles'],
            'timestamp': datetime.now()
        }
        
        mensaje = f"Compra confirmada con {resultados['ponderada']:.2%} de probabilidad"
        
        print(f"\n🚀 SEÑAL DE COMPRA CONFIRMADA EN {symbol}")
        print(f"   Precio entrada: ${entrada:.4f}")
        print(f"   Stop Loss: ${stop_loss:.4f}")
        print(f"   Take Profit 1: ${tp1:.4f}")
        
        self.ultima_senal = senal
        return senal, mensaje