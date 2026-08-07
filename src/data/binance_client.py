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
                print("✅ Conectado a Binance Testnet")
            else:
                self.client = Client(
                    BINANCE_API_KEY,
                    BINANCE_SECRET_KEY,
                    requests_params=req_params
                )
                print("⚠️ Conectado a Binance MAINNET (FUTUROS)")
            
            # Verificar conexión con Binance
            self.client.ping()
            print("✅ Conexión verificada exitosamente con Binance")
            return True
            
        except Exception as e:
            print(f"❌ Error conectando a Binance: {e}")
            return False
    
    def obtener_velas(self, symbol, intervalo=TIMEFRAME, limit=500):
        """
        Obtiene velas históricas de Binance
        """
        try:
            if self.client is None:
                self.conectar()
            
            # Obtener velas de FUTUROS
            klines = self.client.futures_klines(
                symbol=symbol,
                interval=intervalo,
                limit=limit
            )
            
            # Convertir a DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Convertir tipos
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
            df['taker_buy_base_asset_volume'] = df['taker_buy_base_asset_volume'].astype(float)
            df['taker_buy_quote_asset_volume'] = df['taker_buy_quote_asset_volume'].astype(float)
            
            # Seleccionar columnas útiles
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                     'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume']]
            
            # Ordenar por tiempo
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            return df
            
        except BinanceAPIException as e:
            print(f"❌ Error de Binance al obtener {symbol}: {e}")
            return pd.DataFrame()
        
        except Exception as e:
            print(f"❌ Error obteniendo datos de {symbol}: {e}")
            return pd.DataFrame()
    
    def obtener_top_ganadores(self, limit=50):
        """
        Obtiene las monedas que más están subiendo en las últimas 24h
        en FUTUROS de Binance (Únicamente Contratos Perpetuos Activos)
        """
        try:
            if self.client is None:
                self.conectar()
            
            # Obtener información oficial de contratos de FUTUROS activos
            exchange_info = self.client.futures_exchange_info()
            # Crear set con únicamente los símbolos que son contratos PERPETUAL y están TRADING
            simbolos_perpetuos = {
                s['symbol'] for s in exchange_info['symbols']
                if s['contractType'] == 'PERPETUAL' and s['status'] == 'TRADING'
            }

            # Obtener tickers de FUTUROS
            tickers = self.client.futures_ticker()
            
            ganadores = []
            for t in tickers:
                symbol = t['symbol']
                
                # 1. Filtro estricto: Debe ser un contrato Perpetuo activo en Binance Futuros
                if symbol not in simbolos_perpetuos:
                    continue

                # 2. Solo pares contra USDT
                if not symbol.endswith('USDT'):
                    continue
                
                # 3. Evitar pares raros o stablecoins
                if 'USDC' in symbol or 'BUSD' in symbol or 'USDT' in symbol[:-4]:
                    continue
                
                try:
                    cambio = float(t['priceChangePercent'])
                    volumen = float(t['quoteVolume'])
                    precio = float(t['lastPrice'])
                    
                    if volumen > 100000:  # $100k mínimo de volumen en 24h
                        ganadores.append({
                            'symbol': symbol,
                            'cambio': cambio,
                            'volumen': volumen,
                            'precio': precio,
                            'high': float(t['highPrice']),
                            'low': float(t['lowPrice'])
                        })
                except (ValueError, KeyError):
                    continue
            
            # Ordenar por cambio (mayor primero)
            ganadores.sort(key=lambda x: x['cambio'], reverse=True)
            
            return ganadores[:limit]
            
        except Exception as e:
            print(f"❌ Error obteniendo ganadores: {e}")
            return []
    
    def obtener_order_book(self, symbol, limit=20):
        """
        Obtiene el order book (profundidad) de una moneda
        """
        try:
            if self.client is None:
                self.conectar()
            
            depth = self.client.futures_order_book(symbol=symbol, limit=limit)
            
            # Calcular volumen de compras y ventas
            bid_volume = sum(float(bid[1]) * float(bid[0]) for bid in depth['bids'])
            ask_volume = sum(float(ask[1]) * float(ask[0]) for ask in depth['asks'])
            
            return {
                'bids': depth['bids'],
                'asks': depth['asks'],
                'bid_volume': bid_volume,
                'ask_volume': ask_volume,
                'imbalance': bid_volume / ask_volume if ask_volume > 0 else 0
            }
            
        except Exception as e:
            print(f"❌ Error obteniendo order book de {symbol}: {e}")
            return None
    
    def obtener_funding_rate(self, symbol):
        """
        Obtiene la tasa de financiación de una moneda en futuros
        """
        try:
            if self.client is None:
                self.conectar()
            
            funding = self.client.futures_funding_rate(symbol=symbol, limit=1)
            
            if funding and len(funding) > 0:
                return float(funding[0]['fundingRate']) * 100
            return 0
            
        except Exception as e:
            print(f"❌ Error obteniendo funding rate de {symbol}: {e}")
            return 0
    
    def obtener_precio_actual(self, symbol):
        """Obtiene el precio actual de un par"""
        try:
            ticker = self.client.futures_ticker(symbol=symbol)
            return float(ticker['lastPrice'])
        except Exception as e:
            print(f"❌ Error obteniendo precio de {symbol}: {e}")
            return None


# ============================================================
# FUNCIONES DE ACCESO RÁPIDO (Singleton)
# ============================================================

_cliente = None

def get_client():
    """Obtiene una instancia única del cliente"""
    global _cliente
    if _cliente is None:
        _cliente = BinanceClient()
    return _cliente

def obtener_datos(symbol, intervalo=TIMEFRAME, limit=500):
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


# ============================================================
# PRUEBA RÁPIDA
# ============================================================

if __name__ == "__main__":
    print("="*50)
    print("🧪 Probando conexión a Binance con Proxy")
    print("="*50)
    
    client = BinanceClient()
    
    # 1. Probar obtener datos de BTC
    print("\n📊 Probando obtener velas...")
    df = client.obtener_velas('BTCUSDT', '5m', 10)
    
    if not df.empty:
        print(f"✅ Datos obtenidos exitosamente: {len(df)} velas")
        print(df[['timestamp', 'close', 'volume']].tail(3))
    else:
        print("❌ No se pudieron obtener datos")
    
    # 2. Probar obtener ganadores
    print("\n🏆 Probando obtener top ganadores...")
    ganadores = client.obtener_top_ganadores(5)
    
    if ganadores:
        print(f"✅ Top ganadores de Futuros:")
        for i, g in enumerate(ganadores, 1):
            print(f"   {i}. {g['symbol']}: {g['cambio']:+.2f}%")
    else:
        print("❌ No se obtuvieron ganadores")
    
    print("\n✅ Prueba completada")