# ============================================================
# EXPLOSION BOT - PUNTO DE ENTRADA PRINCIPAL
# ============================================================

import sys
import os
import time
import pandas as pd
import numpy as np
from datetime import datetime
from src.utils.database import inicializar_db, guardar_senal
# Agregar raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import (
    TOP_A_ESCANEAR,
    TIMEFRAME,
    INTERVALO_EJECUCION,
    CAPITAL_INICIAL,
    MAX_OPERACIONES_SIMULTANEAS
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
from src.utils.logger import log_error, log_senal
from src.utils.excel_exporter import exportar_a_excel
from src.utils.telegram_bot import enviar_telegram


class ExplosionBot:
    """
    Bot principal que orquesta todos los módulos
    """
    
    def __init__(self):
        print("\n" + "="*60)
        print("💥 EXPLOSION BOT - CAZADOR DE EXPLOSIONES")
        print("="*60)
        print(f"💰 Capital: ${CAPITAL_INICIAL:,.0f}")
        print(f"📊 Timeframe: {TIMEFRAME}")
        print(f"⏱️ Intervalo: {INTERVALO_EJECUCION//60} minutos")
        print(f"🔍 Top ganadores: {TOP_A_ESCANEAR}")
        print("="*60)
        
        # Conectar a Binance
        self.client = get_client()
        
        # Cargar modelos
        self.modelo_xgb = ModeloXGBoost()
        self.modelo_lstm = ModeloLSTM()
        self.modelo_regimen = ModeloRegimen()
        
        # Cargar modelos guardados
        self.modelo_xgb.cargar()
        self.modelo_lstm.cargar()
        
        # Inicializar generador de señales
        self.generador = GeneradorSenales(
            modelo_xgb=self.modelo_xgb,
            modelo_lstm=self.modelo_lstm,
            modelo_regimen=self.modelo_regimen
        )
        
        # Inicializar gestor de riesgo
        self.risk = RiskManager(CAPITAL_INICIAL)
        
        print("✅ Bot inicializado correctamente")
    
    def obtener_datos_moneda(self, symbol):
        """
        Obtiene y procesa datos de una moneda
        """
        try:
            df = obtener_datos(symbol, TIMEFRAME, 100)
            
            if df.empty:
                return None
            
            # Calcular indicadores
            df = calcular_todos_indicadores(df)
            
            return df
            
        except Exception as e:
            print(f"   ❌ Error obteniendo datos de {symbol}: {e}")
            return None
    
   def analizar_moneda(self, symbol, ganador_info):
        """
        Analiza una moneda y devuelve señal si corresponde
        """
        print(f"\n📈 Analizando {symbol}...")
        
        # 1. Obtener datos
        df = self.obtener_datos_moneda(symbol)
        if df is None or df.empty:
            return None
        
        # 2. Obtener order book
        book = obtener_order_book(symbol, 20)
        if book is None:
            book_imbalance = 1.0
        else:
            book_imbalance = book.get('imbalance', 1.0)
        
        # 3. Obtener funding rate
        funding_rate = obtener_funding_rate(symbol)
        
        # 4. Obtener BTC para comparación
        btc_data = self.obtener_datos_moneda('BTCUSDT')
        if btc_data is not None and not btc_data.empty:
            btc_cambio = (btc_data['close'].iloc[-1] / btc_data['close'].iloc[-24] - 1) * 100
        else:
            btc_cambio = 0
        
        # 5. Aplicar filtros
        resultado_filtros = aplicar_todos_los_filtros(
            df, symbol, ganador_info, book_imbalance, funding_rate, btc_cambio
        )
        
        print(resumen_filtros(resultado_filtros))
        
        # 6. Si no pasa filtros, no hay señal
        if not resultado_filtros['pasa_todos']:
            return None
        
        # 7. Generar señal
        precio_actual = ganador_info.get('precio', df['close'].iloc[-1])
        senal = self.generador.generar_senal(df, symbol, precio_actual)
        
        # 8. Si no hay señal, salir
        if not senal['comprar']:
            print(f"\n⏸️ {senal['razon']}")
            return None
        
        # 9. Guardar señal en Logs
        log_senal(symbol, "COMPRA", senal['probabilidad'], senal['precio_entrada'])
        
        # 🗄️ 10. Guardar en PostgreSQL
        try:
            guardar_senal(
                symbol=symbol,
                precio=senal['precio_entrada'],
                score=senal['probabilidad'],
                prob_xgb=senal.get('prob_xgb', 0.0),
                prob_lstm=senal.get('prob_lstm', 0.0),
                prob_stats=senal.get('prob_statsmodels', 0.0),
                sl=senal['stop_loss'],
                tp1=senal['take_profit_1'],
                tp2=senal['take_profit_2']
            )
        except Exception as e:
            print(f"⚠️ No se pudo guardar en la BD: {e}")
        
        # 11. Enviar a Telegram
        mensaje = self._formatear_mensaje(senal, resultado_filtros)
        enviar_telegram(mensaje)
        
        # 12. Exportar a Excel
        exportar_a_excel(senal, resultado_filtros)
        
        return senal
    
def _formatear_mensaje(self, senal, filtros):
        """
        Formatea un mensaje para Telegram
        """
        mensaje = f"""
💥 EXPLOSION BOT - SEÑAL DE COMPRA

🚀 {senal['symbol']}
📊 Probabilidad: {senal['probabilidad']:.2%}

💰 Precio entrada: ${senal['precio_entrada']:.4f}
🛑 Stop Loss: ${senal['stop_loss']:.4f}
🎯 Take Profit 1: ${senal['take_profit_1']:.4f}
🎯 Take Profit 2: ${senal['take_profit_2']:.4f}
🎯 Take Profit 3: ${senal['take_profit_3']:.4f}

📊 Puntuación filtros: {filtros['puntuacion']}/{filtros['max_puntos']}
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return mensaje
    
    def ejecutar_ciclo(self):
        """
        Ejecuta un ciclo completo de análisis
        """
        print("\n" + "="*60)
        print(f"🔍 INICIANDO ANÁLISIS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # 1. Obtener ganadores
        ganadores = obtener_ganadores(TOP_A_ESCANEAR)
        
        if not ganadores:
            print("❌ No se obtuvieron ganadores")
            return
        
        print(f"\n🏆 TOP {len(ganadores[:10])} GANADORES:")
        for i, g in enumerate(ganadores[:10], 1):
            print(f"   {i}. {g['symbol']}: {g['cambio']:+.2f}% (${g['volumen']:,.0f})")
        
        # 2. Filtrar por rango de entrada
        candidatos = []
        for g in ganadores:
            cambio = g.get('cambio', 0)
            if 5 <= cambio <= 15:
                candidatos.append(g)
        
        if not candidatos:
            print("\n⚠️ No hay monedas en rango de entrada (5%-15%)")
            return
        
        print(f"\n🎯 MONEDAS EN RANGO DE ENTRADA ({len(candidatos)}):")
        for g in candidatos:
            print(f"   {g['symbol']}: {g['cambio']:.2f}%")
        
        # 3. Analizar cada candidato
        senales = []
        for g in candidatos:
            senal = self.analizar_moneda(g['symbol'], g)
            if senal:
                senales.append(senal)
        
        # 4. Resumen
        print("\n" + "="*60)
        print(f"📊 RESUMEN: {len(senales)} señales generadas")
        print("="*60)
        
        for s in senales:
            print(f"   🚀 {s['symbol']}: {s['probabilidad']:.2%}")
    
    def ejecutar(self):
        """
        Bucle principal
        """
        while True:
            try:
                self.ejecutar_ciclo()
                print(f"\n⏳ Esperando {INTERVALO_EJECUCION//60} minutos...")
                time.sleep(INTERVALO_EJECUCION)
                
            except KeyboardInterrupt:
                print("\n🛑 Bot detenido por el usuario")
                break
                
            except Exception as e:
                print(f"❌ Error en ejecución: {e}")
                log_error("Error en ejecución", e)
                time.sleep(30)
            print("🔄 Bot vivo - escaneando mercado...") 
             
             
if __name__ == "__main__":
    # Crear carpetas necesarias
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("models/xgboost", exist_ok=True)
    os.makedirs("models/lstm", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    inicializar_db()

    bot = ExplosionBot()
    bot.ejecutar()