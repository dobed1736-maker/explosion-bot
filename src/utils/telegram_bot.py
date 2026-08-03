# ============================================================
# TELEGRAM BOT - EXPLOSION BOT
# ============================================================

import requests
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def enviar_telegram(mensaje):
    """
    Envía un mensaje por Telegram
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram no configurado (sin token o chat_id)")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': mensaje,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            print("📱 Mensaje enviado a Telegram")
            return True
        else:
            print(f"❌ Error enviando a Telegram: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error enviando a Telegram: {e}")
        return False


def enviar_señal_telegram(symbol, tipo, probabilidad, precio, tp1, tp2, tp3, sl):
    """
    Envía una señal de trading formateada a Telegram
    """
    mensaje = f"""
💥 <b>EXPLOSION BOT - SEÑAL DE {tipo}</b>

🚀 <b>{symbol}</b>
📊 Probabilidad: {probabilidad:.2%}

💰 Precio entrada: <b>${precio:.4f}</b>
🛑 Stop Loss: ${sl:.4f}
🎯 Take Profit 1: ${tp1:.4f}
🎯 Take Profit 2: ${tp2:.4f}
🎯 Take Profit 3: ${tp3:.4f}

🕐 {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    return enviar_telegram(mensaje)


if __name__ == "__main__":
    print("🧪 Probando Telegram...")
    
    # Probar envío
    enviar_telegram("🧪 Mensaje de prueba desde Explosion Bot")
    
    print("✅ Prueba completada")