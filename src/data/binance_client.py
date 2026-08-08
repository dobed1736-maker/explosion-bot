import pandas as pd
import numpy as np
from binance.client import Client
from binance.exceptions import BinanceAPIException
import sys
import os
import time
from datetime import datetime, timedelta

# Agregar raíz del proyecto al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import (
    BINANCE_API_KEY,
    BINANCE_SECRET_KEY,
    BINANCE_TESTNET,
    TIMEFRAME,
    PROXY_CONFIG  # ← Leemos el proxy configurado en settings.py
)

class BinanceClient:
    """Cliente para interactuar con la API de Binance"""
    
    def __init__(self):
        self.client = None
        self.conectar()
    
    def conectar(self):
        """Establece conexión con Binance usando el Proxy residencial/ISP"""
        try:
            req_params = {'timeout': 30}
            
            # Solo pasamos el proxy si realmente está configurado en .env
            if PROXY_CONFIG:
                req_params['proxies'] = PROXY_CONFIG
                print("🛡️ Usando Proxy para Binance desde Webshare...")

            if BINANCE_TESTNET:
                self.client = Client(
                    BINANCE_API_KEY,
                    BINANCE_SECRET_KEY,
                    testnet=True,
                    requests_params=req_params
                )
                self.client.FUTURES_URL = 'https://testnet.binancefuture.com/fapi'
                print("🧪 Conectado a BINANCE FUTURES (TESTNET)")
            else:
                self.client = Client(
                    BINANCE_API_KEY,
                    BINANCE_SECRET_KEY,
                    requests_params=req_params
                )
                print("⚡ Conectado a BINANCE REAL")
                
        except Exception as e:
            print(f"❌ Error conectando a Binance: {e}")
            self.client = None

    def obtener_velas(self, symbol, intervalo=TIMEFRAME, limit=100):
        """Obtiene velas históricas para un símbolo"""
        try:
            if not self.client:
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
            for col in ['open', 'high', 'low', 'close', 'volume', 'taker_buy_base_asset_volume']:
                df[col] = df[col].astype(float)
                
            return df
            
        except Exception as e:
            print(f"❌ Error obteniendo velas de {symbol}: {e}")
            return pd.DataFrame()

    def obtener_top_ganadores(self, limit=50):
        """Obtiene las monedas con mayor volumen/variación"""
        try:
            if not self.client:
                self.conectar()
                
            tickers = self.client.futures_ticker()
            df = pd.DataFrame(tickers)
            df['priceChangePercent'] = df['priceChangePercent'].astype(float)
            df['quoteVolume'] = df['quoteVolume'].astype(float)
            
            # Filtrar solo pares con USDT
            df = df[df['symbol'].str.endswith('USDT')]
            
            # Ordenar por cambio porcentual de 24h
            top = df.sort_values(by='priceChangePercent', ascending=False).head(limit)
            return top[['symbol', 'priceChangePercent', 'quoteVolume', 'lastPrice']].to_dict('records')
            
        except Exception as e:
            print(f"❌ Error obteniendo top ganadores: {e}")
            return []

    def obtener_order_book(self, symbol, limit=20):
        """Obtiene el libro de órdenes"""
        try:
            if not self.client:
                self.conectar()
            depth = self.client.futures_order_book(symbol=symbol, limit=limit)
            return depth
        except Exception as e:
            print(f"❌ Error obteniendo order book de {symbol}: {e}")
            return {}

    def obtener_funding_rate(self, symbol):
        """Obtiene la tasa de financiación actual"""
        try:
            if not self.client:
                self.conectar()
            res = self.client.futures_funding_rate(symbol=symbol, limit=1)
            if res:
                return float(res[0]['fundingRate'])
            return 0.0
        except Exception as e:
            print(f"❌ Error obteniendo funding rate de {symbol}: {e}")
            return 0.0


# Instancia global
_binance_client = None

def get_client():
    global _binance_client
    if _binance_client is None:
        _binance_client = BinanceClient()
    return _binance_client

def obtener_datos(symbol, intervalo=TIMEFRAME, limit=100):
    client = get_client()
    return client.obtener_velas(symbol, intervalo, limit)

def obtener_ganadores(limit=50):
    client = get_client()
    return client.obtener_top_ganadores(limit)

def obtener_order_book(symbol, limit=20):
    client = get_client()
    return client.obtener_order_book(symbol, limit)

def obtener_funding_rate(symbol):
    client = get_client()
    return client.obtener_funding_rate(symbol)