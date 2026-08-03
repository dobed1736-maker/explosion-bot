# ============================================================
# LOGGER - EXPLOSION BOT
# ============================================================

import os
import pandas as pd
from datetime import datetime


def log_error(mensaje, error=None, archivo="logs/errores.csv"):
    """
    Guarda errores en un archivo CSV
    """
    try:
        os.makedirs(os.path.dirname(archivo), exist_ok=True)
        
        data = {
            'timestamp': [datetime.now()],
            'mensaje': [mensaje],
            'error': [str(error) if error else None]
        }
        
        df = pd.DataFrame(data)
        
        if os.path.exists(archivo):
            df_existente = pd.read_csv(archivo)
            df = pd.concat([df_existente, df], ignore_index=True)
        
        df.to_csv(archivo, index=False)
        
    except Exception as e:
        print(f"❌ Error guardando log de error: {e}")


def log_senal(symbol, tipo, probabilidad, precio, archivo="logs/senales.csv"):
    """
    Guarda señales generadas en un archivo CSV
    """
    try:
        os.makedirs(os.path.dirname(archivo), exist_ok=True)
        
        data = {
            'timestamp': [datetime.now()],
            'symbol': [symbol],
            'tipo': [tipo],
            'probabilidad': [probabilidad],
            'precio': [precio]
        }
        
        df = pd.DataFrame(data)
        
        if os.path.exists(archivo):
            df_existente = pd.read_csv(archivo)
            df = pd.concat([df_existente, df], ignore_index=True)
        
        df.to_csv(archivo, index=False)
        
    except Exception as e:
        print(f"❌ Error guardando log de señal: {e}")


def log_operacion(symbol, accion, precio_entrada, precio_salida, resultado, archivo="logs/operaciones.csv"):
    """
    Guarda operaciones completadas en un archivo CSV
    """
    try:
        os.makedirs(os.path.dirname(archivo), exist_ok=True)
        
        data = {
            'timestamp': [datetime.now()],
            'symbol': [symbol],
            'accion': [accion],
            'precio_entrada': [precio_entrada],
            'precio_salida': [precio_salida],
            'resultado': [resultado]
        }
        
        df = pd.DataFrame(data)
        
        if os.path.exists(archivo):
            df_existente = pd.read_csv(archivo)
            df = pd.concat([df_existente, df], ignore_index=True)
        
        df.to_csv(archivo, index=False)
        
    except Exception as e:
        print(f"❌ Error guardando log de operación: {e}")


if __name__ == "__main__":
    print("🧪 Probando logger...")
    
    # Probar log de error
    log_error("Error de prueba", "Detalle del error")
    print("✅ Log de error guardado")
    
    # Probar log de señal
    log_senal("TESTUSDT", "COMPRA", 0.85, 100.0)
    print("✅ Log de señal guardado")
    
    # Probar log de operación
    log_operacion("TESTUSDT", "COMPRA", 100.0, 105.0, 5.0)
    print("✅ Log de operación guardado")
    
    print("\n✅ Prueba completada")