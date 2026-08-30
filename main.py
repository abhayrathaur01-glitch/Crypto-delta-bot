import asyncio
import json
import websockets
import aiohttp
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Delta WebSocket Bot is running successfully!")

    def log_message(self, format, *args):
        return

def run_dummy_server():
    server = HTTPServer(('0.0.0.0', 10000), DummyServer)
    server.serve_forever()

TELEGRAM_BOT_TOKEN = "8739623680:AAFU7b7mIHp8nNeN37TClUsHrIjcF1Fzt98"
TELEGRAM_CHAT_ID = "-1004473153244"
WS_URL = "wss://socket.delta.exchange"

SYMBOLS = [
    "BTCUSD", "ETHUSD", "CRCLXUSD", "PAXGUSD",  
    "AAVEUSD", "NVDAXUSD", "TSLAXUSD", "SPCXXUSD",  
    "BNBUSD", "SNDKBUSD", "MRBLBUSD", "MSTRBUSD"
]

TF_CHANNELS = {
    "15m": "candlestick_15m",
    "1h": "candlestick_1h",
    "1w": "candlestick_1w"
}

last_alerted_candles = {}

async def send_telegram_alert(session, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        async with session.post(url, json=payload, timeout=10) as resp:
            await resp.text()
    except Exception as e:
        print(f"Telegram Alert Error: {e}", flush=True)

async def fetch_historical_closes(session, symbol, resolution):
    url = f"https://api.delta.exchange/v2/history/candles?resolution={resolution}&symbol={symbol}"
    try:
        async with session.get(url, timeout=8) as response:
            res = await response.json()
            if "result" in res and res["result"]:
                candles = res["result"]
                if len(candles) >= 200:
                    if candles[0].get('time', 0) > candles[-1].get('time', 0):
                        candles.reverse()
                    return [float(c['close']) for c in candles]
    except Exception:
        pass
    return []

async def run_websocket_bot():
    async with aiohttp.ClientSession() as session:
        await send_telegram_alert(session, "🚀 *Delta WebSocket Raw Monitor is Online!*")
        
        ema_cache = {}
        print("Fetching initial historical data for EMA calculation...", flush=True)
        for symbol in SYMBOLS:
            for tf in ["15m", "1h", "1w"]:
                closes = await fetch_historical_closes(session, symbol, tf)
                ema_cache[f"{symbol}_{tf}"] = closes
        print("Initialization complete. Connecting to WebSocket stream...", flush=True)

        while True:
            try:
                async with websockets.connect(WS_URL) as websocket:
                    channels_list = []
                    for tf_key, channel_name in TF_CHANNELS.items():
                        channels_list.append({"name": channel_name, "symbols": SYMBOLS})

                    subscribe_message = {
                        "type": "subscribe",
                        "payload": {"channels": channels_list}
                    }
                    await websocket.send(json.dumps(subscribe_message))
                    print("Successfully subscribed to Delta WebSocket channels.", flush=True)

                    async for message in websocket:
                        data = json.loads(message)
                        
                        # Print every incoming socket message structure to verify in Render logs
                        print(f"RAW MSG RECEIVED: {str(data)[:150]}", flush=True)
                        
                        if "type" in data and data["type"].startswith("candlestick_"):
                            ch_type = data["type"]
                            tf = ""
                            if ch_type == "candlestick_15m": tf = "15m"
                            elif ch_type == "candlestick_1h": tf = "1h"
                            elif ch_type == "candlestick_1w": tf = "1w"
                            
                            if not tf:
                                continue

                            symbol = data.get("symbol")
                            if not symbol or symbol not in SYMBOLS:
                                continue

                            is_completed = data.get("completed", True)
                            if not is_completed:
                                continue

                            candle_time = data.get("time") or data.get("candle_start_time")
                            cache_key = f"{symbol}_{tf}"
                            
                            if last_alerted_candles.get(cache_key) == candle_time:
                                continue

                            open_price = float(data['open'])
                            high_price = float(data['high'])
                            low_price = float(data['low'])
                            close_price = float(data['close'])

                            closes_list = ema_cache.get(cache_key, [])
                            if len(closes_list) < 200:
                                continue
                            
                            closes_list.append(close_price)
                            k = 2.0 / (200 + 1)
                            ema_val = closes_list[0]
                            for price in closes_list[1:]:
                                ema_val = (price * k) + (ema_val * (1 - k))

                            body_min = min(open_price, close_price)
                            body_max = max(open_price, close_price)

                            print(f"[{symbol} {tf}] Closed | High: {high_price}, Low: {low_price}, EMA: {round(ema_val, 2)}", flush=True)

                            # BUY Setup: Wick touches/crosses below EMA, body closes above EMA
                            if low_price <= ema_val and body_min > ema_val:
                                last_alerted_candles[cache_key] = candle_time
                                msg = (f"🚨 *DELTA REVERSAL ALERT (BUY)* 🚨\n\n"
                                       f"📌 *Symbol*: {symbol}\n"
                                       f"⏱ *Timeframe*: {tf}\n"
                                       f"🔹 *Reason*: 200 EMA Wick Rejection!\n"
                                       f"📉 *EMA 200*: {round(ema_val, 2)}")
                                await send_telegram_alert(session, msg)

                            # SELL Setup: Wick touches/crosses above EMA, body closes below EMA
                            elif high_price >= ema_val and body_max < ema_val:
                                last_alerted_candles[cache_key] = candle_time
                                msg = (f"🚨 *DELTA REVERSAL ALERT (SELL)* 🚨\n\n"
                                       f"📌 *Symbol*: {symbol}\n"
                                       f"⏱ *Timeframe*: {tf}\n"
                                       f"🔹 *Reason*: 200 EMA Wick Rejection!\n"
                                       f"📈 *EMA 200*: {round(ema_val, 2)}")
                                await send_telegram_alert(session, msg)

            except Exception as e:
                print(f"WebSocket Error: {e}. Reconnecting in 5 seconds...", flush=True)
                await asyncio.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(run_websocket_bot())
