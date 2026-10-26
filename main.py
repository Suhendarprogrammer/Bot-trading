import os, time, threading, logging
from datetime import datetime
import pytz
import yfinance as yf
import pandas as pd
import requests
from flask import Flask

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
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        logging.error(e)

def get_signal():
    try:
        # pakai Ticker biar gak kena bug DataFrame
        ticker = yf.Ticker("GC=F")
        data = ticker.history(period="2d", interval="15m", auto_adjust=True)
        if len(data) < 50:
            return None, 0
        
        close = data['Close'].dropna()
        ema_fast = float(close.ewm(span=20).mean().iloc[-1])
        ema_slow = float(close.ewm(span=50).mean().iloc[-1])
        price = float(close.iloc[-1])

        delta = close.diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14).mean()
        loss = -delta.where(delta < 0, 0).ewm(alpha=1/14).mean()
        rsi_now = float(100 - (100 / (1 + (gain/loss)))).iloc[-1]

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
    while True:
        now = datetime.now(WIB)
        if now.weekday() < 5 and 5 <= now.hour < 23:
            signal, price = get_signal()
            logging.info(f"{now} Price: {price} Signal: {signal}")
            if signal and signal != last_signal:
                if abs(price - last_price) > 0.5 or last_signal is None:
                    msg = f"🔔 *SINYAL XAUUSD*\n\nAksi: *{signal}*\nHarga: `${price:.2f}`\nWaktu: {now.strftime('%H:%M WIB')}"
                    send_telegram(msg)
                    last_signal = signal
                    last_price = price
        time.sleep(300)

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
