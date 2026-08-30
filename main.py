import asyncio
import aiohttp
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Delta REST Bot is running successfully!")

    def log_message(self, format, *args):
        return

def run_dummy_server():
    server = HTTPServer(('0.0.0.0', 10000), DummyServer)
    server.serve_forever()

TELEGRAM_BOT_TOKEN = "8739623680:AAFU7b7mIHp8nNeN37TClUsHrIjcF1Fzt98"
TELEGRAM_CHAT_ID = "-1004473153244"

SYMBOLS = [
    "BTCUSD", "ETHUSD", "CRCLXUSD", "PAXGUSD",  
    "AAVEUSD", "NVDAXUSD", "TSLAXUSD", "SPCXXUSD",  
    "BNBUSD", "SNDKBUSD", "MRBLBUSD", "MSTRBUSD"
]

async def send_telegram_alert(session, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        async with session.post(url, json=payload, timeout=10) as resp:
            await resp.text()
    except Exception as e:
        print(f"Telegram Alert Error: {e}", flush=True)

async def check_market_data():
    async with aiohttp.ClientSession() as session:
        await send_telegram_alert(session, "🚀 *Delta REST Polling Bot is Online!*")
        print("Polling bot started successfully.", flush=True)

        while True:
            for symbol in SYMBOLS:
                url = f"https://api.delta.exchange/v2/history/candles?resolution=1m&symbol={symbol}"
                try:
                    async with session.get(url, timeout=8) as response:
                        res = await response.json()
                        if "result" in res and res["result"]:
                            candles = res["result"]
                            latest = candles[-1]
                            print(f"[POLL SUCCESS] {symbol} | Close: {latest.get('close')}", flush=True)
                except Exception as e:
                    print(f"Error fetching {symbol}: {e}", flush=True)
            
            # Har 60 seconds mein check karega
            await asyncio.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(check_market_data())
