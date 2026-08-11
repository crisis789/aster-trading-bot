"""
示例策略: 简单 EMA 交叉策略 (演示框架用法, 非投资建议)
========================================================
策略逻辑 (演示用, 故意简单):
  LONG:  EMA10 上穿 EMA30 且收盘价 > EMA10
  SHORT: EMA10 下穿 EMA30 且收盘价 < EMA10
  出场:  收盘价穿越 EMA30

运行:
  pip install python-dotenv websocket-client
  cp .env.example .env   # 填入你的 Aster API key
  python strategy_demo.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import requests
from aster_trading_bot.bot_framework import TradingBot, log
from aster_trading_bot.indicators import ema_series

SYMBOLS = ["HYPEUSDT", "ENAUSDT"]
EMA_F, EMA_S = 10, 30


class EmaCrossBot(TradingBot):
    """演示用均线交叉策略"""

    def signal(self, symbol):
        try:
            r = requests.get("https://fapi.asterdex.com/fapi/v3/klines",
                             params={"symbol": symbol, "interval": "1h", "limit": 100}, timeout=30)
            closes = [float(x[4]) for x in r.json()]
        except Exception as e:
            log(f"  K线获取失败 {symbol}: {e}")
            return None
        e_f = ema_series(closes, EMA_F)
        e_s = ema_series(closes, EMA_S)
        if e_f is None or e_s is None:
            return None
        # 上穿 (金叉)
        if e_f[-3] is not None and e_s[-3] is not None:
            if e_f[-3] <= e_s[-3] and e_f[-2] > e_s[-2]:
                return ('LONG', closes[-1])
            if e_f[-3] >= e_s[-3] and e_f[-2] < e_s[-2]:
                return ('SHORT', closes[-1])
        return None

    def exit_signal(self, symbol):
        try:
            r = requests.get("https://fapi.asterdex.com/fapi/v3/klines",
                             params={"symbol": symbol, "interval": "1h", "limit": 100}, timeout=30)
            closes = [float(x[4]) for x in r.json()]
        except Exception:
            return False
        e_s = ema_series(closes, EMA_S)
        if e_s is None or e_s[-2] is None:
            return False
        # 收盘穿越EMA30 即出场
        return (closes[-2] < e_s[-2] and closes[-3] >= e_s[-3]) or \
               (closes[-2] > e_s[-2] and closes[-3] <= e_s[-3])


if __name__ == "__main__":
    log("EMA交叉示例策略启动 (演示用, 非投资建议)")
    bot = EmaCrossBot(SYMBOLS)
    bot.run()
