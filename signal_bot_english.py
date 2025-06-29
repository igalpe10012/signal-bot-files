
import json
import time
import ccxt
import requests
import pandas as pd
from datetime import datetime, timedelta

# Load config
with open("config.json") as f:
    config = json.load(f)

api_key = config["binance_api_key"]
api_secret = config["binance_api_secret"]
telegram_token = config["telegram_token"]
chat_id = config["telegram_chat_id"]

# Telegram send message function
def send_signal(message):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    requests.post(url, data=data)

# Connect to Binance
exchange = ccxt.binance({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

# Ignore list to prevent duplicate alerts within cooldown window
ignore_until = {}

# Main bot logic
def run_bot():
    try:
        markets = exchange.load_markets()
        usdt_pairs = [s for s in markets if s.endswith('/USDT') and markets[s]['future']]

        for symbol in usdt_pairs:
            now = datetime.utcnow()

            for tf, duration_hours in [('1h', 72), ('1d', 180)]:
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=duration_hours)
                if not ohlcv or len(ohlcv) < 2:
                    continue

                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

                max_row = df.loc[df['high'].idxmax()]
                max_price = max_row['high']
                max_volume = max_row['volume']

                current_price = df.iloc[-1]['close']
                current_volume = df.iloc[-1]['volume']

                if abs(current_price - max_price) / max_price <= 0.01 and current_volume < max_volume:
                    tag = f"{symbol}_{tf}"
                    if tag in ignore_until and now < ignore_until[tag]:
                        continue

                    msg = f"🚨 High Retest ({tf})\nSymbol: {symbol}\nPrice: {current_price:.4f}\nATH: {max_price:.4f}\nVolume lower than peak"
                    send_signal(msg)

                    ignore_until[tag] = now + timedelta(hours=4)

    except Exception as e:
        print(f"Error: {e}")

# Run the bot every 15 minutes
while True:
    run_bot()
    time.sleep(900)
