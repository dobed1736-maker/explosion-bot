import os
import sys

# Asegurar que el directorio raíz esté en el PATH
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
)

from binance.client import Client
from config.settings import (
    BINANCE_API_KEY,
    BINANCE_SECRET_KEY,
    BINANCE_TESTNET,
)
from src.execution.order_manager import OrderManager


def probar_moneda_micro_precio():
  print(
      '🧪 [TEST MICRO-PRECIO] Buscando nueva moneda de micro-precio en'
      ' Testnet...\n'
  )

  client_directo = Client(
      BINANCE_API_KEY, BINANCE_SECRET_KEY, testnet=BINANCE_TESTNET
  )
  order_manager = OrderManager()

  # 1. Obtener símbolos que ya tienen posición abierta para ignorarlos
  posiciones_abiertas = set()
  try:
    acc_info = client_directo.futures_account()
    for pos in acc_info.get('positions', []):
      if float(pos.get('positionAmt', 0)) != 0:
        posiciones_abiertas.add(pos['symbol'])
  except Exception:
    pass

  if posiciones_abiertas:
    print(
        f'ℹ️ Posiciones actualmente abiertas en Testnet:'
        f' {list(posiciones_abiertas)}'
    )

  # 2. Buscar una moneda con precio < $0.05 que NO esté abierta
  tickers = client_directo.futures_symbol_ticker()
  symbol_encontrado = None
  precio_encontrado = 0.0

  for t in tickers:
    s = t['symbol']
    p = float(t['price'])
    if s.endswith('USDT') and 0 < p < 0.05 and s not in posiciones_abiertas:
      symbol_encontrado = s
      precio_encontrado = p
      break

  if not symbol_encontrado:
    print(
        '⚠️ No se encontró una moneda < $0.05 sin posición. Probando con'
        ' DENTUSDT...'
    )
    symbol_encontrado = 'DENTUSDT'
    ticker = client_directo.futures_symbol_ticker(symbol=symbol_encontrado)
    precio_encontrado = float(ticker['price'])

  symbol = symbol_encontrado
  precio_actual = precio_encontrado

  print(
      f'🎯 Nueva moneda seleccionada: {symbol} (Precio actual:'
      f' ${precio_actual:.8f})'
  )

  # 3. Calculamos TP (2% arriba) y SL (1% abajo)
  sl_price = precio_actual * 0.99
  tp_price = precio_actual * 1.02

  print(f'🎯 TP Objetivo: ${tp_price:.8f}')
  print(f'🛑 SL Objetivo: ${sl_price:.8f}\n')

  # 4. Ejecutar la orden en la nueva moneda
  exito = order_manager.ejecutar_orden_compra(
      symbol=symbol,
      precio_entrada=precio_actual,
      stop_loss=sl_price,
      take_profit=tp_price,
      margen_usdt=11,  # $11 USDT x 5x = $55 USDT nocional
      apalancamiento=5,
  )

  if exito:
    print(
        f'\n✅ TEST EXITOSO: Se abrió la posición en {symbol} y sus TP/SL'
        ' quedaron vinculados correctamente.'
    )
  else:
    print(
        f'\n❌ TEST FALLIDO: Ocurrió un problema con la orden en {symbol}.'
    )


if __name__ == '__main__':
  probar_moneda_micro_precio()