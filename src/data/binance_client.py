# ============================================================
# CLIENTE BINANCE - CAZADOR DINÁMICO DE GANADORES + WEBSOCKETS
# ============================================================

import pandas as pd
import time
import sys
import os
from binance import ThreadedWebsocketManager
from binance.client import Client

DIRECTORIO_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DIRECTORIO_RAIZ not in sys.path:
    sys.path.insert(0, DIRECTORIO_RAIZ)

from config.settings import (
    BINANCE_API_KEY,
    BINANCE_SECRET_KEY,
    BINANCE_TESTNET,
    TOP_A_ESCANEAR,
    RANGO_ENTRADA_MIN,
    RANGO_ENTRADA_MAX,
    VOLUMEN_MINIMO_USDT,
    TIMEFRAME,
    PROXY_CONFIG
)

class BinanceDynamicWSClient:
    def __init__(self):
        self.testnet = BINANCE_TESTNET
        client_kwargs = {'testnet': self.testnet}
        
        # ✅ FORZAR PROXY A NIVEL DE SISTEMA Y SESIÓN PARA FUTURES
        if PROXY_CONFIG:
            proxy_url = PROXY_CONFIG.get('https') or PROXY_CONFIG.get('http')
            if proxy_url:
                # Inyectar al entorno para que Futures API no lo esquive
                os.environ['HTTP_PROXY'] = proxy_url
                os.environ['HTTPS_PROXY'] = proxy_url
                
                client_kwargs['requests_params'] = {
                    'proxies': {
                        'http': proxy_url,
                        'https': proxy_url
                    }
                }

        self.client_rest = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY, **client_kwargs)
        self.twm = None
        self.velas_memoria = {}
        self.sockets_activos = set()

    def escanear_top_ganadores(self):
        """Escanea Binance Futures buscando monedas en pleno PUMP (5% a 50%)"""
        try:
            tickers = self.client_rest.futures_ticker()
            candidatos = []
            
            for t in tickers:
                symbol = t['symbol']
                if not symbol.endswith('USDT'):
                    continue
                
                pct_change = float(t['priceChangePercent'])
                quote_volume = float(t['quoteVolume'])
                
                if RANGO_ENTRADA_MIN <= pct_change <= RANGO_ENTRADA_MAX and quote_volume >= VOLUMEN_MINIMO_USDT:
                    candidatos.append({
                        'symbol': symbol,
                        'change': pct_change,
                        'volume': quote_volume
                    })
            
            candidatos = sorted(candidatos, key=lambda x: x['change'], reverse=True)[:TOP_A_ESCANEAR]
            simbolos = [c['symbol'] for c in candidatos]
            print(f"🔥 Escáner halló {len(simbolos)} ganadores en explosión (+{RANGO_ENTRADA_MIN}% a +{RANGO_ENTRADA_MAX}%).")
            return simbolos
            
        except Exception as e:
            print(f"❌ Error escaneando top ganadores: {e}")
            return []

    def _cargar_historial_inicial(self, symbol, limit=100):
        try:
            klines = self.client_rest.futures_klines(symbol=symbol, interval=TIMEFRAME, limit=limit)
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            columnas_num = [
                'open', 'high', 'low', 'close', 'volume',
                'quote_asset_volume', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume'
            ]
            df[columnas_num] = df[columnas_num].astype(float)
            
            return df
        except Exception as e:
            print(f"❌ Error cargando historial de {symbol}: {e}")
            return pd.DataFrame()
        
    def _procesar_mensaje_kline(self, msg):
        if msg.get('e') == 'kline':
            kline = msg['k']
            symbol = kline['s']
            
            nueva_vela = {
                'timestamp': pd.to_datetime(kline['t'], unit='ms'),
                'open': float(kline['o']),
                'high': float(kline['h']),
                'low': float(kline['l']),
                'close': float(kline['c']),
                'volume': float(kline['v'])
            }

            df = self.velas_memoria.get(symbol, pd.DataFrame())
            if not df.empty:
                if df.iloc[-1]['timestamp'] == nueva_vela['timestamp']:
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df.iat[-1, df.columns.get_loc(col)] = nueva_vela[col]
                else:
                    df = pd.concat([df, pd.DataFrame([nueva_vela])], ignore_index=True)
                    if len(df) > 300:
                        df = df.iloc[-300:].reset_index(drop=True)
                self.velas_memoria[symbol] = df

    def actualizar_conector_websocket(self, simbolos):
        """Abre streaming WebSocket solo para las monedas que están explotando"""
        if self.twm is None:
            self.twm = ThreadedWebsocketManager(
                api_key=BINANCE_API_KEY,
                api_secret=BINANCE_SECRET_KEY,
                testnet=self.testnet
            )
            self.twm.start()

        for symbol in simbolos:
            if symbol not in self.sockets_activos:
                self.velas_memoria[symbol] = self._cargar_historial_inicial(symbol)
                
                # ✅ PAUSA DE RITMO: Evita ráfagas demasiado rápidas al servidor
                time.sleep(0.15)
                
                self.twm.start_kline_futures_socket(
                    callback=self._procesar_mensaje_kline,
                    symbol=symbol,
                    interval=TIMEFRAME
                )
                self.sockets_activos.add(symbol)

    def obtener_velas(self, symbol):
        return self.velas_memoria.get(symbol, pd.DataFrame()).copy()

    def detener(self):
        if self.twm:
            self.twm.stop()
            print("🛑 WebSockets detenidos.")


_cliente_ws = None

def get_client_ws():
    global _cliente_ws
    if _cliente_ws is None:
        _cliente_ws = BinanceDynamicWSClient()
    return _cliente_ws