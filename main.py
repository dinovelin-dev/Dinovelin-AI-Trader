import os
import time
import json
import ccxt
import openai
import telebot
import pandas as pd
import pandas_ta as ta
import threading
from dotenv import load_dotenv

# --- Load Konfigurasi ---
load_dotenv()
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ID_COMMANDER = os.environ.get('ID_COMMANDER')

bot = telebot.TeleBot(TELEGRAM_TOKEN)
exchange = ccxt.binance({
    'apiKey': os.environ.get('BINANCE_API_KEY'),
    'secret': os.environ.get('BINANCE_SECRET'),
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})
client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# --- FUNGSI PENDUKUNG ---
def get_market_snapshot():
    try:
        bars = exchange.fetch_ohlcv('BTC/USDT', timeframe='15m', limit=100)
        df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
        df.ta.mfi(length=14, append=True)
        df.ta.adx(length=14, append=True)
        curr = df.iloc[-1]
        return {
            "price": float(curr['close']),
            "mfi": float(curr['MFI_14']),
            "adx": float(curr['ADX_14']),
            "volume": float(curr['volume'])
        }
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

# --- LOGIKA TRADING OTOMATIS (RUNNING IN BACKGROUND) ---
def autonomous_trading_loop():
    print("🛰️ Autonomous Trading Engine Active...")
    while True:
        snapshot = get_market_snapshot()
        if snapshot:
            prompt = f"Analisis data BTC/USDT: {snapshot}. Berikan keputusan trading dalam format JSON: {{\"action\": \"BUY/SELL/WAIT\", \"reason\": \"...\", \"confidence\": 0-100}}"
            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "system", "content": "Anda adalah Senior Quant Trader."},
                              {"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                decision = json.loads(response.choices[0].message.content)
                
                if decision['confidence'] >= 85:
                    msg = f"🤖 **AI SIGNAL ({decision['action']})**\nConfidence: {decision['confidence']}%\nReason: {decision['reason']}"
                    bot.send_message(ID_COMMANDER, msg)
                    # Tambahkan perintah eksekusi binance di sini jika ingin otomatis
            except Exception as e:
                print(f"AI Loop Error: {e}")
        
        time.sleep(900) # Cek setiap 15 menit

# --- LOGIKA CHAT INTERAKTIF ---
@bot.message_handler(func=lambda message: True)
def handle_chat(message):
    if str(message.from_user.id) != ID_COMMANDER:
        return

    bot.send_chat_action(message.chat.id, 'typing')
    snapshot = get_market_snapshot() # Ambil data terbaru saat user bertanya
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Anda adalah Agen Dinovelin. Anda ahli trading BTC/USDT. Jawab dengan gaya profesional namun santai."},
                {"role": "user", "content": f"Data Market Saat Ini: {snapshot}\n\nPertanyaan User: {message.text}"}
            ]
        )
        bot.reply_to(message, response.choices[0].message.content)
    except Exception as e:
        bot.reply_to(message, f"Aduh, otak saya lagi hang: {e}")

# --- MENJALANKAN KEDUA SISTEM ---
if __name__ == "__main__":
    # Jalankan loop trading di thread terpisah
    threading.Thread(target=autonomous_trading_loop, daemon=True).start()
    
    # Jalankan polling telegram (Chat) di thread utama
    print("💬 Interactive Chat Active...")
    bot.infinity_polling()
