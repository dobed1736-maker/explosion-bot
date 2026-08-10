# ============================================================
# BOT DE MOMENTUM - PUNTO DE ENTRADA CON ESCÁNER DINÁMICO
# ============================================================

import sys
import os
import time
from datetime import datetime
import pandas as pd

# Asegurar que el directorio raíz está en el path
DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
if DIRECTORIO_RAIZ not in sys.path:
    sys.path.insert(0, DIRECTORIO_RAIZ)

from config.settings import (
    INTERVALO_EJECUCION,
    CAPITAL_INICIAL
)

from src.data.binance_client import get_client_ws
from src.features.indicators import calcular_todos_indicadores
from src.models.xgboost_model import ModeloXGBoost as ModeloExplosiones
from src.models.lstm_model import ModeloLSTM
from src.models.regime_model import ModeloRegimen
from src.features.filters import pasar_filtros, obtener_candidatos
from src.signals.signal_generator import GeneradorSenales
from src.execution.order_manager import OrderManager
from src.utils.logger import log_error, log_senal

try:
    from src.utils.telegram_bot import enviar_mensaje_telegram
except ImportError:
    enviar_mensaje_telegram = None


class BotMomentumDinamico:
    def __init__(self):
        print("\n" + "="*60)
        print("🚀 CAZADOR DE EXPLOSIONES - TOP GANADORES EN TIEMPO REAL")
        print("="*60)
        
        self.client_ws = get_client_ws()
        
        # 1. Cargar XGBoost
        self.modelo_xgb = ModeloExplosiones()
        if not self.modelo_xgb.cargar():
            print("⚠️ Modelo XGBoost no encontrado. Entrenando nuevo...")
            self._entrenar_modelo_xgb()

        # 2. Cargar LSTM (Red Neuronal)
        self.modelo_lstm = ModeloLSTM()
        if not self.modelo_lstm.cargar():
            print("⚠️ Modelo LSTM no encontrado. Entrenando nuevo...")
            self._entrenar_modelo_lstm()

        # 3. Cargar Régimen de Mercado (Statsmodels)
        self.modelo_regimen = ModeloRegimen()

        # 4. Iniciar Generador de Señales integrando el Ensamble Completo
        self.generador_senales = GeneradorSenales(
            modelo_xgb=self.modelo_xgb,
            modelo_lstm=self.modelo_lstm,
            modelo_regimen=self.modelo_regimen
        )
        
        self.ordenes = OrderManager()
        print(f"💰 Capital Inicial: ${CAPITAL_INICIAL}")
        print("="*60)

    def _entrenar_modelo_xgb(self):
        try:
            ruta_dataset = "data/processed/dataset_unificado.csv"
            if not os.path.exists(ruta_dataset):
                print("⚠️ Dataset no encontrado. Descargando datos...")
                from src.data.data_processor import preparar_todas_las_monedas
                df_total = preparar_todas_las_monedas()
            else:
                df_total = pd.read_csv(ruta_dataset)
            
            self.modelo_xgb.entrenar(df_total)
            self.modelo_xgb.guardar()
        except Exception as e:
            print(f"❌ Error entrenando modelo XGBoost: {e}")
            log_error("Error entrenando modelo XGBoost", e)

    def _entrenar_modelo_lstm(self):
        try:
            ruta_dataset = "data/processed/dataset_unificado.csv"
            if not os.path.exists(ruta_dataset):
                print("⚠️ Dataset no encontrado para LSTM...")
                from src.data.data_processor import preparar_todas_las_monedas
                df_total = preparar_todas_las_monedas()
            else:
                df_total = pd.read_csv(ruta_dataset)
            
            self.modelo_lstm.entrenar(df_total, epochs=25)
            self.modelo_lstm.guardar()
        except Exception as e:
            print(f"❌ Error entrenando modelo LSTM: {e}")
            log_error("Error entrenando modelo LSTM", e)

    def ejecutar(self):
        print("\n🔎 ESCANEANDO GANADORES DEL MERCADO (TOP GAINERS)...")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*60)
        
        # 1. Escanear top ganadores
        monedas_top = self.client_ws.escanear_top_ganadores()
        
        if not monedas_top:
            print("⚠️ No hay altcoins en rango de explosión actualmente.")
            return

        print(f"📋 Monedas analizadas en esta ronda ({len(monedas_top)}):")
        print(", ".join(monedas_top[:15]) + "..." if len(monedas_top) > 15 else ", ".join(monedas_top))

        # 2. Conectar WebSocket a las ganadoras
        self.client_ws.actualizar_conector_websocket(monedas_top)
        time.sleep(2)  # Sincronizar buffer RAM

        # 3. Leer velas en directo y calcular indicadores
        datos_monedas = {}
        for symbol in monedas_top:
            df = self.client_ws.obtener_velas(symbol)
            if not df.empty and len(df) >= 30:
                df = calcular_todos_indicadores(df)
                datos_monedas[symbol] = df

        df_btc = self.client_ws.obtener_velas('BTCUSDT')
        if not df_btc.empty and len(df_btc) >= 30:
            df_btc = calcular_todos_indicadores(df_btc)

        # 4. Filtrar candidatas
        print("\n🎯 FILTRANDO EXPLOSIONES REALES CON IA...")
        candidatos = obtener_candidatos(datos_monedas, df_btc)

        if not candidatos:
            print("\n⚠️ Ningún ganador superó los filtros estrictos de confirmación.")
            return

        # 5. Generar señales y ejecutar compras
        # 5. Generar señales y ejecutar compras
        for candidato in candidatos:
            symbol = candidato['symbol']
            df = candidato['df']
            
            precio_actual = float(df['close'].iloc[-1])
            print(f"\n🔍 Evaluando candidato: {symbol} | Precio actual: ${precio_actual}")
            
            # Pasamos los parámetros por posición: (df, symbol, precio_actual)
            resultado = self.generador_senales.generar_senal(df, symbol, precio_actual)
            
            if isinstance(resultado, tuple):
                senal = resultado[0]
                mensaje = resultado[1]
            else:
                senal = resultado
                mensaje = ""

            if senal and senal.get('comprar', False):
                prob = senal.get('probabilidad', 0)
                precio_in = senal.get('precio_entrada', precio_actual)
                sl = senal.get('stop_loss')
                tp = senal.get('take_profit_1')

                msg_exito = f"🚀 ¡COMPRA EJECUTADA EN {symbol}!\nPrecio: ${precio_in} | Probabilidad: {prob*100:.1f}%\nSL: ${sl} | TP: ${tp}"
                print(f"\n{msg_exito}")
                
                # Guardar logs
                log_senal(symbol, "COMPRA", prob, precio_in)

                # Notificación Telegram
                if enviar_mensaje_telegram:
                    try:
                        enviar_mensaje_telegram(msg_exito)
                    except Exception as e_tg:
                        print(f"⚠️ No se pudo enviar notificación a Telegram: {e_tg}")

                # Ejecutar orden
                self.ordenes.ejecutar_orden_compra(
                    symbol=symbol,
                    precio_entrada=precio_in,
                    stop_loss=sl,
                    take_profit=tp
                )
            else:
                print(f"⏸️ {symbol}: {mensaje}")

if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("models/lstm", exist_ok=True)
    os.makedirs("models/xgboost", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    bot = BotMomentumDinamico()
    
    try:
        while True:
            bot.ejecutar()
            print(f"\n⏳ Próximo rastreo en {INTERVALO_EJECUCION} segundos...")
            time.sleep(INTERVALO_EJECUCION)
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo cazador...")
        bot.client_ws.detener()
    except Exception as e:
        print(f"❌ Error en ejecución: {e}")
        log_error("Error en ejecución", e)
        bot.client_ws.detener()