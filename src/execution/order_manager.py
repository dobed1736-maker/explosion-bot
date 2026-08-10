# ============================================================
# EJECUTA ÓRDENES EN BINANCE FUTUROS (TESTNET / REAL)
# ============================================================
# src/execution/order_manager.py

import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.data.binance_client import get_client_ws
from config.settings import BINANCE_TESTNET
from binance.exceptions import BinanceAPIException


class OrderManager:
    """Maneja la apertura y cierre de órdenes en Binance Futuros"""

    def __init__(self):
        self.client_wrapper = get_client_ws()
        # Apuntamos a 'client_rest' que es el cliente REST interno del wrapper
        self.client = getattr(self.client_wrapper, 'client_rest', getattr(self.client_wrapper, 'client', None))

    def ejecutar_orden_compra(self, symbol, precio_entrada, stop_loss, take_profit, margen_usdt=20, apalancamiento=5):
        """
        Ejecuta una orden de COMPRA (LONG) a mercado y configura SL / TP
        """
        try:
            print(f"\n🚀 [ORDER MANAGER] Iniciando orden LONG para {symbol}...")
            
            # 1. Configurar Apalancamiento (5x)
            try:
                self.client.futures_change_leverage(symbol=symbol, leverage=apalancamiento)
                print(f"  └─ Apalancamiento configurado: {apalancamiento}x")
            except Exception as e:
                print(f"  └─ ⚠️ No se pudo cambiar apalancamiento: {e}")

            # 2. Configurar Margen Aislado (ISOLATED)
            try:
                self.client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
                print("  └─ Tipo de margen: ISOLATED")
            except Exception:
                pass # Si ya está en ISOLATED ignora el aviso

            # 3. Obtener precisión de decimales de la moneda
            info = self.client.futures_exchange_info()
            symbol_info = next((item for item in info['symbols'] if item['symbol'] == symbol), None)
            
            step_size = 0.001
            if symbol_info:
                for f in symbol_info['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        step_size = float(f['stepSize'])
                        break

            # 4. Calcular cantidad basada en $20 USD * 5x = $100 USD de posición
            notional_total = margen_usdt * apalancamiento
            precio_ref = float(self.client.futures_symbol_ticker(symbol=symbol)['price'])
            raw_quantity = notional_total / precio_ref

            # Redondear cantidad según precisión exigida por Binance
            precision = 0
            if step_size < 1:
                precision = len(str(step_size).split('.')[1].rstrip('0'))
            
            quantity = round(raw_quantity, precision)
            if precision == 0:
                quantity = int(quantity)

            print(f"  └─ Entrada: {quantity} {symbol} (~${notional_total} USDT nocional)")

            # 5. Enviar Orden LONG a Mercado (BUY)
            order = self.client.futures_create_order(
                symbol=symbol,
                side='BUY',
                type='MARKET',
                quantity=quantity
            )
            print(f"✅ ¡ORDEN EJECUTADA EN TESTNET! ID: {order.get('orderId')}")

            # 6. Colocar Stop Loss Automático
            try:
                sl_order = self.client.futures_create_order(
                    symbol=symbol,
                    side='SELL',
                    type='STOP_MARKET',
                    stopPrice=round(stop_loss, 6),
                    closePosition=True
                )
                print(f"  └─ 🛑 Stop Loss fijado en: ${stop_loss}")
            except Exception as e_sl:
                print(f"  └─ ❌ Error al colocar SL: {e_sl}")

            # 7. Colocar Take Profit Automático (TP1)
            try:
                tp_order = self.client.futures_create_order(
                    symbol=symbol,
                    side='SELL',
                    type='TAKE_PROFIT_MARKET',
                    stopPrice=round(take_profit, 6),
                    closePosition=True
                )
                print(f"  └─ 🎯 Take Profit 1 fijado en: ${take_profit}")
            except Exception as e_tp:
                print(f"  └─ ❌ Error al colocar TP: {e_tp}")

            return order

        except BinanceAPIException as e:
            print(f"❌ Error API de Binance al ejecutar {symbol}: {e}")
            return None
        except Exception as e:
            print(f"❌ Error inesperado en OrderManager para {symbol}: {e}")
            return None