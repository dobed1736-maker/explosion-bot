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

    def _obtener_precisiones(self, symbol_info):
        """Extrae la precisión requerida para la cantidad (stepSize) y el precio (tickSize)"""
        step_size = 0.001
        tick_size = 0.01
        
        if symbol_info:
            for f in symbol_info.get('filters', []):
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
                elif f['filterType'] == 'PRICE_FILTER':
                    tick_size = float(f['tickSize'])

        def contar_decimales(valor):
            # Formatear como flotante fijo para evitar problemas con notación científica (1e-05)
            s = f"{valor:.10f}".rstrip('0')
            if '.' in s:
                partes = s.split('.')
                return len(partes[1]) if len(partes) > 1 else 0
            return 0

        prec_qty = contar_decimales(step_size)
        prec_price = contar_decimales(tick_size)

        return prec_qty, prec_price

    def ejecutar_orden_compra(self, symbol, precio_entrada, stop_loss, take_profit, margen_usdt=20, apalancamiento=5):
        """
        Ejecuta una orden de COMPRA (LONG) a mercado y configura SL / TP
        """
        try:
            print(f"\n🚀 [ORDER MANAGER] Iniciando orden LONG para {symbol}...")
            
            if not self.client:
                print("❌ Cliente Binance REST no disponible.")
                return None

            # 1. Configurar Apalancamiento (5x)
            try:
                self.client.futures_change_leverage(symbol=symbol, leverage=apalancamiento)
                print(f"   └─ Apalancamiento configurado: {apalancamiento}x")
            except Exception as e:
                print(f"   └─ ⚠️ No se pudo cambiar apalancamiento: {e}")

            # 2. Configurar Margen Aislado (ISOLATED)
            try:
                self.client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
                print("   └─ Tipo de margen: ISOLATED")
            except Exception:
                pass # Si ya está en ISOLATED ignora el aviso

            # 3. Obtener precisión exacta de la moneda (Cantidad y Precio)
            info = self.client.futures_exchange_info()
            symbol_info = next((item for item in info.get('symbols', []) if item['symbol'] == symbol), None)
            
            if not symbol_info:
                print(f"⚠️ {symbol} no fue encontrado en el exchange_info de Binance Futuros.")
                return None

            prec_qty, prec_price = self._obtener_precisiones(symbol_info)

            # 4. Calcular cantidad basada en $20 USD * 5x = $100 USD de posición
            notional_total = margen_usdt * apalancamiento
            precio_ref = float(self.client.futures_symbol_ticker(symbol=symbol)['price'])
            raw_quantity = notional_total / precio_ref

            quantity = round(raw_quantity, prec_qty)
            if prec_qty == 0:
                quantity = int(quantity)

            # Formatear Stop Loss y Take Profit a los decimales permitidos
            sl_price_formatted = round(float(stop_loss), prec_price)
            tp_price_formatted = round(float(take_profit), prec_price)
            if prec_price == 0:
                sl_price_formatted = int(sl_price_formatted)
                tp_price_formatted = int(tp_price_formatted)

            print(f"   └─ Entrada: {quantity} {symbol} (~${notional_total} USDT nocional)")

            # 5. Enviar Orden LONG a Mercado (BUY)
            order = self.client.futures_create_order(
                symbol=symbol,
                side='BUY',
                type='MARKET',
                quantity=quantity
            )
            print(f"✅ ¡ORDEN EJECUTADA EN BINANCE! ID: {order.get('orderId')}")

            # 6. Colocar Stop Loss Automático (Usando Algo Order Endpoint)
            try:
                if hasattr(self.client, 'futures_place_algo_order'):
                    sl_order = self.client.futures_place_algo_order(
                        symbol=symbol,
                        side='SELL',
                        type='STOP_MARKET',
                        triggerPrice=str(sl_price_formatted),
                        closePosition='TRUE',
                        workingType='MARK_PRICE'
                    )
                else:
                    sl_order = self.client._request_api(
                        'post', 'fapi/v1/algo/order',
                        data={
                            'symbol': symbol,
                            'side': 'SELL',
                            'type': 'STOP_MARKET',
                            'triggerPrice': str(sl_price_formatted),
                            'closePosition': 'TRUE',
                            'workingType': 'MARK_PRICE'
                        },
                        signed=True
                    )
                print(f"   └─ 🛑 Stop Loss fijado en: ${sl_price_formatted}")
            except Exception as e_sl:
                print(f"   └─ ❌ Error al colocar SL: {e_sl}")

            # 7. Colocar Take Profit Automático (Usando Algo Order Endpoint)
            try:
                if hasattr(self.client, 'futures_place_algo_order'):
                    tp_order = self.client.futures_place_algo_order(
                        symbol=symbol,
                        side='SELL',
                        type='TAKE_PROFIT_MARKET',
                        triggerPrice=str(tp_price_formatted),
                        closePosition='TRUE',
                        workingType='MARK_PRICE'
                    )
                else:
                    tp_order = self.client._request_api(
                        'post', 'fapi/v1/algo/order',
                        data={
                            'symbol': symbol,
                            'side': 'SELL',
                            'type': 'TAKE_PROFIT_MARKET',
                            'triggerPrice': str(tp_price_formatted),
                            'closePosition': 'TRUE',
                            'workingType': 'MARK_PRICE'
                        },
                        signed=True
                    )
                print(f"   └─ 🎯 Take Profit 1 fijado en: ${tp_price_formatted}")
            except Exception as e_tp:
                print(f"   └─ ❌ Error al colocar TP: {e_tp}")

            return order

        except BinanceAPIException as e:
            print(f"❌ Error API de Binance al ejecutar {symbol}: {e}")
            return None
        except Exception as e:
            print(f"❌ Error inesperado en OrderManager para {symbol}: {e}")
            return None    
        