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
    
    def calcular_puntuacion(self, df):
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
        
        # 1. XGBoost
        if self.modelo_xgb is not None:
            try:
                prob_xgb = self.modelo_xgb.predecir_ultima(df)
                if prob_xgb is not None:
                    resultados['xgb'] = prob_xgb
                    resultados['detalles']['XGBoost'] = f"{prob_xgb:.2%}"
            except Exception as e:
                print(f"⚠️ Error en XGBoost: {e}")
        
        # 2. LSTM
        if self.modelo_lstm is not None:
            try:
                prob_lstm = self.modelo_lstm.predecir(df)
                if prob_lstm is not None:
                    resultados['lstm'] = prob_lstm
                    resultados['detalles']['LSTM'] = f"{prob_lstm:.2%}"
            except Exception as e:
                print(f"⚠️ Error en LSTM: {e}")
        
        # 3. Statsmodels (régimen)
        if self.modelo_regimen is not None:
            try:
                regimen = self.modelo_regimen.analizar_regimen(df)
                # Si el régimen es alcista, aumentar puntuación
                if 'ALCISTA' in regimen['regimen']:
                    resultados['regimen'] = 0.7 + (0.2 * regimen['confianza'])
                elif 'BAJISTA' in regimen['regimen']:
                    resultados['regimen'] = 0.3 - (0.2 * regimen['confianza'])
                else:
                    resultados['regimen'] = 0.5
                
                # Ajustar por volatilidad
                if regimen['volatilidad'] == 'ALTA':
                    resultados['regimen'] *= 0.9
                elif regimen['volatilidad'] == 'BAJA':
                    resultados['regimen'] *= 1.1
                
                resultados['regimen'] = max(0, min(1, resultados['regimen']))
                resultados['detalles']['Régimen'] = f"{resultados['regimen']:.2%} ({regimen['regimen']})"
            except Exception as e:
                print(f"⚠️ Error en Statsmodels: {e}")
        
        # 4. Ponderación final
        resultados['ponderada'] = (
            resultados['xgb'] * PESO_XGBOOST +
            resultados['lstm'] * PESO_LSTM +
            resultados['regimen'] * PESO_STATSMODELS
        )
        
        return resultados
    
    def generar_senal(self, df, symbol, precio_actual):
        """
        Genera una señal de trading completa
        """
        print(f"\n🎯 GENERANDO SEÑAL PARA {symbol}")
        print("-"*40)
        
        # 1. Calcular puntuación
        resultados = self.calcular_puntuacion(df)
        
        print(f"📊 XGBoost: {resultados['xgb']:.2%}")
        print(f"📊 LSTM: {resultados['lstm']:.2%}")
        print(f"📊 Régimen: {resultados['regimen']:.2%}")
        print(f"📊 Ponderada: {resultados['ponderada']:.2%}")
        
        # 2. Verificar umbral
        if resultados['ponderada'] < UMBRAL_COMPRA:
            return {
                'comprar': False,
                'razon': f"Puntuación baja: {resultados['ponderada']:.2%} < {UMBRAL_COMPRA:.0%}",
                'probabilidad': resultados['ponderada'],
                'detalles': resultados['detalles']
            }
        
        # 3. Calcular niveles de entrada/salida
        atr = df['atr'].iloc[-1]
        close = df['close'].iloc[-1]
        
        # Si el precio_actual es diferente, usarlo
        if precio_actual is not None:
            entrada = precio_actual
        else:
            entrada = close
        
        # Niveles
        stop_loss = entrada - (atr * SL_ATR)
        tp1 = entrada + (atr * TP1_ATR)
        tp2 = entrada + (atr * TP2_ATR)
        tp3 = entrada + (atr * TP3_ATR)
        
        # 4. Tamaño de posición
        riesgo_por_operacion = CAPITAL_INICIAL * RIESGO_POR_OPERACION
        riesgo_por_operacion = min(riesgo_por_operacion, CAPITAL_INICIAL * 0.05)  # Máximo 5%
        
        if stop_loss > 0:
            tamanio = riesgo_por_operacion / (entrada - stop_loss)
        else:
            tamanio = 0
        
        # 5. Crear señal
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
        
        print(f"\n🚀 SEÑAL DE COMPRA CONFIRMADA")
        print(f"   Precio entrada: ${entrada:.4f}")
        print(f"   Stop Loss: ${stop_loss:.4f} ({-SL_ATR*atr/entrada*100:.1f}%)")
        print(f"   Take Profit 1: ${tp1:.4f} ({TP1_ATR*atr/entrada*100:.1f}%) - Cierra {TP1_CIERRE:.0%}")
        print(f"   Take Profit 2: ${tp2:.4f} ({TP2_ATR*atr/entrada*100:.1f}%) - Cierra {TP2_CIERRE:.0%}")
        print(f"   Take Profit 3: ${tp3:.4f} ({TP3_ATR*atr/entrada*100:.1f}%) - Cierra {TP3_CIERRE:.0%}")
        print(f"   Tamaño: {tamanio:.4f}")
        
        self.ultima_senal = senal
        return senal


if __name__ == "__main__":
    print("🧪 Probando generador de señales...")
    
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
    
    # Simular modelos (usando valores aleatorios para prueba)
    class MockModel:
        def predecir_ultima(self, df):
            return np.random.uniform(0.4, 0.9)
        def predecir(self, df):
            return np.random.uniform(0.4, 0.9)
    
    class MockRegimen:
        def analizar_regimen(self, df):
            return {
                'regimen': 'ALCISTA_DEBIL',
                'confianza': 0.7,
                'volatilidad': 'MEDIA'
            }
    
    generador = GeneradorSenales(
        modelo_xgb=MockModel(),
        modelo_lstm=MockModel(),
        modelo_regimen=MockRegimen()
    )
    
    senal = generador.generar_senal(df, 'TESTUSDT', 105.0)
    
    if senal['comprar']:
        print("\n✅ Señal generada correctamente")
    else:
        print(f"\n⏸️ {senal['razon']}")
    
    print("\n✅ Prueba completada")