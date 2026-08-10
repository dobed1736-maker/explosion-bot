# ============================================================
# EXPLOSION BOT - PUNTO DE ENTRADA PRINCIPAL
# ============================================================

import sys
import os
import time
import pandas as pd
import numpy as np
from datetime import datetime

# Agregar raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import (
    TOP_A_ESCANEAR,
    TIMEFRAME,
    INTERVALO_EJECUCION,
    CAPITAL_INICIAL,
    MAX_OPERACIONES_SIMULTANEAS,
    UMBRAL_COMPRA
)

from src.data.binance_client import (
    get_client,
    obtener_datos,
    obtener_ganadores,
    obtener_order_book,
    obtener_funding_rate
)

from src.features.indicators import calcular_todos_indicadores
from src.features.filters import aplicar_todos_los_filtros, resumen_filtros
from src.models.xgboost_model import ModeloXGBoost
from src.models.lstm_model import ModeloLSTM
from src.models.regime_model import ModeloRegimen
from src.signals.signal_generator import GeneradorSenales
from src.signals.risk_manager import RiskManager
from src.execution.order_manager import OrderManager
from src.utils.logger import log_error, log_senal
from src.utils.excel_exporter import exportar_a_excel
from src.utils.telegram_bot import enviar_telegram


class ExplosionBot:
    """
    Orquestador principal del bot de trading cuantitativo
    """
    def __init__(self):
        print("="*60)
        print("🚀 INICIALIZANDO EXPLOSION BOT")
        print("="*60)
        
        # 1. Cargar modelos de Machine Learning
        print("\n🧠 Cargando modelos de Inteligencia Artificial...")
        self.modelo_xgb = ModeloXGBoost()
        self.modelo_xgb.cargar()
        
        self.modelo_lstm = ModeloLSTM()
        self.modelo_lstm.cargar()
        
        self.modelo_regimen = ModeloRegimen()
        
        # 2. Inicializar generadores y gestores
        self.generador = GeneradorSenales(
            modelo_xgb=self.modelo_xgb,
            modelo_lstm=self.modelo_lstm,
            modelo_regimen=self.modelo_regimen
        )
        self.risk_manager = RiskManager()
        self.order_manager = OrderManager()
        
        print("✅ Bot configurado y listo para escanear el mercado")
        
    def analizar_moneda(self, symbol, info_ganador):
        """
        Analiza una moneda individual con diagnóstico transparente de filtros y ML
        """
        try:
            # 1. Obtener datos de Binance
            df = obtener_datos(symbol, TIMEFRAME, limit=100)
            if df.empty or len(df) < 50:
                return None
                
            # 2. Calcular indicadores
            df = calcular_todos_indicadores(df)
            
            # 3. Aplicar los filtros cuantitativos
            pasa_filtros, detalles_filtros = aplicar_todos_los_filtros(df)
            if not pasa_filtros:
                # 💡 Muestra qué filtro técnico la rechazó
                # print(f"⚪ {symbol}: Rechazado por filtros técnicos ({detalles_filtros})")
                return None
                
            # 4. Generar señal y score de ML
            precio_actual = info_ganador.get('precio', df['close'].iloc[-1])
            senal = self.generador.generar_senal(df, symbol, precio_actual)
            
            prob = senal.get('probabilidad', 0) if senal else 0
            
            # 💡 Diagnóstico de la IA
            if prob < UMBRAL_COMPRA:
                print(f"📊 {symbol}: Pasó filtros técnicos | Confianza IA: {prob:.1%} (Requerido: {UMBRAL_COMPRA:.0%})")
                return None
                
            return senal
            
        except Exception as e:
            log_error(f"Error analizando {symbol}", e)
            return None

    def ejecutar_ciclo(self):
        """
        Ejecuta un ciclo de escaneo completo
        """
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔍 Iniciando escaneo de mercado...")
        
        # 1. Obtener top monedas volátiles/ganadoras
        candidatos = obtener_ganadores(limit=TOP_A_ESCANEAR)
        print(f"📋 Analizando Top {len(candidatos)} monedas más activas...")
        
        senales = []
        for g in candidatos:
            time.sleep(1)  # 👈 AGREGAR ESTA LÍNEA AQUÍ (Evita el error -1003 Too Many Requests)
            
            senal = self.analizar_moneda(g['symbol'], g)
            if senal:
                senales.append(senal)
                
                # A. Guardar en Logs
                log_senal(g['symbol'], "COMPRA", senal['probabilidad'], senal['precio_entrada'])
                
                # B. Enviar Alerta a Telegram
                msg = f"🚀 SEÑAL EN {senal['symbol']}\nProbabilidad: {senal['probabilidad']:.2%}\nPrecio Entrada: ${senal['precio_entrada']:.4f}"
                enviar_telegram(msg)
                
                # C. 🔥 EJECUTAR AUTOMÁTICAMENTE EN TESTNET
                print(f"🔥 Disparando orden en Testnet para {senal['symbol']} (Probabilidad: {senal['probabilidad']:.2%})")
                self.order_manager.ejecutar_orden_compra(
                    symbol=senal['symbol'],
                    precio_entrada=senal['precio_entrada'],
                    stop_loss=senal['stop_loss'],
                    take_profit=senal['take_profit_1'],
                    margen_usdt=20,     # $20 USD por operación
                    apalancamiento=5   # 5x apalancamiento
                )
        
      
    def ejecutar(self):
        """
        Bucle principal
        """
        while True:
            try:
                self.ejecutar_ciclo()
                print(f"\n⏳ Esperando {INTERVALO_EJECUCION//60} minutos para el siguiente escaneo...")
                time.sleep(INTERVALO_EJECUCION)
                
            except KeyboardInterrupt:
                print("\n🛑 Bot detenido por el usuario")
                break
                
            except Exception as e:
                print(f"❌ Error en ejecución: {e}")
                log_error("Error en ejecución", e)
                time.sleep(30)


if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    bot = ExplosionBot()
    bot.ejecutar()