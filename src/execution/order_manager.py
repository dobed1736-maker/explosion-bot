# ============================================================
# EJECUTA ÓRDENES EN BINANCE FUTUROS (TESTNET / REAL)
# ============================================================
# src/execution/order_manager.py

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
import os
import sys
import time

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from binance.exceptions import BinanceAPIException
from config.settings import BINANCE_TESTNET
from src.data.binance_client import get_client_ws


class OrderManager:
  """Maneja la apertura y cierre de órdenes en Binance Futuros"""

  def __init__(self):
    self.client_wrapper = get_client_ws()
    # Apuntamos a 'client_rest' que es el cliente REST interno del wrapper
    self.client = getattr(
        self.client_wrapper,
        'client_rest',
        getattr(self.client_wrapper, 'client', None),
    )

  def _obtener_precisiones(self, symbol_info):
    """Extrae la precisión exacta para la cantidad (stepSize), el precio (tickSize) y el nocional mínimo."""
    step_size = Decimal('0.001')
    tick_size = Decimal('0.01')
    min_qty = Decimal('0.001')
    min_notional = Decimal('5.0')  # Valor por defecto de seguridad

    if symbol_info:
      for f in symbol_info.get('filters', []):
        if f['filterType'] == 'LOT_SIZE':
          step_size = Decimal(str(f['stepSize']))
          min_qty = Decimal(str(f['minQty']))
        elif f['filterType'] == 'PRICE_FILTER':
          tick_size = Decimal(str(f['tickSize']))
        elif f['filterType'] in ['MIN_NOTIONAL', 'NOTIONAL']:
          if 'notional' in f:
            min_notional = Decimal(str(f['notional']))
          elif 'minNotional' in f:
            min_notional = Decimal(str(f['minNotional']))

    return tick_size, step_size, min_qty, min_notional

  def _formatear_precio(self, precio, tick_size):
    """Formatea el precio como un múltiplo exacto de tick_size sin errores de coma flotante."""
    precio_dec = Decimal(str(precio))
    precio_ajustado = (precio_dec / tick_size).quantize(
        Decimal('1'), rounding=ROUND_HALF_UP
    ) * tick_size
    return f'{precio_ajustado:f}'

  def _formatear_cantidad(self, cantidad, step_size, min_qty):
    """Formatea la cantidad como un múltiplo exacto de step_size."""
    cant_dec = Decimal(str(cantidad))
    cant_ajustada = (cant_dec / step_size).quantize(
        Decimal('1'), rounding=ROUND_DOWN
    ) * step_size

    if cant_ajustada < min_qty:
      cant_ajustada = min_qty

    return f'{cant_ajustada:f}'

  def _colocar_orden_proteccion(
      self,
      symbol,
      order_type,
      trigger_price_str,
      quantity_str,
      side='SELL',
      max_retries=3,
  ):
    """Intenta colocar orden de protección (SL o TP).

    Soporta de forma nativa la diferencia entre Testnet y Producción
    resolviendo el error API -4120 sin cruzar tipos de órdenes ni fallos de
    firma.
    """
    # Detectar entorno Testnet
    is_testnet = False
    if hasattr(self.client, 'FUTURES_TESTNET_URL') or getattr(
        self.client, 'testnet', False
    ):
      is_testnet = True

    # Mapeo de tipo para Algo Orders API
    algo_type = (
        'STOP_MARKET'
        if order_type in ['STOP_MARKET', 'STOP_LOSS']
        else 'TAKE_PROFIT_MARKET'
    )

    for intento in range(1, max_retries + 1):
      # -------------------------------------------------------------------
      # CASO A: TESTNET (Endpoint tradicional /fapi/v1/order)
      # -------------------------------------------------------------------
      if is_testnet:
        # Intento A1: closePosition='true'
        try:
          res = self.client.futures_create_order(
              symbol=symbol,
              side=side,
              type=algo_type,
              stopPrice=trigger_price_str,
              closePosition='true',
              workingType='MARK_PRICE',
          )
          return True, res
        except Exception:
          pass

        # Intento A2: Cantidad explícita + reduceOnly (vía SDK usa booleano True)
        try:
          res = self.client.futures_create_order(
              symbol=symbol,
              side=side,
              type=algo_type,
              stopPrice=trigger_price_str,
              quantity=quantity_str,
              reduceOnly=True,
              workingType='MARK_PRICE',
          )
          return True, res
        except Exception as e_testnet:
          print(
              f'    └─ ⚠️ [TESTNET Intento {intento}/{max_retries}] Error en'
              f' {symbol}: {e_testnet}'
          )

      # -------------------------------------------------------------------
      # CASO B: PRODUCCIÓN (Algo Order API /fapi/v1/algo/order)
      # -------------------------------------------------------------------
      else:
        # Intento B1: SDK Algo Order API nativo
        try:
          if hasattr(self.client, 'futures_place_algo_order'):
            res = self.client.futures_place_algo_order(
                symbol=symbol,
                side=side,
                type=algo_type,
                triggerPrice=trigger_price_str,
                closePosition='true',
                workingType='MARK_PRICE',
            )
            return True, res
        except Exception:
          pass

        # Intento B2: POST HTTP directo al endpoint Algo (closePosition)
        try:
          params = {
              'symbol': symbol,
              'side': side,
              'type': algo_type,
              'triggerPrice': trigger_price_str,
              'closePosition': 'true',
              'workingType': 'MARK_PRICE',
          }
          if hasattr(self.client, '_request_futures_api'):
            res = self.client._request_futures_api(
                'post', 'algo/order', signed=True, data=params
            )
            return True, res
          elif hasattr(self.client, '_request_api'):
            res = self.client._request_api(
                'post', 'fapi/v1/algo/order', signed=True, data=params
            )
            return True, res
        except Exception:
          pass

        # Intento B3: Fallback con cantidad explícita en Algo API
        try:
          # IMPORTANTE: En payload HTTP raw para Binance, usar string 'true'
          params_fallback = {
              'symbol': symbol,
              'side': side,
              'type': algo_type,
              'triggerPrice': trigger_price_str,
              'quantity': quantity_str,
              'reduceOnly': 'true',
              'workingType': 'MARK_PRICE',
          }
          if hasattr(self.client, '_request_futures_api'):
            res = self.client._request_futures_api(
                'post', 'algo/order', signed=True, data=params_fallback
            )
            return True, res
        except Exception as e_prod:
          print(
              f'    └─ ⚠️ [PROD Intento {intento}/{max_retries}] Error en Algo'
              f' API {symbol}: {e_prod}'
          )

      # Retardo progresivo entre intentos para no saturar la API
      time.sleep(1.0 * intento)

    return False, None

  def _aborto_emergencia(self, symbol, quantity_str):
    """Cierra la posición inmediatamente a mercado si el SL no pudo colocarse."""
    print(
        f'\n🚨 [EMERGENCIA] Imposible colocar Stop Loss. Cerrando posición en'
        f' {symbol} a mercado...'
    )
    try:
      close_order = self.client.futures_create_order(
          symbol=symbol,
          side='SELL',
          type='MARKET',
          quantity=quantity_str,
          reduceOnly=True,
      )
      print(
          f"🛑 Posición en {symbol} CERRADA POR SEGURIDAD. ID:"
          f" {close_order.get('orderId')}"
      )
      return True
    except Exception as e:
      print(
          f'☠️ [CRÍTICO] Fallo al cerrar posición de emergencia en {symbol}:'
          f' {e}'
      )
      return False

  def ejecutar_orden_compra(
      self,
      symbol,
      precio_entrada,
      stop_loss,
      take_profit,
      margen_usdt=20,
      apalancamiento=5,
  ):
    """Ejecuta una orden de COMPRA (LONG) a mercado y configura SL / TP blindados.

    Retorna True si se ejecutó y protegió correctamente, False en caso
    contrario.
    """
    try:
      print(f'\n🚀 [ORDER MANAGER] Iniciando orden LONG para {symbol}...')

      if not self.client:
        print('❌ Cliente Binance REST no disponible.')
        return False

      # 1. Configurar Apalancamiento
      try:
        self.client.futures_change_leverage(
            symbol=symbol, leverage=apalancamiento
        )
        print(f'    └─ Apalancamiento configurado: {apalancamiento}x')
      except Exception as e:
        print(f'    └─ ⚠️ No se pudo cambiar apalancamiento: {e}')

      # 2. Configurar Margen Aislado
      try:
        self.client.futures_change_margin_type(
            symbol=symbol, marginType='ISOLATED'
        )
        print('    └─ Tipo de margen: ISOLATED')
      except Exception:
        pass

      # 3. Obtener precisión exacta y filtros
      info = self.client.futures_exchange_info()
      symbol_info = next(
          (item for item in info.get('symbols', []) if item['symbol'] == symbol),
          None,
      )

      if not symbol_info:
        print(
            f'⚠️ {symbol} no fue encontrado en el exchange_info de Binance'
            ' Futuros.'
        )
        return False

      tick_size, step_size, min_qty, min_notional = self._obtener_precisiones(
          symbol_info
      )

      # 4. Calcular cantidad y validar Nocional Mínimo
      notional_total = margen_usdt * apalancamiento
      if Decimal(str(notional_total)) < min_notional:
        print(
            f'❌ El valor nocional (${notional_total} USDT) es menor al mínimo'
            f' requerido (${min_notional} USDT) para {symbol}.'
        )
        return False

      precio_ref = float(
          self.client.futures_symbol_ticker(symbol=symbol)['price']
      )
      raw_quantity = notional_total / precio_ref

      quantity_str = self._formatear_cantidad(raw_quantity, step_size, min_qty)
      sl_price_str = self._formatear_precio(stop_loss, tick_size)
      tp_price_str = self._formatear_precio(take_profit, tick_size)

      print(
          f'    └─ Entrada: {quantity_str} {symbol} (~${notional_total} USDT'
          ' nocional)'
      )

      # 5. Enviar Orden LONG a Mercado (BUY)
      order = self.client.futures_create_order(
          symbol=symbol, side='BUY', type='MARKET', quantity=quantity_str
      )
      print(f"✅ ¡ORDEN EJECUTADA EN BINANCE! ID: {order.get('orderId')}")

      # 6. Colocar Stop Loss con Blindaje
      sl_exitoso, _ = self._colocar_orden_proteccion(
          symbol=symbol,
          order_type='STOP_MARKET',
          trigger_price_str=sl_price_str,
          quantity_str=quantity_str,
          side='SELL',
          max_retries=3,
      )

      if sl_exitoso:
        print(f'    └─ 🛑 Stop Loss fijado en: ${sl_price_str}')
      else:
        self._aborto_emergencia(symbol, quantity_str)
        return False

      # 7. Colocar Take Profit con Reintentos
      tp_exitoso, _ = self._colocar_orden_proteccion(
          symbol=symbol,
          order_type='TAKE_PROFIT_MARKET',
          trigger_price_str=tp_price_str,
          quantity_str=quantity_str,
          side='SELL',
          max_retries=3,
      )

      if tp_exitoso:
        print(f'    └─ 🎯 Take Profit fijado en: ${tp_price_str}')
      else:
        print(
            f'    └─ ⚠️ No se pudo fijar TP en {symbol}, pero la posición sigue'
            ' protegida con Stop Loss.'
        )

      return True

    except BinanceAPIException as e:
      print(f'❌ Error API de Binance al ejecutar {symbol}: {e}')
      return False
    except Exception as e:
      print(f'❌ Error inesperado en OrderManager para {symbol}: {e}')
      return False