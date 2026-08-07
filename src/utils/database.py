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
    """Crea la tabla de señales si no existe"""
    conn = get_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
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
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Tabla de BD 'senales' verificada/lista en PostgreSQL")
    except Exception as e:
        print(f"❌ Error creando tabla en PostgreSQL: {e}")

def guardar_senal(symbol, precio, score, prob_xgb, prob_lstm, prob_stats, sl, tp1, tp2):
    """Guarda una nueva señal generada por el bot"""
    conn = get_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO senales 
            (fecha, symbol, precio_entrada, score_total, prob_xgboost, prob_lstm, prob_statsmodels, stop_loss, take_profit_1, take_profit_2)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            float(tp2)
        ))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"💾 Señal de {symbol} guardada exitosamente en PostgreSQL")
    except Exception as e:
        print(f"❌ Error guardando señal de {symbol}: {e}")

if __name__ == "__main__":
    inicializar_db()