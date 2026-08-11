"""Strategy signal tests — mock market data, no network.

Verifies that each example strategy emits the expected signal for
hand-crafted price series (and that no signal fires in neutral markets).

Run with: python -m unittest tests.test_strategies -v
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'examples'))

import strategy_rsi as rsi_mod
import strategy_bollinger as bb_mod


def make_bot(cls):
    """Build a strategy instance without touching the network / .env."""
    with mock.patch.object(cls, '__init__', lambda self, symbols: None):
        bot = cls.__new__(cls)
    bot.symbols = ["HYPEUSDT"]
    return bot


def neutral_series(n=40):
    """Tight sideways market: 100..101.5 zigzag, no trend."""
    return [100.0 + (i % 4) * 0.5 for i in range(n)]


class TestRsiStrategy(unittest.TestCase):
    def test_oversold_gives_long(self):
        bot = make_bot(rsi_mod.RsiMeanReversionBot)
        # 20 bars: 19 falling + 1 flat → RSI pinned near 0
        closes = [100.0 - i * 0.5 for i in range(19)] + [90.5]
        with mock.patch.object(rsi_mod, 'fetch_klines', return_value=closes):
            sig = bot.signal("HYPEUSDT")
        self.assertIsNotNone(sig)
        self.assertEqual(sig[0], 'LONG')

    def test_overbought_gives_short(self):
        bot = make_bot(rsi_mod.RsiMeanReversionBot)
        closes = [100.0 + i * 0.5 for i in range(19)] + [109.5]
        with mock.patch.object(rsi_mod, 'fetch_klines', return_value=closes):
            sig = bot.signal("HYPEUSDT")
        self.assertIsNotNone(sig)
        self.assertEqual(sig[0], 'SHORT')

    def test_neutral_gives_none(self):
        bot = make_bot(rsi_mod.RsiMeanReversionBot)
        with mock.patch.object(rsi_mod, 'fetch_klines', return_value=neutral_series()):
            sig = bot.signal("HYPEUSDT")
        self.assertIsNone(sig)

    def test_exit_when_rsi_back_to_neutral(self):
        bot = make_bot(rsi_mod.RsiMeanReversionBot)
        # Oversold (15 falling bars → RSI~0), then 15 rising bars → RSI back ~50
        closes = [100.0 - i * 0.8 for i in range(15)] + \
                 [88.8 + j * 0.5 for j in range(15)]
        with mock.patch.object(rsi_mod, 'fetch_klines', return_value=closes):
            self.assertTrue(bot.exit_signal("HYPEUSDT"))

    def test_no_exit_while_still_oversold(self):
        bot = make_bot(rsi_mod.RsiMeanReversionBot)
        closes = [100.0 - i * 0.5 for i in range(19)] + [90.5]
        with mock.patch.object(rsi_mod, 'fetch_klines', return_value=closes):
            self.assertFalse(bot.exit_signal("HYPEUSDT"))


class TestBollingerStrategy(unittest.TestCase):
    def test_below_lower_band_gives_long(self):
        bot = make_bot(bb_mod.BollingerBot)
        # Sideways market, then a sharp last-bar dump far below the lower band
        closes = neutral_series(40)
        closes[-2] = 95.0
        closes[-1] = 95.0
        with mock.patch.object(bb_mod, 'fetch_klines', return_value=closes):
            sig = bot.signal("HYPEUSDT")
        self.assertIsNotNone(sig)
        self.assertEqual(sig[0], 'LONG')

    def test_above_upper_band_gives_short(self):
        bot = make_bot(bb_mod.BollingerBot)
        closes = neutral_series(40)
        closes[-2] = 107.0
        closes[-1] = 107.0
        with mock.patch.object(bb_mod, 'fetch_klines', return_value=closes):
            sig = bot.signal("HYPEUSDT")
        self.assertIsNotNone(sig)
        self.assertEqual(sig[0], 'SHORT')

    def test_within_bands_gives_none(self):
        bot = make_bot(bb_mod.BollingerBot)
        with mock.patch.object(bb_mod, 'fetch_klines', return_value=neutral_series()):
            sig = bot.signal("HYPEUSDT")
        self.assertIsNone(sig)

    def test_exit_on_mid_cross(self):
        bot = make_bot(bb_mod.BollingerBot)
        # Was far below the lower band (95), now back above the mid band (~100)
        closes = neutral_series(40)
        closes[-3] = 95.0
        closes[-2] = 101.0
        closes[-1] = 101.0
        with mock.patch.object(bb_mod, 'fetch_klines', return_value=closes):
            self.assertTrue(bot.exit_signal("HYPEUSDT"))

    def test_no_exit_below_bands(self):
        bot = make_bot(bb_mod.BollingerBot)
        closes = neutral_series(40)
        closes[-3] = 95.0
        closes[-2] = 95.0
        closes[-1] = 95.0
        with mock.patch.object(bb_mod, 'fetch_klines', return_value=closes):
            self.assertFalse(bot.exit_signal("HYPEUSDT"))


if __name__ == "__main__":
    unittest.main()
