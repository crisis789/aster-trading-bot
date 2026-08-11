"""Indicator unit tests — pure math, no network.

Run with: python -m unittest tests.test_indicators -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from aster_trading_bot.indicators import (
    ema_series, sma_series, rsi_series, bollinger_bands, atr_series,
)


class TestEma(unittest.TestCase):
    def test_short_input_returns_none(self):
        self.assertIsNone(ema_series([1.0, 2.0], 10))

    def test_alignment(self):
        vals = [float(i) for i in range(1, 31)]
        e = ema_series(vals, 10)
        self.assertEqual(len(e), len(vals))
        self.assertEqual(e[:9], [None] * 9)
        # EMA seed equals SMA of first 10
        self.assertAlmostEqual(e[9], sum(vals[:10]) / 10, places=6)

    def test_ema_follows_trend(self):
        vals = [float(i) for i in range(1, 31)]
        e = ema_series(vals, 10)
        # On an uptrend the latest EMA sits below the latest price
        self.assertLess(e[-1], vals[-1])


class TestSma(unittest.TestCase):
    def test_sma_value(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        s = sma_series(vals, 3)
        self.assertEqual(s[:2], [None, None])
        self.assertAlmostEqual(s[2], 2.0)
        self.assertAlmostEqual(s[4], 4.0)


class TestRsi(unittest.TestCase):
    def test_all_up_means_100(self):
        vals = [100.0 + i for i in range(20)]
        r = rsi_series(vals, 14)
        self.assertIsNotNone(r)
        self.assertEqual(r[-1], 100.0)

    def test_all_down_means_0(self):
        vals = [100.0 - i for i in range(20)]
        r = rsi_series(vals, 14)
        self.assertIsNotNone(r)
        self.assertEqual(r[-1], 0.0)

    def test_boundaries(self):
        vals = [50.0, 51.0, 50.0, 51.0, 50.0] * 6
        r = rsi_series(vals, 14)
        self.assertIsNotNone(r)
        self.assertGreaterEqual(r[-1], 0.0)
        self.assertLessEqual(r[-1], 100.0)


class TestBollinger(unittest.TestCase):
    def test_bands_alignment(self):
        vals = [100.0 + (i % 5) for i in range(40)]
        bands = bollinger_bands(vals, 20, 2.0)
        self.assertIsNotNone(bands)
        upper, mid, lower = bands
        self.assertEqual(len(upper), len(vals))
        self.assertIsNone(upper[18])
        self.assertIsNotNone(upper[19])
        for i in range(19, len(vals)):
            self.assertGreater(upper[i], mid[i])
            self.assertLess(lower[i], mid[i])

    def test_constant_series_zero_width(self):
        vals = [42.0] * 40
        bands = bollinger_bands(vals, 20, 2.0)
        upper, mid, lower = bands
        self.assertAlmostEqual(upper[-1], 42.0, places=6)
        self.assertAlmostEqual(lower[-1], 42.0, places=6)


class TestAtr(unittest.TestCase):
    def test_atr_positive(self):
        highs = [101.0 + i for i in range(20)]
        lows = [99.0 + i for i in range(20)]
        closes = [100.0 + i for i in range(20)]
        a = atr_series(highs, lows, closes, 14)
        self.assertIsNotNone(a)
        self.assertEqual(len(a), len(closes))
        self.assertIsNone(a[13])
        self.assertIsNotNone(a[14])
        self.assertGreater(a[-1], 0.0)


if __name__ == "__main__":
    unittest.main()
