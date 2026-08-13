# ============================================================
# BOT DE MOMENTUM - PUNTO DE ENTRADA CON ESCÁNER DINÁMICO (MEM-OPTIMIZED)
# ============================================================

import sys
import os
import time
import gc  # 🧹 Recolector de basura para liberar memoria RAM en Render
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

# Importar Base de Datos PostgreSQL y Telegram
try:
    from src.utils.database import guardar_senal, inicializar_db, actualizar_estado_senal, get_connection
except ImportError:
    guardar_senal = None
    inicializar_db = None
    actualizar_estado_senal = None
    get_connection = None

try:
    from src.utils.telegram_bot import enviar_telegram, enviar_señal_telegram
except ImportError:
    enviar_telegram = None
    enviar_señal_telegram = None


class BotMomentumDinamico:
    def __init__(self):
        print("\n" + "="*60)
        print("🚀 CAZADOR DE EXPLOSIONES - TOP GANADORES EN TIEMPO REAL")
        print("="*60)
        
        # Verificar / Crear tabla en PostgreSQL si existe el conector
        if inicializar_db:
            inicializar_db()

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

        # 🔔 Enviar prueba de vida a Telegram al iniciar el bot
        if enviar_telegram:
            try:
                enviar_telegram("🤖 <b>BOT DE MOMENTUM INICIADO</b>\nEl cazador de explosiones está activo en Render y listo para operar.")
            except Exception as e_tg:
                print(f"⚠️ Error enviando inicio a Telegram: {e_tg}")

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
            del df_total
            gc.collect()
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
            del df_total
            gc.collect()
        except Exception as e:
            print(f"❌ Error entrenando modelo LSTM: {e}")
            log_error("Error entrenando modelo LSTM", e)

    def monitorear_posiciones_abiertas(self):
        """
        Consulta en PostgreSQL las operaciones en estado 'EJECUTADA' o 'PENDIENTE_CERRAR'.
        Garantiza cierre de conexión BD en todo escenario.
        """
        if not get_connection or not actualizar_estado_senal:
            return

        conn = get_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, symbol, precio_entrada 
                FROM senales 
                WHERE estado IN ('EJECUTADA', 'PENDIENTE_CERRAR')
            """)
            posiciones_activas = cursor.fetchall()
            cursor.close()

            if not posiciones_activas:
                return

            print(f"\n🔄 MONITOREANDO {len(posiciones_activas)} POSICIONES ACTIVAS EN BINANCE...")

            for id_db, symbol, precio_entrada in posiciones_activas:
                try:
                    pos_info = self.ordenes.client.futures_position_information(symbol=symbol)
                    pos_amount = 0.0
                    for p in pos_info:
                        if p['symbol'] == symbol:
                            pos_amount = float(p.get('positionAmt', 0))
                            break

                    if pos_amount == 0:
                        trades = self.ordenes.client.futures_account_trades(symbol=symbol, limit=5)
                        pnl_acumulado = 0.0
                        ultimo_precio_salida = precio_entrada

                        if trades:
                            pnl_acumulado = sum(float(t.get('realizedPnl', 0)) for t in trades)
                            ultimo_precio_salida = float(trades[-1].get('price', precio_entrada))
                        else:
                            # Fallback para Testnet cuando futures_account_trades tiene lag
                            try:
                                ticker = self.ordenes.client.futures_symbol_ticker(symbol=symbol)
                                ultimo_precio_salida = float(ticker.get('price', precio_entrada))
                            except Exception:
                                pass

                        nuevo_estado = "GANADA" if pnl_acumulado >= 0 else "PERDIDA"

                        print(f"🎯 Posición cerrada detectada en {symbol} | Estado: {nuevo_estado} | PnL: ${pnl_acumulado:.4f} USDT")
                        
                        actualizar_estado_senal(
                            id_senal=id_db,
                            nuevo_estado=nuevo_estado,
                            precio_salida=ultimo_precio_salida,
                            pnl_usdt=pnl_acumulado
                        )
                except Exception as e_pos:
                    print(f"⚠️ Error monitoreando posición {symbol}: {e_pos}")

        except Exception as e:
            print(f"⚠️ Error en monitoreo general de posiciones: {e}")
        finally:
            # 🔒 GARANTIZAR CIERRE DE CONEXIÓN POSTGRESQL SIEMPRE
            try:
                conn.close()
            except Exception:
                pass

    def ejecutar(self):
        print("\n🔎 ESCANEANDO GANADORES DEL MERCADO (TOP GAINERS)...")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*60)
        
        datos_monedas = {}
        df_btc = None
        candidatos = []

        try:
            # 1. Escanear top ganadores
            monedas_top = self.client_ws.escanear_top_ganadores()
            
            if not monedas_top:
                print("⚠️ No hay altcoins en rango de explosión actualmente.")
                self.monitorear_posiciones_abiertas()
                return

            print(f"📋 Monedas analizadas en esta ronda ({len(monedas_top)}):")
            print(", ".join(monedas_top[:15]) + "..." if len(monedas_top) > 15 else ", ".join(monedas_top))

            # 2. Conectar WebSocket a las ganadoras
            self.client_ws.actualizar_conector_websocket(monedas_top)
            time.sleep(2)  # Sincronizar buffer RAM

            # 3. Leer velas en directo y calcular indicadores
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
                self.monitorear_posiciones_abiertas()
                return

            # 5. Generar señales y ejecutar compras
            for candidato in candidatos:
                symbol = candidato['symbol']
                df = candidato['df']
                
                precio_actual = float(df['close'].iloc[-1])
                print(f"\n🔍 Evaluando candidato: {symbol} | Precio actual: ${precio_actual}")
                
                resultado = self.generador_senales.generar_senal(df, symbol, precio_actual)
                
                if isinstance(resultado, tuple):
                    senal = resultado[0]
                    mensaje = resultado[1]
                else:
                    senal = resultado
                    mensaje = ""

                prob = senal.get('probabilidad', 0)
                precio_in = senal.get('precio_entrada', precio_actual)
                sl = senal.get('stop_loss', 0)
                tp1 = senal.get('take_profit_1', 0)
                tp2 = senal.get('take_profit_2', 0)
                tp3 = senal.get('take_profit_3', 0)
                detalles = senal.get('detalles', {})

                # Extraer probabilidades individuales
                prob_xgb = float(detalles.get('XGBoost', '0').replace('%', '')) / 100 if 'XGBoost' in detalles else 0
                prob_lstm = float(detalles.get('LSTM', '0').replace('%', '')) / 100 if 'LSTM' in detalles else 0
                prob_stats = float(detalles.get('Régimen', '0').split('%')[0]) / 100 if 'Régimen' in detalles else 0

                es_compra = senal and senal.get('comprar', False)
                
                if es_compra:
                    # 🚀 1. PRIMERO: Ejecutar la orden en Binance
                    msg_exito = f"🚀 ¡COMPRA SOLICITADA EN {symbol}!\nPrecio: ${precio_in} | Probabilidad: {prob*100:.1f}%\nSL: ${sl} | TP1: ${tp1}"
                    print(f"\n{msg_exito}")
                    
                    log_senal(symbol, "COMPRA", prob, precio_in)

                    res_ejecucion = self.ordenes.ejecutar_orden_compra(
                        symbol=symbol,
                        precio_entrada=precio_in,
                        stop_loss=sl,
                        take_profit=tp1
                    )

                    # Evaluar si la orden realmente se envió con éxito
                    exito_orden = res_ejecucion if isinstance(res_ejecucion, bool) else True
                    estado_inicial = 'EJECUTADA' if exito_orden else 'FALLIDA'

                    # 💾 2. SEGUNDO: Guardar en PostgreSQL el estado REAL
                    id_db = None
                    if guardar_senal:
                        try:
                            id_db = guardar_senal(
                                symbol=symbol,
                                precio=precio_in,
                                score=prob,
                                prob_xgb=prob_xgb,
                                prob_lstm=prob_lstm,
                                prob_stats=prob_stats,
                                sl=sl,
                                tp1=tp1,
                                tp2=tp2,
                                estado=estado_inicial
                            )
                        except Exception as e_db:
                            print(f"⚠️ Error al guardar en PostgreSQL: {e_db}")

                    # 🔔 3. Notificar a Telegram si la orden fue válida
                    if enviar_señal_telegram and exito_orden:
                        try:
                            enviar_señal_telegram(
                                symbol=symbol,
                                tipo="COMPRA",
                                probabilidad=prob,
                                precio=precio_in,
                                tp1=tp1,
                                tp2=tp2,
                                tp3=tp3,
                                sl=sl
                            )
                        except Exception as e_tg:
                            print(f"⚠️ No se pudo enviar notificación a Telegram: {e_tg}")
                else:
                    print(f"⏸️ {symbol}: {mensaje}")

            # 6. Monitorear cierres de posiciones tras escanear
            self.monitorear_posiciones_abiertas()

        finally:
            # 🧹 LIMPIEZA AGRESIVA DE MEMORIA RAM TRAS CADA EJECUCIÓN
            datos_monedas.clear()
            candidatos.clear()
            del datos_monedas
            del df_btc
            del candidatos
            gc.collect()  # Forzar barrido del garbage collector


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
            # Vaciar caché extra del motor gc en el bucle principal
            gc.collect()
            print(f"\n⏳ Próximo rastreo en {INTERVALO_EJECUCION} segundos...")
            time.sleep(INTERVALO_EJECUCION)
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo cazador...")
        bot.client_ws.detener()
    except Exception as e:
        print(f"❌ Error en ejecución: {e}")
        log_error("Error en ejecución", e)
        bot.client_ws.detener()