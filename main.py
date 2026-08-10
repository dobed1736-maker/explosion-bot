# ============================================================
# BOT DE MOMENTUM - PUNTO DE ENTRADA CON ESCÁNER DINÁMICO
# ============================================================

import sys
import os
import time
from datetime import datetime
import pandas as pd

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
from src.features.filters import pasar_filtros, obtener_candidatos
from src.signals.signal_generator import GeneradorSenales
from src.execution.order_manager import OrderManager
from src.utils.logger import log_error, log_senal

class BotMomentumDinamico:
    def __init__(self):
        print("\n" + "="*60)
        print("🚀 CAZADOR DE EXPLOSIONES - TOP GANADORES EN TIEMPO REAL")
        print("="*60)
        
        self.client_ws = get_client_ws()
        
        self.modelo = ModeloExplosiones()
        if not self.modelo.cargar():
            print("⚠️ Modelo no encontrado. Entrenando nuevo...")
            self._entrenar_modelo()
        
        self.ordenes = OrderManager()
        print(f"💰 Capital Inicial: ${CAPITAL_INICIAL}")
        print("="*60)

    def _entrenar_modelo(self):
        try:
            if not os.path.exists("data/processed/dataset_unificado.csv"):
                print("⚠️ Dataset no encontrado. Descargando datos...")
                from src.data.data_processor import preparar_todas_las_monedas
                df_total = preparar_todas_las_monedas()
            else:
                df_total = pd.read_csv("data/processed/dataset_unificado.csv")
            
            self.modelo.entrenar(df_total)
            self.modelo.guardar()
        except Exception as e:
            print(f"❌ Error entrenando modelo: {e}")
            log_error("Error entrenando modelo", e)

    def ejecutar(self):
        print("\n🔎 ESCANEANDO GANADORES DEL MERCADO (TOP GAINERS)...")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*60)
        
        # 1. Buscar monedas que están subiendo rápido en este instante
        monedas_top = self.client_ws.escanear_top_ganadores()
        
        if not monedas_top:
            print("⚠️ No hay altcoins en rango de explosión actualmente.")
            return

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

        # 4. Filtrar y evaluar modelo de IA
        print("\n🎯 FILTRANDO EXPLOSIONES REALES CON IA...")
        candidatos = obtener_candidatos(datos_monedas, df_btc)

        if not candidatos:
            print("\n⚠️ Ningún ganador superó los filtros estrictos de confirmación.")
            return

        # 5. Mandar señal y ejecutar compra
        for candidato in candidatos:
            symbol = candidato['symbol']
            df = candidato['df']
            
            senal, mensaje =  GeneradorSenales(df, self.modelo)
            
            if senal and senal['comprar']:
                print(f"\n🚀 ¡COMPRA EJECUTADA EN {symbol}!: {mensaje}")
                log_senal(symbol, "COMPRA", senal['probabilidad'], senal['precio_entrada'])
                self.ordenes.ejecutar_compra(symbol, senal)
            else:
                print(f"\n⏸️ {symbol}: {mensaje}")

if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("models", exist_ok=True)
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