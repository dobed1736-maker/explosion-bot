# ============================================================
# CREACIÓN DEL TARGET - EXPLOSION BOT
# ============================================================

import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import TARGET_UMBRAL, TARGET_VENTANA


def crear_target_explosion(df, umbral=TARGET_UMBRAL, ventana=TARGET_VENTANA):
    """
    Crea el target para predecir explosiones.
    
    El target es 1 si el precio sube más del 'umbral' en las próximas 'ventana' velas.
    Esto permite que el modelo aprenda a predecir el inicio de una explosión.
    
    Args:
        df: DataFrame con datos de velas (debe tener columna 'close')
        umbral: Subida mínima para considerar explosión (ej. 0.05 = 5%)
        ventana: Número de velas hacia adelante (ej. 12 = 1 hora en 5m)
    
    Returns:
        df con columna 'target' y 'retorno_futuro'
    """
    df = df.copy()
    
    # Precio máximo en las próximas 'ventana' velas
    precio_futuro_max = df['high'].shift(-ventana).rolling(ventana).max()
    precio_actual = df['close']
    
    # Target: 1 si sube más del umbral, 0 si no
    df['target'] = ((precio_futuro_max / precio_actual - 1) > umbral).astype(int)
    
    # Retorno futuro (para análisis)
    df['retorno_futuro'] = precio_futuro_max / precio_actual - 1
    
    return df


def verificar_fuga_futuro(df):
    """
    Verifica que no haya fuga de futuro en los datos.
    Imprime advertencia si encuentra features con datos futuros.
    """
    columnas_sospechosas = []
    
    for col in df.columns:
        # Si la columna tiene shift o rolling con window, podría tener fuga
        if 'shift' in col or 'rolling' in col:
            columnas_sospechosas.append(col)
    
    if columnas_sospechosas:
        print("⚠️ Columnas que podrían tener fuga de futuro:")
        for col in columnas_sospechosas:
            print(f"   - {col}")
        print("   → Revisa que uses 'shift(-X)' solo para el target, no para features.")
    else:
        print("✅ Verificación completada: No se detectaron columnas sospechosas.")
    
    return df


if __name__ == "__main__":
    # Prueba rápida
    print("🧪 Probando creación de target...")
    
    # Crear datos de prueba
    np.random.seed(42)
    fechas = pd.date_range('2024-01-01', periods=100, freq='5min')
    df = pd.DataFrame({
        'timestamp': fechas,
        'close': 100 + np.cumsum(np.random.randn(100) * 0.5),
        'high': 100 + np.cumsum(np.random.randn(100) * 0.5) + 0.5,
        'low': 100 + np.cumsum(np.random.randn(100) * 0.5) - 0.5,
        'volume': np.random.randint(1000, 10000, 100)
    })
    
    print(f"📊 Datos originales: {len(df)} filas")
    
    # Crear target
    df = crear_target_explosion(df, umbral=0.05, ventana=12)
    
    # Verificar
    total_explosiones = df['target'].sum()
    print(f"🎯 Target creado: {total_explosiones} explosiones ({total_explosiones/len(df)*100:.1f}%)")
    print(f"📈 Retorno futuro medio: {df['retorno_futuro'].mean():.2%}")
    
    # Mostrar ejemplos
    print("\n📋 Ejemplos de target:")
    print(df[['timestamp', 'close', 'target', 'retorno_futuro']].tail(10))
    
    print("\n✅ Prueba completada")