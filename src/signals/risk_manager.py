# ============================================================
# GESTOR DE RIESGO - EXPLOSION BOT
# ============================================================

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import (
    CAPITAL_INICIAL,
    RIESGO_POR_OPERACION,
    RIESGO_POR_OPERACION_VOLATIL,
    MAX_OPERACIONES_SIMULTANEAS,
    ATR_PERIODO,
    TRAILING_ACTIVAR_EN,
    TRAILING_STEP_1,
    TRAILING_STEP_2,
    TRAILING_STEP_3,
    TRAILING_STEP_4,
    MOMENTUM_SALIDA_VELAS
)


class RiskManager:
    """
    Gestor de riesgo y posición
    """
    
    def __init__(self, capital=CAPITAL_INICIAL):
        self.capital = capital
        self.capital_inicial = capital
        self.posiciones_abiertas = []
        self.historial = []
        self.racha_perdedora = 0
        self.max_drawdown = 0
        self.pico_capital = capital
    
    def calcular_tamano_posicion(self, entrada, stop_loss, volatilidad=None):
        """
        Calcula el tamaño de la posición basado en riesgo
        """
        # Determinar riesgo por operación
        if volatilidad is not None and volatilidad > 5:  # ATR% > 5%
            riesgo = RIESGO_POR_OPERACION_VOLATIL
        else:
            riesgo = RIESGO_POR_OPERACION
        
        # Ajustar por racha perdedora
        if self.racha_perdedora >= 3:
            riesgo *= 0.5  # Reducir a la mitad si hay 3 pérdidas seguidas
        elif self.racha_perdedora >= 5:
            riesgo *= 0.25  # Reducir a la cuarta parte si hay 5 pérdidas seguidas
        
        riesgo_dinero = self.capital * riesgo
        
        # Calcular tamaño
        if stop_loss > 0 and entrada > stop_loss:
            riesgo_por_unidad = entrada - stop_loss
            if riesgo_por_unidad > 0:
                tamano = riesgo_dinero / riesgo_por_unidad
                return tamano, riesgo
        
        return 0, 0
    
    def actualizar_capital(self, resultado):
        """
        Actualiza el capital después de una operación
        """
        self.capital += resultado
        self.historial.append({
            'timestamp': datetime.now(),
            'resultado': resultado,
            'capital': self.capital
        })
        
        # Actualizar máximo drawdown
        if self.capital > self.pico_capital:
            self.pico_capital = self.capital
        
        drawdown_actual = (self.pico_capital - self.capital) / self.pico_capital
        if drawdown_actual > self.max_drawdown:
            self.max_drawdown = drawdown_actual
        
        # Actualizar racha
        if resultado < 0:
            self.racha_perdedora += 1
        else:
            self.racha_perdedora = 0
    
    def check_trailing_stop(self, posicion, precio_actual):
        """
        Verifica si se debe activar trailing stop
        """
        if posicion.get('trailing_activado', False):
            # Trailing ya activado, mover stop
            beneficio_actual = (precio_actual - posicion['precio_entrada']) / posicion['precio_entrada']
            
            if beneficio_actual > TRAILING_STEP_4:
                nuevo_sl = precio_actual * (1 - TRAILING_STEP_4)
            elif beneficio_actual > TRAILING_STEP_3:
                nuevo_sl = precio_actual * (1 - TRAILING_STEP_3)
            elif beneficio_actual > TRAILING_STEP_2:
                nuevo_sl = precio_actual * (1 - TRAILING_STEP_2)
            else:
                nuevo_sl = precio_actual * (1 - TRAILING_STEP_1)
            
            # Solo mover hacia arriba
            if nuevo_sl > posicion['stop_loss']:
                posicion['stop_loss'] = nuevo_sl
                print(f"   🔄 Trailing Stop movido a: ${nuevo_sl:.4f}")
            
            # Verificar si se activa salida por falta de momentum
            if posicion.get('ultimo_maximo', 0) == 0:
                posicion['ultimo_maximo'] = precio_actual
            
            if precio_actual > posicion['ultimo_maximo']:
                posicion['ultimo_maximo'] = precio_actual
                posicion['velas_sin_maximo'] = 0
            else:
                posicion['velas_sin_maximo'] += 1
            
            # Salir si no hay nuevo máximo en N velas
            if posicion['velas_sin_maximo'] >= MOMENTUM_SALIDA_VELAS:
                print(f"   ⏰ Salida por falta de momentum ({MOMENTUM_SALIDA_VELAS} velas sin máximo)")
                return 'MOMENTUM_EXIT'
        
        else:
            # Verificar si se activa trailing
            beneficio = (precio_actual - posicion['precio_entrada']) / posicion['precio_entrada']
            if beneficio > TRAILING_ACTIVAR_EN:
                posicion['trailing_activado'] = True
                posicion['ultimo_maximo'] = precio_actual
                posicion['velas_sin_maximo'] = 0
                print(f"   🚀 Trailing Stop activado (beneficio: {beneficio:.2%})")
        
        return 'HOLD'
    
    def gestionar_posicion(self, posicion, df):
        """
        Gestiona una posición abierta
        """
        if df.empty:
            return 'HOLD', None
        
        precio_actual = df['close'].iloc[-1]
        atr = df['atr'].iloc[-1] if 'atr' in df.columns else 0
        
        # 1. Verificar Stop Loss
        if precio_actual <= posicion['stop_loss']:
            print(f"   ❌ Stop Loss activado: ${posicion['stop_loss']:.4f}")
            return 'STOP_LOSS', precio_actual
        
        # 2. Verificar Take Profits
        if not posicion.get('tp1_tomado', False) and precio_actual >= posicion['tp1']:
            posicion['tp1_tomado'] = True
            print(f"   ✅ Take Profit 1 alcanzado: ${posicion['tp1']:.4f}")
            return 'TP1', precio_actual
        
        if not posicion.get('tp2_tomado', False) and precio_actual >= posicion['tp2']:
            posicion['tp2_tomado'] = True
            print(f"   ✅ Take Profit 2 alcanzado: ${posicion['tp2']:.4f}")
            return 'TP2', precio_actual
        
        if not posicion.get('tp3_tomado', False) and precio_actual >= posicion['tp3']:
            posicion['tp3_tomado'] = True
            print(f"   ✅ Take Profit 3 alcanzado: ${posicion['tp3']:.4f}")
            return 'TP3', precio_actual
        
        # 3. Verificar Trailing Stop
        return self.check_trailing_stop(posicion, precio_actual), precio_actual


if __name__ == "__main__":
    print("🧪 Probando Risk Manager...")
    
    # Crear datos de prueba
    np.random.seed(42)
    df = pd.DataFrame({
        'close': 100 + np.cumsum(np.random.randn(50) * 0.5),
        'atr': np.random.uniform(1, 3, 50),
        'high': 100 + np.cumsum(np.random.randn(50) * 0.5) + 1,
        'low': 100 + np.cumsum(np.random.randn(50) * 0.5) - 1,
    })
    
    risk = RiskManager()
    
    # Simular posición
    posicion = {
        'symbol': 'TESTUSDT',
        'precio_entrada': 100,
        'stop_loss': 95,
        'tp1': 105,
        'tp2': 110,
        'tp3': 115,
        'tamano': 1,
        'tp1_tomado': False,
        'tp2_tomado': False,
        'tp3_tomado': False,
        'trailing_activado': False,
        'ultimo_maximo': 100,
        'velas_sin_maximo': 0
    }
    
    print("📊 Simulando gestión de posición...")
    
    for i in range(10):
        precio = 100 + i * 1.2
        df_temp = df.copy()
        df_temp['close'] = precio
        df_temp['atr'] = 2
        
        accion, precio_salida = risk.gestionar_posicion(posicion, df_temp)
        
        if accion != 'HOLD':
            print(f"   Acción: {accion} a ${precio_salida:.2f}")
            break
        else:
            print(f"   HOLD - Precio: ${precio:.2f}")
    
    print("\n✅ Prueba completada")