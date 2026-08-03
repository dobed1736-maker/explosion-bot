# ============================================================
# MODELO DE RÉGIMEN (Statsmodels) - EXPLOSION BOT
# ============================================================

import pandas as pd
import numpy as np
import sys
import os
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.stattools import kpss
import warnings
warnings.filterwarnings('ignore')

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import PESO_STATSMODELS


class ModeloRegimen:
    """
    Modelo para detectar el régimen del mercado usando Statsmodels
    """
    
    def __init__(self):
        self.regimen_actual = 'NEUTRAL'
        self.volatilidad = 0
        self.tendencia = 0
        self.confianza = 0.5
    
    def detectar_estacionariedad(self, serie):
        """
        Detecta si una serie es estacionaria usando ADF test
        """
        try:
            # ADF Test
            adf_result = adfuller(serie.dropna(), autolag='AIC')
            adf_pvalue = adf_result[1]
            
            # KPSS Test
            kpss_result = kpss(serie.dropna(), regression='c', nlags='auto')
            kpss_pvalue = kpss_result[1]
            
            # Si ADF p-value < 0.05 y KPSS p-value > 0.05 → Estacionaria
            # Si ADF p-value > 0.05 y KPSS p-value < 0.05 → No estacionaria (tendencia)
            
            if adf_pvalue < 0.05 and kpss_pvalue > 0.05:
                return 'ESTACIONARIA', 0.8
            elif adf_pvalue > 0.05 and kpss_pvalue < 0.05:
                return 'TENDENCIA', 0.8
            else:
                return 'NEUTRAL', 0.5
                
        except Exception as e:
            print(f"⚠️ Error en test de estacionariedad: {e}")
            return 'NEUTRAL', 0.5
    
    def calcular_volatilidad(self, df, periodo=20):
        """
        Calcula la volatilidad actual vs histórica
        """
        try:
            # Retornos
            retornos = df['close'].pct_change().dropna()
            
            # Volatilidad actual (últimas 20 velas)
            vol_actual = retornos.iloc[-periodo:].std() * 100
            
            # Volatilidad histórica (todo el período)
            vol_historica = retornos.std() * 100
            
            # Ratio de volatilidad
            if vol_historica > 0:
                ratio = vol_actual / vol_historica
            else:
                ratio = 1
            
            # Clasificar
            if ratio > 1.5:
                nivel = 'ALTA'
                confianza = 0.8
            elif ratio > 0.8:
                nivel = 'MEDIA'
                confianza = 0.6
            else:
                nivel = 'BAJA'
                confianza = 0.7
            
            return nivel, ratio, confianza
            
        except Exception as e:
            print(f"⚠️ Error calculando volatilidad: {e}")
            return 'MEDIA', 1.0, 0.5
    
    def detectar_tendencia(self, df, periodo=50):
        """
        Detecta la dirección de la tendencia
        """
        try:
            # EMAs
            ema_9 = df['close'].ewm(span=9, adjust=False).mean()
            ema_21 = df['close'].ewm(span=21, adjust=False).mean()
            ema_50 = df['close'].ewm(span=50, adjust=False).mean()
            
            # Últimos valores
            precio_actual = df['close'].iloc[-1]
            ema_9_actual = ema_9.iloc[-1]
            ema_21_actual = ema_21.iloc[-1]
            ema_50_actual = ema_50.iloc[-1]
            
            # Pendientes
            pendiente_9 = (ema_9.iloc[-1] - ema_9.iloc[-10]) / ema_9.iloc[-10] * 100
            pendiente_21 = (ema_21.iloc[-1] - ema_21.iloc[-10]) / ema_21.iloc[-10] * 100
            
            # Clasificar
            if precio_actual > ema_9_actual > ema_21_actual > ema_50_actual:
                if pendiente_9 > 0 and pendiente_21 > 0:
                    return 'ALCISTA_FUERTE', 0.9
            
            elif precio_actual > ema_9_actual > ema_21_actual:
                if pendiente_9 > 0:
                    return 'ALCISTA_DEBIL', 0.7
            
            elif precio_actual < ema_9_actual < ema_21_actual < ema_50_actual:
                if pendiente_9 < 0 and pendiente_21 < 0:
                    return 'BAJISTA_FUERTE', 0.9
            
            elif precio_actual < ema_9_actual < ema_21_actual:
                if pendiente_9 < 0:
                    return 'BAJISTA_DEBIL', 0.7
            
            else:
                return 'LATERAL', 0.5
            
        except Exception as e:
            print(f"⚠️ Error detectando tendencia: {e}")
            return 'NEUTRAL', 0.5
    
    def analizar_regimen(self, df):
        """
        Análisis completo del régimen de mercado
        """
        print("\n" + "="*50)
        print("📊 ANÁLISIS DE RÉGIMEN (Statsmodels)")
        print("="*50)
        
        # 1. Estacionariedad (tendencia vs rango)
        estacionariedad, conf_est = self.detectar_estacionariedad(df['close'])
        
        # 2. Volatilidad
        volatilidad, ratio_vol, conf_vol = self.calcular_volatilidad(df)
        
        # 3. Tendencia
        tendencia, conf_tend = self.detectar_tendencia(df)
        
        # 4. Calcular puntuación de régimen
        # Si hay tendencia alcista, el régimen es favorable para compras
        puntaje_regimen = 0.5  # Neutral por defecto
        
        if tendencia in ['ALCISTA_FUERTE', 'ALCISTA_DEBIL']:
            puntaje_regimen += 0.2
        elif tendencia in ['BAJISTA_FUERTE', 'BAJISTA_DEBIL']:
            puntaje_regimen -= 0.2
        
        if estacionariedad == 'TENDENCIA':
            puntaje_regimen += 0.1
        
        if volatilidad == 'ALTA':
            puntaje_regimen -= 0.1
        elif volatilidad == 'BAJA':
            puntaje_regimen += 0.1
        
        # Limitar entre 0 y 1
        puntaje_regimen = max(0, min(1, puntaje_regimen))
        
        # Almacenar resultados
        self.regimen_actual = tendencia
        self.volatilidad = volatilidad
        self.tendencia = tendencia
        self.confianza = (conf_est + conf_vol + conf_tend) / 3
        
        # Mostrar resultados
        print(f"📈 Régimen: {tendencia}")
        print(f"📊 Estacionariedad: {estacionariedad}")
        print(f"🌊 Volatilidad: {volatilidad} (ratio: {ratio_vol:.2f}x)")
        print(f"🎯 Puntaje de régimen: {puntaje_regimen:.2f}")
        print(f"🔒 Confianza: {self.confianza:.2%}")
        
        return {
            'regimen': tendencia,
            'estacionariedad': estacionariedad,
            'volatilidad': volatilidad,
            'volatilidad_ratio': ratio_vol,
            'puntaje': puntaje_regimen,
            'confianza': self.confianza
        }
    
    def obtener_factor(self, df):
        """
        Obtiene un factor de corrección basado en el régimen
        """
        resultado = self.analizar_regimen(df)
        
        # Si el régimen es alcista, aumentar confianza en señales
        if 'ALCISTA' in resultado['regimen']:
            factor = 1.0 + (0.1 * resultado['confianza'])
        # Si es bajista, reducir confianza
        elif 'BAJISTA' in resultado['regimen']:
            factor = 1.0 - (0.15 * resultado['confianza'])
        # Si es lateral, neutral
        else:
            factor = 1.0
        
        # Si la volatilidad es alta, reducir factor
        if resultado['volatilidad'] == 'ALTA':
            factor *= 0.9
        
        return max(0.5, min(1.5, factor))


if __name__ == "__main__":
    print("🧪 Probando modelo de régimen...")
    
    # Crear datos de prueba
    np.random.seed(42)
    df = pd.DataFrame({
        'close': 100 + np.cumsum(np.random.randn(100) * 0.5),
        'high': 100 + np.cumsum(np.random.randn(100) * 0.5) + 0.5,
        'low': 100 + np.cumsum(np.random.randn(100) * 0.5) - 0.5,
        'volume': np.random.randint(1000, 10000, 100),
        'taker_buy_base_asset_volume': np.random.randint(500, 5000, 100)
    })
    
    modelo = ModeloRegimen()
    resultado = modelo.analizar_regimen(df)
    
    print("\n📋 Resumen:")
    for key, value in resultado.items():
        print(f"   {key}: {value}")
    
    print("\n✅ Prueba completada")