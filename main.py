# ============================================================
# BOT DE MOMENTUM - PUNTO DE ENTRADA PRINCIPAL
# ============================================================

import sys
import os
import time
import random
from datetime import datetime
import pandas as pd

# Agregar raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import (
    MONEDAS,
    MONEDA_REFERENCIA,
    TIMEFRAME_ML,
    INTERVALO_EJECUCION,
    CAPITAL_INICIAL,
    MAX_OPERACIONES_SIMULTANEAS
)

from src.data.binance_client import obtener_datos, get_client
from src.features.indicators import calcular_todos_indicadores
from src.models.xgboost_model import ModeloExplosiones
from src.features.filters import pasar_filtros, obtener_candidatos
from src.signals.signal_generator import generar_senal_compra
from src.execution.order_manager import OrderManager
from src.utils.logger import log_error, log_senal


class BotMomentum:
    def __init__(self):
        print("\n" + "="*60)
        print("🚀 BOT DE MOMENTUM - CAZADOR DE EXPLOSIONES")
        print("="*60)
        
        # Conectar a Binance
        self.client = get_client()
        
        # Cargar modelo
        self.modelo = ModeloExplosiones()
        if not self.modelo.cargar():
            print("⚠️ Modelo no encontrado. Entrenando nuevo...")
            self._entrenar_modelo()
        
        # Gestor de órdenes
        self.ordenes = OrderManager()
        
        print(f"💰 Capital: ${CAPITAL_INICIAL}")
        print(f"📊 Monedas en lista: {len(MONEDAS)}")
        print(f"⏱️ Intervalo: {INTERVALO_EJECUCION//60} minutos")
        print("="*60)
    
    def _entrenar_modelo(self):
        """Entrena el modelo si no existe"""
        try:
            # Cargar dataset unificado
            if not os.path.exists("data/processed/dataset_unificado.csv"):
                print("⚠️ Dataset no encontrado. Descargando datos...")
                from src.data.data_processor import preparar_todas_las_monedas
                df_total = preparar_todas_las_monedas()
            else:
                df_total = pd.read_csv("data/processed/dataset_unificado.csv")
            
            # Entrenar
            self.modelo.entrenar(df_total)
            self.modelo.guardar()
            
        except Exception as e:
            print(f"❌ Error entrenando modelo: {e}")
            log_error("Error entrenando modelo", e)
    
    def ejecutar(self):
        """Ciclo principal del bot"""
        print("\n🔍 INICIANDO ANÁLISIS...")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*60)
        
        # 1. Obtener datos de todas las monedas con pausa prudente entre peticiones
        datos_monedas = {}
        total_monedas = len(MONEDAS)
        
        for idx, symbol in enumerate(MONEDAS, 1):
            # Pausa humana aleatoria (entre 1.1s y 1.5s) para cuidar la IP y el Rate Limit
            time.sleep(1.0 + random.uniform(0.1, 0.5))
            
            df = obtener_datos(symbol, TIMEFRAME_ML, 100)
            if not df.empty:
                df = calcular_todos_indicadores(df)
                datos_monedas[symbol] = df
                print(f"  [ {idx}/{total_monedas} ] ✅ {symbol} procesado correctamente")
            else:
                print(f"  [ {idx}/{total_monedas} ] ❌ Sin datos para {symbol}")
        
        # 2. Obtener BTC para el contexto de mercado
        time.sleep(1.0)
        df_btc = obtener_datos(MONEDA_REFERENCIA, TIMEFRAME_ML, 100)
        if not df_btc.empty:
            df_btc = calcular_todos_indicadores(df_btc)
        
        # 3. Aplicar filtros de selección
        print("\n🔎 APLICANDO FILTROS...")
        candidatos = obtener_candidatos(datos_monedas, df_btc)
        
        if not candidatos:
            print("\n⚠️ No hay candidatos que pasen los filtros en este ciclo.")
            return
        
        # 4. Generar señales de compra
        print(f"\n🎯 GENERANDO SEÑALES DE COMPRA...")
        
        for candidato in candidatos:
            symbol = candidato['symbol']
            df = candidato['df']
            
            senal, mensaje = generar_senal_compra(df, self.modelo)
            
            if senal and senal['comprar']:
                print(f"\n🚀 {symbol}: {mensaje}")
                log_senal(symbol, "COMPRA", senal['probabilidad'], senal['precio_entrada'])
                
                # Ejecutar compra
                self.ordenes.ejecutar_compra