import os, time, threading, logging
from datetime import datetime
import pytz
import yfinance as yf
import pandas as pd
import requests
from flask import Flask

# --- CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WIB = pytz.timezone("Asia/Jakarta")

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot XAUUSD Aktif 24/7 di Render"

last_signal = None
last_price = 0

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        logging.error("BOT_TOKEN / CHAT_ID belum di-set di Render!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
        logging.info(f"Sent: {msg}")
    except Exception as e:
        logging.error(f"Gagal kirim Telegram: {e}")

def get_signal():
    global last_signal
    try:
        data = yf.download("GC=F", period="2d", interval="15m", progress=False, auto_adjust=True)
        if len(data) < 50:
            return None, 0
        
        # FIX: ambil Close dengan benar
        if isinstance(data['Close'], pd.DataFrame):
            close = data['Close'].iloc[:, 0]
        else:
            close = data['Close']
            
        close = close.dropna()
        if len(close) < 50:
            return None, 0
            
        ema_fast = close.ewm(span=20).mean().iloc[-1]
        ema_slow = close.ewm(span=50).mean().iloc[-1]
        price = float(close.iloc[-1])

        delta = close.diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14).mean()
        loss = -delta.where(delta < 0, 0).ewm(alpha=1/14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_now = float(rsi.iloc[-1])

        signal = None
        if ema_fast > ema_slow and 50 < rsi_now < 75:
            signal = "BUY"
        elif ema_fast < ema_slow and 25 < rsi_now < 50:
            signal = "SELL"

        return signal, price
    except Exception as e:
        logging.error(f"Error get data: {e}")
        return None, 0

def bot_loop():
    global last_signal, last_price
    send_telegram("✅ *Bot XAUUSD Baru Aktif di Render*\nMonitoring tiap 5 menit (Senin-Jumat 05:00-23:00 WIB)")
    while True:
        now = datetime.now(WIB)
        # Cek jadwal: Senin=0 ... Jumat=4, jam 5-23 WIB
        if now.weekday() < 5 and 5 <= now.hour < 23:
            signal, price = get_signal()
            logging.info(f"{now} Price: {price} Signal: {signal}")
            
            if signal and signal != last_signal:
                # Cek perubahan harga signifikan biar gak spam
                if abs(price - last_price) > 0.5 or last_signal is None:
                    msg = (
                        f"🔔 *SINYAL XAUUSD*\n\n"
                        f"Pair: `XAUUSD`\n"
                        f"Aksi: *{signal}*\n"
                        f"Harga: `${price:.2f}`\n"
                        f"Waktu: {now.strftime('%d %b %H:%M WIB')}\n\n"
                        f"TF: M15 | EMA20/50 + RSI"
                    )
                    send_telegram(msg)
                    last_signal = signal
                    last_price = price
        else:
            logging.info(f"Tidur - di luar jam trading: {now}")

        time.sleep(300) # 5 menit

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
