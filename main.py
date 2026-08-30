import time
import requests
import pandas as pd
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Dummy HTTP Server so Render Web Service stays alive
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

    def log_message(self, format, *args):
        return  # Silence HTTP server logs

def run_dummy_server():
    server = HTTPServer(('0.0.0.0', 10000), DummyServer)
    server.serve_forever()

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = "8739623680:AAFu7b7mIHp8nNeN37TClUsHrIjcF1Fzt98"
TELEGRAM_CHAT_ID = "-549118591"

SYMBOLS = [
    "BTCUSD", "ETHUSD", "CRCLXUSD", "PAXGUSD", 
    "AAVEUSD", "NVDAXUSD", "TSLAXUSD", "SPCXXUSD", 
    "BNBUSD", "SNDKBUSD", "MRBLBUSD", "MSTRBUSD"
]

TIMEFRAMES = ["15m", "1h", "1w"]

TIMEFRAME_MAP = {
    "15m": "15m",
    "1h": "1h",
    "1w": "1w"
}

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Alert Error: {e}", flush=True)

def get_delta_candles(symbol, timeframe):
    url = f"https://api.delta.exchange/v2/history/candles?resolution={TIMEFRAME_MAP[timeframe]}&symbol={symbol}"
    try:
        res = requests.get(url).json()
        if "result" in res:
            df = pd.DataFrame(res["result"])
            df = df.iloc[::-1].reset_index(drop=True)
            df['close'] = df['close'].astype(float)
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            return df
    except Exception as e:
        print(f"Error fetching data for {symbol} {timeframe}: {e}", flush=True)
    return None

def check_strategy():
    print("🔍 Scanning Delta Exchange markets (15m, 1h, 1w)...", flush=True)
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            df = get_delta_candles(symbol, tf)
            if df is None or len(df) < 200:
                continue

            df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()

            last_candle = df.iloc[-2] 
            open_price = last_candle['open']
            close_price = last_candle['close']
            high_price = last_candle['high']
            low_price = last_candle['low']
            ema = last_candle['ema200']

            body_min = min(open_price, close_price)
            body_max = max(open_price, close_price)

            # Bullish Rejection
            if low_price <= ema and body_min > ema:
                msg = (f"🚨 *DELTA REVERSAL ALERT (BUY)* 🚨\n\n"
                       f"📌 *Symbol*: {symbol}\n"
                       f"⏱ *Timeframe*: {tf}\n"
                       f"🔹 *Reason*: 200 EMA Wick Rejection!\n"
                       f"📉 *EMA 200*: {round(ema, 2)}")
                print(msg, flush=True)
                send_telegram_alert(msg)

            # Bearish Rejection
            elif high_price >= ema and body_max < ema:
                msg = (f"🚨 *DELTA REVERSAL ALERT (SELL)* 🚨\n\n"
                       f"📌 *Symbol*: {symbol}\n"
                       f"⏱ *Timeframe*: {tf}\n"
                       f"🔹 *Reason*: 200 EMA Wick Rejection!\n"
                       f"📈 *EMA 200*: {round(ema, 2)}")
                print(msg, flush=True)
                send_telegram_alert(msg)

if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()
    send_telegram_alert("🚀 *Delta Scanner Bot is Online & Active!*")
    
    while True:
        check_strategy()
        time.sleep(60)
