import os
import json
import time
import urllib.parse
import urllib.request

import ccxt

# ================== AYARLAR ==================
EXCHANGE = "kraken"
SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TIMEFRAME = "15m"
WINDOW_MIN = 20
FAST = 9
SLOW = 21
RSI_PERIOD = 14
RSI_MAX = 70
STOP_LOSS = 0.02
TAKE_PROFIT = 0.04
# =============================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
MANUAL = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"


def fmt(price):
    return f"{price:.2f}" if price >= 1 else f"{price:.6f}"


def sma(values, n):
    return sum(values[-n:]) / n


def rsi(values, n=14):
    gains, losses = 0.0, 0.0
    for i in range(-n, 0):
        diff = values[i] - values[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
    if losses == 0:
        return 100.0
    return 100 - 100 / (1 + gains / losses)


def find_chat_id():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.load(r)
    for update in reversed(data.get("result", [])):
        msg = update.get("message")
        if msg:
            return str(msg["chat"]["id"])
    return ""


def notify(text):
    print(text.replace("\n", " | "))
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
        urllib.request.urlopen(url, data=data, timeout=10)
    except Exception as e:
        print("Telegram gönderilemedi:", e)


def check_symbol(ex, symbol):
    ohlcv = ex.fetch_ohlcv(symbol, TIMEFRAME)[-100:]
    closes = [c[4] for c in ohlcv][:-1]
    price = ohlcv[-1][4]
    age_min = (time.time() * 1000 - ohlcv[-1][0]) / 60000

    fast_now, slow_now = sma(closes, FAST), sma(closes, SLOW)
    fast_prev, slow_prev = sma(closes[:-1], FAST), sma(closes[:-1], SLOW)
    rsi_now = rsi(closes, RSI_PERIOD)

    cross_up = fast_prev <= slow_prev and fast_now > slow_now
    cross_down = fast_prev >= slow_prev and fast_now < slow_now
    fresh = 0 <= age_min < WINDOW_MIN

    print(f"{symbol} | fiyat {fmt(price)} | RSI {rsi_now:.1f} | "
          f"yukari={cross_up} asagi={cross_down} taze={fresh}")

    if fresh and cross_up and rsi_now < RSI_MAX:
        notify(
            f"🟢 AL sinyali\n{symbol}\nFiyat: {fmt(price)}\nRSI: {rsi_now:.1f}\n"
            f"Zarar durdur: {fmt(price * (1 - STOP_LOSS))}\n"
            f"Kâr al hedefi: {fmt(price * (1 + TAKE_PROFIT))}"
        )
    elif fresh and cross_down:
        notify(
            f"🔴 SAT sinyali\n{symbol}\nFiyat: {fmt(price)}\n"
            f"Trend aşağı döndü. Bu coine girdiysen çıkmayı düşün."
        )


def main():
    global CHAT_ID
    if TELEGRAM_TOKEN and not CHAT_ID:
        try:
            CHAT_ID = find_chat_id()
        except Exception as e:
            print("Chat id bulunamadı:", e)
        if not CHAT_ID:
            print("Telegram'da botuna 'merhaba' yazip tekrar calistir.")

    ex = getattr(ccxt, EXCHANGE)({"enableRateLimit": True})
    errors = []
    for symbol in SYMBOLS:
        try:
            check_symbol(ex, symbol)
        except Exception as e:
            print(f"Hata ({symbol}):", e)
            errors.append(f"{symbol}: {str(e)[:150]}")

    if MANUAL:
        if errors:
            notify("⚠️ Bot çalıştı ama hata var:\n" + "\n".join(errors))
        else:
            notify(f"✅ Bot çalışıyor\n{', '.join(SYMBOLS)} | {TIMEFRAME} | {EXCHANGE}")


if __name__ == "__main__":
    main()
