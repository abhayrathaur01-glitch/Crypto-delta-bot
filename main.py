import asyncio
import aiohttp
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
TELEGRAM_BOT_TOKEN = "8739623680:AAFU7b7mIHp8nNeN37TClUsHrIjcF1Fzt98"
TELEGRAM_CHAT_ID = "-1004473153244"

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

# Track last alerted candles to avoid duplicate spam: { (symbol, tf): candle_timestamp }
last_alerted_candles = {}

async def send_telegram_alert(session, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        async with session.post(url, json=payload, timeout=10) as resp:
            await resp.text()
    except Exception as e:
        print(f"Telegram Alert Error: {e}", flush=True)

async def fetch_and_check(session, symbol, tf):
    url = f"https://api.delta.exchange/v2/history/candles?resolution={TIMEFRAME_MAP[tf]}&symbol={symbol}"
    try:
        async with session.get(url, timeout=8) as response:
            res = await response.json()
            if "result" in res and res["result"]:
                df = pd.DataFrame(res["result"])
                if len(df) < 200:
                    return
                df = df.iloc[::-1].reset_index(drop=True)
                df['close'] = df['close'].astype(float)
                df['open'] = df['open'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)

                df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()

                last_candle = df.iloc[-2]  
                open_price = last_candle['open']
                close_price = last_candle['close']
                high_price = last_candle['high']
                low_price = last_candle['low']
                ema = last_candle['ema200']
                
                candle_time = last_candle.get('time', len(df) - 2)
                cache_key = f"{symbol}_{tf}"
                
                if last_alerted_candles.get(cache_key) == candle_time:
                    return

                body_min = min(open_price, close_price)
                body_max = max(open_price, close_price)

                # Bullish Rejection
                if low_price <= ema and body_min > ema:
                    last_alerted_candles[cache_key] = candle_time
                    msg = (f"🚨 *DELTA REVERSAL ALERT (BUY)* 🚨\n\n"
                           f"📌 *Symbol*: {symbol}\n"
                           f"⏱ *Timeframe*: {tf}\n"
                           f"🔹 *Reason*: 200 EMA Wick Rejection!\n"
                           f"📉 *EMA 200*: {round(ema, 2)}")
                    print(msg, flush=True)
                    await send_telegram_alert(session, msg)

                # Bearish Rejection
                elif high_price >= ema and body_max < ema:
                    last_alerted_candles[cache_key] = candle_time
                    msg = (f"🚨 *DELTA REVERSAL ALERT (SELL)* 🚨\n\n"
                           f"📌 *Symbol*: {symbol}\n"
                           f"⏱ *Timeframe*: {tf}\n"
                           f"🔹 *Reason*: 200 EMA Wick Rejection!\n"
                           f"📈 *EMA 200*: {round(ema, 2)}")
                    print(msg, flush=True)
                    await send_telegram_alert(session, msg)
    except Exception:
        pass  # Silently handle network timeouts to prevent loop breakage

async def check_strategy_async(session):
    print("🔍 Scanning Delta Exchange markets (15m, 1h, 1w) [Zero-Lag Async]...", flush=True)
    start_time = asyncio.get_event_loop().time()
    
    tasks = [fetch_and_check(session, symbol, tf) for symbol in SYMBOLS for tf in TIMEFRAMES]
    await asyncio.gather(*tasks)
    
    elapsed = asyncio.get_event_loop().time() - start_time
    print(f"⚡ Scan completed in {round(elapsed, 2)} seconds.", flush=True)

async def main():
    async with aiohttp.ClientSession() as session:
        await send_telegram_alert(session, "🚀 *Delta Scanner Zero-Lag Bot is Online & Active!*")
        while True:
            loop_start = asyncio.get_event_loop().time()
            
            await check_strategy_async(session)
            
            # Precise drift-free timing calculation
            elapsed = asyncio.get_event_loop().time() - loop_start
            sleep_time = max(0.5, 60.0 - elapsed)
            await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(main())
