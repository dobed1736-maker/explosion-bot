# ============================================================
# EJECUTA ÓRDENES EN BINANCE FUTUROS (TESTNET / REAL)
# ============================================================
# src/execution/order_manager.py

import sys
import os
import time
import math

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
            s = f"{valor:.10f}".rstrip('0')
            if '.' in s:
                partes = s.split('.')
                return len(partes[1]) if len(partes) > 1 else 0
            return 0

        prec_qty = contar_decimales(step_size)
        prec_price = contar_decimales(tick_size)

        return prec_qty, prec_price, tick_size, step_size

    def _formatear_precio(self, precio, tick_size, prec_price):
        """Formatea el precio como un múltiplo exacto de tick_size con los decimales requeridos"""
        if tick_size > 0:
            inv = 1.0 / tick_size
            precio_ajustado = math.floor(float(precio) * inv + 0.5) / inv
        else:
            precio_ajustado = float(precio)
        
        if prec_price == 0:
            return str(int(precio_ajustado))
        return f"{precio_ajustado:.{prec_price}f}"

    def _formatear_cantidad(self, cantidad, step_size, prec_qty):
        """Formatea la cantidad como un múltiplo exacto de step_size"""
        if step_size > 0:
            inv = 1.0 / step_size
            cant_ajustada = math.floor(float(cantidad) * inv) / inv
        else:
            cant_ajustada = float(cantidad)
            
        if prec_qty == 0:
            return str(int(cant_ajustada))
        return f"{cant_ajustada:.{prec_qty}f}"

    def _colocar_orden_proteccion(self, symbol, order_type, trigger_price_str, max_retries=3):
        """
        Intenta colocar orden de proteccion (SL o TP) con reintentos y fallback de endpoints.
        """
        for intento in range(1, max_retries + 1):
            try:
                # Intento A: Orden de Futuros estándar (STOP_MARKET / TAKE_PROFIT_MARKET)
                res = self.client.futures_create_order(
                    symbol=symbol,
                    side='SELL',
                    type=order_type,
                    stopPrice=trigger_price_str,
                    closePosition='true',
                    workingType='MARK_PRICE'
                )
                return True, res
            except Exception as e1:
                # Intento B: Fallback al endpoint de Algo Orders si falla el estándar
                try:
                    if hasattr(self.client, 'futures_place_algo_order'):
                        res = self.client.futures_place_algo_order(
                            symbol=symbol,
                            side='SELL',
                            type=order_type,
                            triggerPrice=trigger_price_str,
                            closePosition='TRUE',
                            workingType='MARK_PRICE'
                        )
                    else:
                        res = self.client._request_api(
                            'post', 'fapi/v1/algo/order',
                            data={
                                'symbol': symbol,
                                'side': 'SELL',
                                'type': order_type,
                                'triggerPrice': trigger_price_str,
                                'closePosition': 'TRUE',
                                'workingType': 'MARK_PRICE'
                            },
                            signed=True
                        )
                    return True, res
                except Exception as e2:
                    print(f"    └─ ⚠️ [INTENTO {intento}/{max_retries}] Error enviando {order_type} en {symbol}: {e2}")
                    time.sleep(1.5)

        return False, None

    def _aborto_emergencia(self, symbol, quantity_str):
        """Cierra la posición inmediatamente a mercado si el SL no pudo colocarse."""
        print(f"\n🚨 [EMERGENCIA] Imposible colocar Stop Loss. Cerrando posición en {symbol} a mercado...")
        try:
            close_order = self.client.futures_create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',
                quantity=quantity_str,
                reduceOnly='true'
            )
            print(f"🛑 Posición en {symbol} CERRADA POR SEGURIDAD. ID: {close_order.get('orderId')}")
            return True
        except Exception as e:
            print(f"☠️ [CRÍTICO] Fallo al cerrar posición de emergencia en {symbol}: {e}")
            return False

    def ejecutar_orden_compra(self, symbol, precio_entrada, stop_loss, take_profit, margen_usdt=20, apalancamiento=5):
        """
        Ejecuta una orden de COMPRA (LONG) a mercado y configura SL / TP blindados.
        """
        try:
            print(f"\n🚀 [ORDER MANAGER] Iniciando orden LONG para {symbol}...")
            
            if not self.client:
                print("❌ Cliente Binance REST no disponible.")
                return None

            # 1. Configurar Apalancamiento (5x)
            try:
                self.client.futures_change_leverage(symbol=symbol, leverage=apalancamiento)
                print(f"    └─ Apalancamiento configurado: {apalancamiento}x")
            except Exception as e:
                print(f"    └─ ⚠️ No se pudo cambiar apalancamiento: {e}")

            # 2. Configurar Margen Aislado (ISOLATED)
            try:
                self.client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
                print("    └─ Tipo de margen: ISOLATED")
            except Exception:
                pass 

            # 3. Obtener precisión exacta y filtros
            info = self.client.futures_exchange_info()
            symbol_info = next((item for item in info.get('symbols', []) if item['symbol'] == symbol), None)
            
            if not symbol_info:
                print(f"⚠️ {symbol} no fue encontrado en el exchange_info de Binance Futuros.")
                return None

            prec_qty, prec_price, tick_size, step_size = self._obtener_precisiones(symbol_info)

            # 4. Calcular cantidad
            notional_total = margen_usdt * apalancamiento
            precio_ref = float(self.client.futures_symbol_ticker(symbol=symbol)['price'])
            raw_quantity = notional_total / precio_ref

            quantity_str = self._formatear_cantidad(raw_quantity, step_size, prec_qty)
            sl_price_str = self._formatear_precio(stop_loss, tick_size, prec_price)
            tp_price_str = self._formatear_precio(take_profit, tick_size, prec_price)

            print(f"    └─ Entrada: {quantity_str} {symbol} (~${notional_total} USDT nocional)")

            # 5. Enviar Orden LONG a Mercado (BUY)
            order = self.client.futures_create_order(
                symbol=symbol,
                side='BUY',
                type='MARKET',
                quantity=quantity_str
            )
            print(f"✅ ¡ORDEN EJECUTADA EN BINANCE! ID: {order.get('orderId')}")

            # 6. Colocar Stop Loss con Blindaje (Reintentos + Fallback + Aborto)
            sl_exitoso, _ = self._colocar_orden_proteccion(
                symbol=symbol,
                order_type='STOP_MARKET',
                trigger_price_str=sl_price_str,
                max_retries=3
            )

            if sl_exitoso:
                print(f"    └─ 🛑 Stop Loss fijado en: ${sl_price_str}")
            else:
                # SI EL SL FALLA 3 VECES, ABORTA LA POSICIÓN
                self._aborto_emergencia(symbol, quantity_str)
                return None

            # 7. Colocar Take Profit con Reintentos
            tp_exitoso, _ = self._colocar_orden_proteccion(
                symbol=symbol,
                order_type='TAKE_PROFIT_MARKET',
                trigger_price_str=tp_price_str,
                max_retries=3
            )

            if tp_exitoso:
                print(f"    └─ 🎯 Take Profit 1 fijado en: ${tp_price_str}")
            else:
                print(f"    └─ ⚠️ No se pudo fijar TP1 en {symbol}, pero la posición sigue protegida con Stop Loss.")

            return order

        except BinanceAPIException as e:
            print(f"❌ Error API de Binance al ejecutar {symbol}: {e}")
            return None
        except Exception as e:
            print(f"❌ Error inesperado en OrderManager para {symbol}: {e}")
            return None