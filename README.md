# Aster Trading Bot Framework

[![CI](https://github.com/crisis789/aster-trading-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/crisis789/aster-trading-bot/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/aster-trading-bot.svg)](https://pypi.org/project/aster-trading-bot/)
[![Python](https://img.shields.io/pypi/pyversions/aster-trading-bot.svg)](https://pypi.org/project/aster-trading-bot/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-oriented trading bot framework for [Aster DEX](https://asterdex.com) USDT-margined futures, built on the official [Aster FAPI V3 API](https://github.com/asterdex/api-docs).

> ⚠️ **DISCLAIMER**: Cryptocurrency futures trading with leverage carries extreme risk of loss. This project is for **educational and research purposes only**. It is NOT financial advice. You can lose all your margin. Trade at your own risk.

## ✨ Features

- **Complete risk management**: 3% hard stop-loss, position timeout, consecutive-loss cooldown, position sync on restart
- **Anti-wick protection**: stop-loss orders use `MARK_PRICE` trigger + `priceProtect` (prevents false triggers from price spikes)
- **Real-time account monitoring**: WebSocket user-data stream (orders, balance, positions, margin calls)
- **Clean strategy interface**: subclass `TradingBot` and implement `signal()` / `exit_signal()`
- **Reusable indicator library**: pure-function EMA / RSI / Bollinger Bands / ATR (no network I/O, unit-tested)
- **Multi-key isolation**: separate API keys for bot / monitor / manual ops (Aster's nonce is per-Agent-address)
- **No secrets in code**: all credentials loaded from `.env`

## 📦 Install

```bash
pip install aster-trading-bot
```

Or clone and run from source:

```bash
git clone https://github.com/crisis789/aster-trading-bot.git
cd aster-trading-bot
pip install -r requirements.txt
```

## 🚀 Quick Start

```bash
# 1. Get your API key from https://www.asterdex.com/zh-CN/api-wallet
#    (recommend: create a separate key with trade permission only, no withdrawal)

# 2. Configure
cp .env.example .env
# edit .env with your ASTER_USER / ASTER_SIGNER / ASTER_PRIVATE_KEY

# 3. Run an example strategy (for demonstration only)
python examples/strategy_demo.py          # EMA cross
python examples/strategy_rsi.py           # RSI mean reversion
python examples/strategy_bollinger.py     # Bollinger Band reversion

# 4. Run the real-time account monitor (optional, read-only)
python examples/account_monitor.py
```

## 🧱 Project Structure

```
aster-trading-bot/
├── src/aster_trading_bot/
│   ├── aster_client.py     # Aster FAPI V3 API wrapper (signed requests, EIP-712)
│   ├── bot_framework.py    # Trading framework: risk management + lifecycle
│   └── indicators.py       # Pure technical indicators (EMA/RSI/BB/ATR)
├── examples/
│   ├── strategy_demo.py        # EMA-cross strategy (simplest example)
│   ├── strategy_rsi.py         # RSI mean-reversion strategy
│   ├── strategy_bollinger.py   # Bollinger Band reversion strategy
│   └── account_monitor.py      # WebSocket account monitor (orders/balance/margin calls)
├── tests/
│   ├── test_framework.py   # Framework unit tests (no network needed)
│   ├── test_indicators.py  # Indicator math tests
│   └── test_strategies.py  # Strategy signal tests (mocked market data)
├── docs/
│   └── strategy-development.md  # How to build your own strategy
├── .github/workflows/ci.yml    # CI: tests on Python 3.10/3.11/3.12
├── .env.example            # Credentials template
└── README.md
```

## 🧪 Testing

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

CI runs automatically on every push (GitHub Actions, Python 3.10–3.12).

## 🔐 Security Notes

- **Never commit `.env`** — it contains your private keys. `.gitignore` already excludes it.
- Use **separate API keys** for trading bot vs monitoring vs manual operations. Aster's nonce replay-protection is maintained per Agent address; sharing a key between processes causes `400` errors.
- Do **not** grant withdrawal permission to the bot's API key.

## 🏗️ Writing Your Own Strategy

```python
from aster_trading_bot import TradingBot

class MyStrategy(TradingBot):
    def signal(self, symbol):
        # return ('SHORT', price) or ('LONG', price) or None
        ...
    def exit_signal(self, symbol):
        # return True to close
        ...

MyStrategy(["HYPEUSDT", "ENAUSDT"]).run()
```

The framework handles: opening positions, placing stop-loss orders (MARK_PRICE + priceProtect), position timeout, cooldown after consecutive losses, position takeover on restart, and real-position sync.

### Indicators

All indicators are pure functions — feed them a list of floats, get an aligned list back (leading `None` until the window is full):

```python
from aster_trading_bot.indicators import ema_series, rsi_series, bollinger_bands, atr_series

closes = [float(k[4]) for k in klines]
rsi    = rsi_series(closes, 14)            # RSI, Wilder smoothing
upper, mid, lower = bollinger_bands(closes, 20, 2.0)
atr    = atr_series(highs, lows, closes, 14)
```

## 🔧 API Reference

See `src/aster_trading_bot/aster_client.py` — covers: klines, ticker, balance, positionRisk, order placement/cancel (LIMIT/MARKET/STOP_MARKET), leverage, and more. Auth via EIP-712 typed-data signing per the official docs.

## 📜 License

MIT

## 🙏 Credits

Built on [Aster FAPI V3 API docs](https://github.com/asterdex/api-docs) (official).
