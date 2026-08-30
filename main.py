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
        await send_telegram_alert(session, "🚀 *Delta WebSocket Bot is Online!*")
        
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
                    # Delta Exchange standard subscription format payload
                    subscribe_message = {
                        "type": "subscribe",
                        "payload": {
                            "channels": [
                                {
                                    "name": "v2/ticker",
                                    "symbols": SYMBOLS
                                }
                            ]
                        }
                    }
                    await websocket.send(json.dumps(subscribe_message))
                    print("Successfully subscribed to Delta v2/ticker stream.", flush=True)

                    async for message in websocket:
                        data = json.loads(message)
                        
                        # Print raw incoming messages to verify stream health
                        print(f"RAW MSG: {str(data)[:150]}", flush=True)

            except Exception as e:
                print(f"WebSocket Error: {e}. Reconnecting in 5 seconds...", flush=True)
                await asyncio.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(run_websocket_bot())
