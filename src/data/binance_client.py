# ============================================================
# CLIENTE DE BINANCE (CON CONTROL ROBUSTO DE RATE LIMIT)
# ============================================================

import sys
import os
import time
import random
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Agregar la raíz del proyecto al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import (
    BINANCE_API_KEY,
    BINANCE_SECRET_KEY,
    BINANCE_TESTNET
)


class BinanceClient:
    """Cliente orquestador para interactuar con la API de Binance Futures"""
    
    def __init__(self):
        self.client = None
        self.conectar()
    
    def conectar(self):
        """Establece la conexión con la API de Binance"""
        try:
            if BINANCE_TESTNET:
                self.client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY, testnet=True)
                print("✅ Conectado a Binance Testnet")
            else:
                self.client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
                print("⚠️ Conectado a Binance MAINNET")
            
            self.client.ping()
            return True
        except Exception as e:
            print(f"❌ Error conectando a Binance: {e}")
            return False
    
    def obtener_velas(self, symbol, intervalo='5m', limit=1000):
        """
        Obtiene velas históricas con reintentos inteligentes en caso de Rate Limit (-1003)
        """
        max_retries = 3
        for intento in range(max_retries):
            try:
                if self.client is None:
                    self.conectar()
                
                klines = self.client.futures_klines(
                    symbol=symbol,
                    interval=intervalo,
                    limit=limit
                )
                
                df = pd.DataFrame(klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_asset_volume', 'number_of_trades',
                    'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
                ])
                
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                df = df.sort_values('timestamp')
                
                return df
                
            except Exception as e:
                err_msg = str(e).lower()
                # Captura aviso de saturación o baneo temporal de API
                if "1003" in err_msg or "too many" in err_msg or "429" in err_msg or "banned" in err_msg:
                    wait_time = (2 ** intento) + random.uniform(1.0, 3.0)
                    print(f"⚠️ Rate limit en {symbol}. Pausando {wait_time:.1f}s antes del reintento {intento + 1}/{max_retries}...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ Error obteniendo velas de {symbol}: {e}")
                    return pd.DataFrame()
                    
        return pd.DataFrame()

    def obtener_precio_actual(self, symbol):
        """Obtiene el último precio registrado de una moneda"""
        try:
            if self.client is None:
                self.conectar()
            ticker = self.client.futures_ticker(symbol=symbol)
            return float(ticker['lastPrice'])
        except Exception as e:
            print(f"❌ Error obteniendo precio de {symbol}: {e}")
            return None

    def obtener_top_ganadores(self, limit=50):
        """Obtiene el listado de las monedas de Futuros USDT con mayor volumen/movimiento"""
        try:
            if self.client is None:
                self.conectar()
            
            tickers = self.client.futures_ticker()
            candidatos = []
            
            for t in tickers:
                symbol = t['symbol']
                # Filtrar solo pares contra USDT válidos
                if symbol.endswith('USDT') and not symbol.startswith('LD'):
                    volumen = float(t.get('quoteVolume', 0))
                    precio = float(t.get('lastPrice', 0))
                    cambio = float(t.get('priceChangePercent', 0))
                    
                    if volumen > 0 and precio > 0:
                        candidatos.append({
                            'symbol': symbol,
                            'volumen': volumen,
                            'precio': precio,
                            'cambio_24h': cambio
                        })
            
            # Ordenar por volumen descendente
            candidatos.sort(key=lambda x: x['volumen'], reverse=True)
            return candidatos[:limit]
            
        except Exception as e:
            print(f"❌ Error obteniendo top ganadores: {e}")
            return []

    def obtener_order_book(self, symbol, limit=10):
        """Obtiene el libro de órdenes"""
        try:
            if self.client is None:
                self.conectar()
            return self.client.futures_order_book(symbol=symbol, limit=limit)
        except Exception as e:
            print(f"❌ Error obteniendo order book de {symbol}: {e}")
            return {}

    def obtener_funding_rate(self, symbol):
        """Obtiene la tasa de financiación actual (Funding Rate)"""
        try:
            if self.client is None:
                self.conectar()
            res = self.client.futures_funding_rate(symbol=symbol, limit=1)
            if res:
                return float(res[0]['fundingRate'])
            return 0.0
        except Exception as e:
            print(f"❌ Error obteniendo funding rate de {symbol}: {e}")
            return 0.0


# ============================================================
# INSTANCIA GLOBAL Y FUNCIONES HELPER
# ============================================================

_cliente = None

def get_client():
    global _cliente
    if _cliente is None:
        _cliente = BinanceClient()
    return _cliente

def obtener_datos(symbol, intervalo='5m', limit=1000):
    client = get_client()
    return client.obtener_velas(symbol, intervalo, limit)

def obtener_ganadores(limit=50):
    client = get_client()
    return client.obtener_top_ganadores(limit=limit)

def obtener_order_book(symbol, limit=10):
    client = get_client()
    return client.obtener_order_book(symbol, limit=limit)

def obtener_funding_rate(symbol):
    client = get_client()
    return client.obtener_funding_rate(symbol)


if __name__ == "__main__":
    print("="*50)
    print("🧪 Probando conexión y cliente de Binance")
    print("="*50)
    client = get_client()
    df = client.obtener_velas('BTCUSDT', '5m', 100)
    
    if not df.empty:
        print("\n✅ Datos de prueba obtenidos correctamente:")
        print(df.head(3))
        print(f"\n📈 Último precio BTCUSDT: ${df['close'].iloc[-1]:,.2f}")
    else:
        print("\n❌ No se pudieron obtener datos de prueba.")