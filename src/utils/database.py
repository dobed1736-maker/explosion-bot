import os
import psycopg2
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from psycopg2.extensions import register_adapter, AsIs

# Adaptadores para que psycopg2 reconozca los tipos numéricos de NumPy/Pandas
register_adapter(np.float32, AsIs)
register_adapter(np.float64, AsIs)
register_adapter(np.int64, AsIs)

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def get_connection():
    """Conecta a la base de datos PostgreSQL"""
    if not DATABASE_URL:
        print("⚠️ No hay DATABASE_URL configurada.")
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        return None

def inicializar_db():
    """Crea la tabla de señales si no existe y asegura las columnas de resultado"""
    conn = get_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        # 1. Crear tabla base si no existe
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS senales (
                id SERIAL PRIMARY KEY,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                symbol VARCHAR(20) NOT NULL,
                precio_entrada FLOAT NOT NULL,
                score_total FLOAT,
                prob_xgboost FLOAT,
                prob_lstm FLOAT,
                prob_statsmodels FLOAT,
                stop_loss FLOAT,
                take_profit_1 FLOAT,
                take_profit_2 FLOAT,
                estado VARCHAR(20) DEFAULT 'PENDIENTE'
            );
        """)
        
        # 2. Agregar columnas necesarias para auditoría de PnL si no existen
        cursor.execute("""
            ALTER TABLE senales 
            ADD COLUMN IF NOT EXISTS precio_salida FLOAT,
            ADD COLUMN IF NOT EXISTS pnl_usdt FLOAT,
            ADD COLUMN IF NOT EXISTS fecha_cierre TIMESTAMP;
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ BD 'senales' verificada y estructurada con métricas de PnL.")
    except Exception as e:
        print(f"❌ Error inicializando tabla en PostgreSQL: {e}")

def guardar_senal(symbol, precio, score, prob_xgb, prob_lstm, prob_stats, sl, tp1, tp2, estado='PENDIENTE'):
    """Guarda una nueva señal generada por el bot y retorna su ID"""
    conn = get_connection()
    if not conn:
        return None
    
    inserted_id = None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO senales 
            (fecha, symbol, precio_entrada, score_total, prob_xgboost, prob_lstm, prob_statsmodels, stop_loss, take_profit_1, take_profit_2, estado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (
            datetime.now(), 
            str(symbol), 
            float(precio), 
            float(score), 
            float(prob_xgb), 
            float(prob_lstm), 
            float(prob_stats), 
            float(sl), 
            float(tp1), 
            float(tp2),
            str(estado)
        ))
        inserted_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        print(f"💾 Señal de {symbol} guardada exitosamente en PostgreSQL (ID: {inserted_id})")
    except Exception as e:
        print(f"❌ Error guardando señal de {symbol}: {e}")
        
    return inserted_id

def actualizar_estado_senal(id_senal=None, symbol=None, nuevo_estado='EJECUTADA', precio_salida=None, pnl_usdt=None):
    """
    Actualiza el estado de una señal (p.ej. EJECUTADA, GANADA, PERDIDA, CANCELADA)
    Se puede buscar por ID o por Symbol (actualizando la última señal PENDIENTE de ese symbol).
    """
    conn = get_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        if id_senal:
            cursor.execute("""
                UPDATE senales 
                SET estado = %s,
                    precio_salida = COALESCE(%s, precio_salida),
                    pnl_usdt = COALESCE(%s, pnl_usdt),
                    fecha_cierre = CASE WHEN %s::VARCHAR IN ('GANADA', 'PERDIDA', 'CERRADA', 'CANCELADA') THEN %s ELSE fecha_cierre END
                WHERE id = %s;
            """, (nuevo_estado, precio_salida, pnl_usdt, nuevo_estado, datetime.now(), id_senal))
        elif symbol:
            # Si se pasa symbol, actualiza la orden más reciente que estuviera PENDIENTE
            cursor.execute("""
                UPDATE senales 
                SET estado = %s,
                    precio_salida = COALESCE(%s, precio_salida),
                    pnl_usdt = COALESCE(%s, pnl_usdt),
                    fecha_cierre = CASE WHEN %s::VARCHAR IN ('GANADA', 'PERDIDA', 'CERRADA', 'CANCELADA') THEN %s ELSE fecha_cierre END
                WHERE id = (
                    SELECT id FROM senales 
                    WHERE symbol = %s AND estado = 'PENDIENTE' 
                    ORDER BY fecha DESC LIMIT 1
                );
            """, (nuevo_estado, precio_salida, pnl_usdt, nuevo_estado, datetime.now(), symbol))

        conn.commit()
        cursor.close()
        conn.close()
        print(f"🔄 Estado de señal actualizado a '{nuevo_estado}' en BD.")
    except Exception as e:
        print(f"❌ Error actualizando estado en BD: {e}")

if __name__ == "__main__":
    inicializar_db()