"""
示例策略: 布林带突破 (演示框架用法, 非投资建议)
================================================
策略逻辑 (演示用, 故意简单):
  LONG:  收盘价跌破布林下轨 (超卖) → 做多
  SHORT: 收盘价升破布林上轨 (超买) → 做空
  出场:  收盘价回到布林中轨 (SMA20) → 平仓

思路: 价格突破通道极端位置后回归中轨。可与 RSI 示例
对比: 布林带用标准差量化波动, RSI 用动量强弱量化。

运行:
  pip install -r requirements.txt
  cp .env.example .env   # 填入你的 Aster API key
  python examples/strategy_bollinger.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import requests
from aster_trading_bot.bot_framework import TradingBot, log
from aster_trading_bot.indicators import bollinger_bands

SYMBOLS = ["HYPEUSDT", "ENAUSDT"]
BB_PERIOD = 20     # 中轨 SMA 周期
BB_MULT = 2.0      # 带宽倍数 (标准差)


def fetch_klines(symbol, limit=200, interval="1h"):
    """拉取K线, 返回收盘价列表. 失败返回 None."""
    try:
        r = requests.get("https://fapi.asterdex.com/fapi/v3/klines",
                         params={"symbol": symbol, "interval": interval, "limit": limit},
                         timeout=30)
        return [float(x[4]) for x in r.json()]
    except Exception as e:
        log(f"  K线获取失败 {symbol}: {e}")
        return None


class BollingerBot(TradingBot):
    """布林带均值回归示例策略"""

    def signal(self, symbol):
        closes = fetch_klines(symbol)
        if closes is None:
            return None
        bands = bollinger_bands(closes, BB_PERIOD, BB_MULT)
        if bands is None:
            return None
        upper, mid, lower = bands
        if upper[-2] is None or lower[-2] is None:
            return None
        price = closes[-2]     # 用已收盘的上一根, 避免未来函数
        if price <= lower[-2]:
            return ('LONG', price)
        if price >= upper[-2]:
            return ('SHORT', price)
        return None

    def exit_signal(self, symbol):
        closes = fetch_klines(symbol)
        if closes is None:
            return False
        bands = bollinger_bands(closes, BB_PERIOD, BB_MULT)
        if bands is None:
            return False
        upper, mid, lower = bands
        if mid[-2] is None:
            return False
        # 穿越中轨即出场
        price = closes[-2]
        prev = closes[-3] if len(closes) > 2 else price
        prev_mid = mid[-3] if len(closes) > 2 and mid[-3] is not None else mid[-2]
        return (price >= mid[-2] and prev < prev_mid) or \
               (price <= mid[-2] and prev > prev_mid)


if __name__ == "__main__":
    log("布林带示例策略启动 (演示用, 非投资建议)")
    bot = BollingerBot(SYMBOLS)
    bot.run()
