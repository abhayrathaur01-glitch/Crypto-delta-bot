import time
import requests
import pandas as pd
import pandas_ta as ta

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = "8739623680:AAFu7b7mIHp8nNeN37TClUsHrIjcF1Fzt98"
TELEGRAM_CHAT_ID = "-549118591"

# 12 Delta Exchange Tickers List
SYMBOLS = [
    "BTCUSD",     # Bitcoin
    "ETHUSD",     # Ethereum
    "CRCLXUSD",   # Circle
    "PAXGUSD",    # Pax Gold
    "AAVEUSD",    # Aave
    "NVDAXUSD",   # Nvidia
    "TSLAXUSD",   # Tesla
    "SPCXXUSD",   # SpaceX
    "BNBUSD",     # BNB
    "SNDKBUSD",   # SNDK BUSD
    "MRBLBUSD",   # MRBL BUSD
    "MSTRBUSD"    # MicroStrategy BUSD
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
        print(f"Telegram Alert Error: {e}")

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
        print(f"Error fetching data for {symbol} {timeframe}: {e}")
    return None

def check_strategy():
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            df = get_delta_candles(symbol, tf)
            if df is None or len(df) < 200:
                continue

            df['ema200'] = ta.ema(df['close'], length=200)

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
                print(msg)
                send_telegram_alert(msg)

            # Bearish Rejection
            elif high_price >= ema and body_max < ema:
                msg = (f"🚨 *DELTA REVERSAL ALERT (SELL)* 🚨\n\n"
                       f"📌 *Symbol*: {symbol}\n"
                       f"⏱ *Timeframe*: {tf}\n"
                       f"🔹 *Reason*: 200 EMA Wick Rejection!\n"
                       f"📈 *EMA 200*: {round(ema, 2)}")
                print(msg)
                send_telegram_alert(msg)

while True:
    print("Scanning Delta Exchange market for 200 EMA Wick Rejections...")
    check_strategy()
    time.sleep(60)
