"""
示例策略: RSI 均值回归 (演示框架用法, 非投资建议)
================================================
策略逻辑 (演示用, 故意简单):
  LONG:  RSI(14) 跌破 30 (超卖) → 做多
  SHORT: RSI(14) 升破 70 (超买) → 做空
  出场:  RSI 回到 50 中性区 (45-55) → 平仓

思路: 均值回归假设价格围绕价值中枢波动, 极端超买/超卖
终将回归。适合震荡市; 单边趋势中会逆势亏损。

运行:
  pip install -r requirements.txt
  cp .env.example .env   # 填入你的 Aster API key
  python examples/strategy_rsi.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import requests
from aster_trading_bot.bot_framework import TradingBot, log
from aster_trading_bot.indicators import rsi_series

SYMBOLS = ["HYPEUSDT", "ENAUSDT"]
RSI_PERIOD = 14
OVERSOLD = 30.0   # 超卖阈值: 低于此做多
OVERBOUGHT = 70.0  # 超买阈值: 高于此做空
NEUTRAL_LO = 45.0  # 出场区下沿
NEUTRAL_HI = 55.0  # 出场区上沿


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


class RsiMeanReversionBot(TradingBot):
    """RSI 均值回归示例策略"""

    def signal(self, symbol):
        closes = fetch_klines(symbol)
        if closes is None:
            return None
        rsi = rsi_series(closes, RSI_PERIOD)
        if rsi is None or rsi[-2] is None:
            return None
        cur = rsi[-2]          # 用已收盘的上一根, 避免未来函数
        price = closes[-2]
        if cur < OVERSOLD:
            return ('LONG', price)
        if cur > OVERBOUGHT:
            return ('SHORT', price)
        return None

    def exit_signal(self, symbol):
        closes = fetch_klines(symbol)
        if closes is None:
            return False
        rsi = rsi_series(closes, RSI_PERIOD)
        if rsi is None or rsi[-2] is None:
            return False
        return NEUTRAL_LO <= rsi[-2] <= NEUTRAL_HI


if __name__ == "__main__":
    log("RSI 均值回归示例策略启动 (演示用, 非投资建议)")
    bot = RsiMeanReversionBot(SYMBOLS)
    bot.run()
