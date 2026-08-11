# Strategy Development Guide

This guide shows how to build your own trading strategy on top of the framework.

## Architecture

```
Your strategy (subclass)
        │  signal() / exit_signal()   ← you implement these
        ▼
TradingBot framework (src/bot_framework.py)
        │  handles: order placement, stop-loss, timeout,
        │  cooldown, position sync, restart takeover
        ▼
aster_client.py (src/aster_client.py)
        │  signed REST calls to Aster FAPI V3
        ▼
Aster DEX (fapi.asterdex.com)
```

The framework owns **risk management and execution**; your strategy owns **decision making**. This separation means you can iterate on strategy logic without touching the risky plumbing.

## Step 1: Subclass TradingBot

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from bot_framework import TradingBot

class MyStrategy(TradingBot):
    def signal(self, symbol):
        """Called every SCAN_INTERVAL for symbols without an open position.
        Return:
          ('SHORT', price)  → open a short at ~price
          ('LONG', price)   → open a long
          None              → no signal
        """
        price = self._fetch_price(symbol)
        if self._momentum_bearish(symbol):
            return ('SHORT', price)
        return None

    def exit_signal(self, symbol):
        """Called every SCAN_INTERVAL for symbols WITH an open position.
        Return True to close the position.
        """
        return self._momentum_reversed(symbol)
```

## Step 2: Data Access

The framework does not dictate how you fetch market data. Use any source:

```python
import requests

def _fetch_klines(self, symbol, interval="1h", limit=200):
    r = requests.get("https://fapi.asterdex.com/fapi/v3/klines",
                     params={"symbol": symbol, "interval": interval, "limit": limit},
                     timeout=30)
    return r.json()  # list of [openTime, open, high, low, close, ...]
```

**Important — no lookahead bias**: when your signal uses candle `i`'s close, make sure candle `i` is actually closed before you act. Using the live price of the *current* unclosed candle for confirmation is fine (intra-bar), but never use data from the *future*.

## Step 3: Risk Tuning

Framework constants in `bot_framework.py`:

| Constant | Default | Meaning |
|----------|---------|---------|
| `STOP_PCT` | 0.03 | Hard stop-loss: price moves 3% against you |
| `MAX_HOLD_HOURS` | 120 | Force-close after this many hours |
| `COOL_LOSSES` | 2 | Cooldown after N consecutive losses |
| `COOL_SECONDS` | 6*3600 | Cooldown duration |
| `BAL_PCT` | 0.30 | Margin per position = 30% of total funds |
| `LEVERAGE` | 20 | Exchange leverage (also sets liquidation distance) |

**Leverage vs stop-loss**: at 20x, a 5% adverse move liquidates your margin. A 3% stop-loss fires *before* liquidation — keep `STOP_PCT` comfortably below `1/LEVERAGE`.

## Step 4: Backtest Before Live

Before risking real money:
1. Download historical klines (the repo's `examples/` has no backtester, but `aster_client.py` klines endpoint can fetch history)
2. Simulate your exact signal + framework risk rules (stop-loss, timeout)
3. Use **realistic fill prices** — don't assume you always get the candle open; use (open+close)/2 as a conservative mid estimate
4. Include fees (0.04% taker per side on Aster)

## Step 5: Run

```bash
cp .env.example .env   # fill credentials
python your_strategy.py
```

## Checklist Before Live Trading

- [ ] Backtested on ≥6 months of data with fees
- [ ] No lookahead bias in signal code
- [ ] Stop-loss < liquidation distance (3% < 5% at 20x)
- [ ] Separate API key for the bot (no withdrawal permission)
- [ ] Paper-run for 1-2 days, verify logs look sane
- [ ] READ the disclaimer in README.md — you trade at your own risk
