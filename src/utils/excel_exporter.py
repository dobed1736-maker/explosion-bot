# ============================================================
# EXPORTADOR A EXCEL - EXPLOSION BOT
# ============================================================

import pandas as pd
import os
from datetime import datetime


def exportar_a_excel(senal, filtros, archivo="logs/senales.xlsx"):
    """
    Guarda una señal en un archivo Excel
    
    Args:
        senal (dict): Diccionario con la señal generada
        filtros (dict): Diccionario con resultados de filtros
        archivo (str): Ruta del archivo Excel
    """
    try:
        # Crear carpeta si no existe
        os.makedirs(os.path.dirname(archivo), exist_ok=True)
        
        # Preparar datos
        data = {
            'Timestamp': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            'Symbol': [senal.get('symbol', '')],
            'Probabilidad': [senal.get('probabilidad', 0)],
            'Precio_Entrada': [senal.get('precio_entrada', 0)],
            'Stop_Loss': [senal.get('stop_loss', 0)],
            'Take_Profit_1': [senal.get('take_profit_1', 0)],
            'Take_Profit_2': [senal.get('take_profit_2', 0)],
            'Take_Profit_3': [senal.get('take_profit_3', 0)],
            'Tamanio': [senal.get('tamanio', 0)],
            'Puntuacion_Filtros': [filtros.get('puntuacion', 0)],
            'Max_Puntos': [filtros.get('max_puntos', 0)]
        }
        
        # Añadir detalles de filtros si existen
        if 'detalles' in filtros:
            for nombre, detalle in filtros['detalles'].items():
                col_name = f"Filtro_{nombre}"
                if isinstance(detalle, dict):
                    data[col_name] = [detalle.get('mensaje', '')]
                else:
                    data[col_name] = [str(detalle)]
        
        df_nuevo = pd.DataFrame(data)
        
        # Si el archivo existe, añadir al final
        if os.path.exists(archivo):
            try:
                df_existente = pd.read_excel(archivo, engine='openpyxl')
                df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
            except Exception as e:
                print(f"⚠️ Error leyendo Excel existente: {e}")
                df_final = df_nuevo
        else:
            df_final = df_nuevo
        
        # Guardar
        df_final.to_excel(archivo, index=False, engine='openpyxl')
        print(f"📊 Señal guardada en Excel: {archivo}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error guardando en Excel: {e}")
        return False


def exportar_operacion(operacion, archivo="logs/operaciones.xlsx"):
    """
    Guarda una operación completada en Excel
    
    Args:
        operacion (dict): Diccionario con la operación
        archivo (str): Ruta del archivo Excel
    """
    try:
        os.makedirs(os.path.dirname(archivo), exist_ok=True)
        
        data = {
            'Timestamp': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            'Symbol': [operacion.get('symbol', '')],
            'Tipo': [operacion.get('tipo', '')],
            'Precio_Entrada': [operacion.get('precio_entrada', 0)],
            'Precio_Salida': [operacion.get('precio_salida', 0)],
            'Resultado_USD': [operacion.get('resultado_usd', 0)],
            'Resultado_%': [operacion.get('resultado_porcentaje', 0)],
            'Motivo_Salida': [operacion.get('motivo_salida', '')]
        }
        
        df_nuevo = pd.DataFrame(data)
        
        if os.path.exists(archivo):
            try:
                df_existente = pd.read_excel(archivo, engine='openpyxl')
                df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
            except Exception as e:
                print(f"⚠️ Error leyendo Excel existente: {e}")
                df_final = df_nuevo
        else:
            df_final = df_nuevo
        
        df_final.to_excel(archivo, index=False, engine='openpyxl')
        print(f"📊 Operación guardada en Excel: {archivo}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error guardando operación en Excel: {e}")
        return False


def exportar_analisis(symbol, df, archivo="logs/analisis.xlsx"):
    """
    Guarda el análisis detallado de una moneda en Excel
    
    Args:
        symbol (str): Símbolo de la moneda
        df (pd.DataFrame): DataFrame con datos e indicadores
        archivo (str): Ruta del archivo Excel
    """
    try:
        os.makedirs(os.path.dirname(archivo), exist_ok=True)
        
        # Últimas 20 velas
        df_export = df.tail(20).copy()
        df_export['symbol'] = symbol
        
        # Añadir timestamp de exportación
        df_export['exportado_en'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if os.path.exists(archivo):
            try:
                df_existente = pd.read_excel(archivo, engine='openpyxl')
                df_final = pd.concat([df_existente, df_export], ignore_index=True)
            except Exception as e:
                print(f"⚠️ Error leyendo Excel existente: {e}")
                df_final = df_export
        else:
            df_final = df_export
        
        df_final.to_excel(archivo, index=False, engine='openpyxl')
        print(f"📊 Análisis guardado en Excel: {archivo}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error guardando análisis en Excel: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Probando exportador a Excel...")
    
    # Crear señal de prueba
    senal = {
        'symbol': 'TESTUSDT',
        'probabilidad': 0.85,
        'precio_entrada': 100.0,
        'stop_loss': 95.0,
        'take_profit_1': 105.0,
        'take_profit_2': 110.0,
        'take_profit_3': 115.0,
        'tamanio': 1.5
    }
    
    filtros = {
        'puntuacion': 45,
        'max_puntos': 45,
        'detalles': {
            'Volumen': {'pasa': True, 'mensaje': 'Volumen: $2,000,000'},
            'RSI': {'pasa': True, 'mensaje': 'RSI: 52.3'}
        }
    }
    
    # Probar exportación
    exportar_a_excel(senal, filtros)
    print("✅ Exportación de señal completada")
    
    # Probar exportación de operación
    operacion = {
        'symbol': 'TESTUSDT',
        'tipo': 'COMPRA',
        'precio_entrada': 100.0,
        'precio_salida': 105.0,
        'resultado_usd': 5.0,
        'resultado_porcentaje': 5.0,
        'motivo_salida': 'Take Profit 1'
    }
    exportar_operacion(operacion)
    print("✅ Exportación de operación completada")
    
    print("\n✅ Prueba completada")