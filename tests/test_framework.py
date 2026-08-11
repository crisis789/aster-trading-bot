"""Framework unit tests — run with: python -m unittest tests.test_framework"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import bot_framework


class FakeClient:
    """Minimal mock of AsterClientV3 for logic testing (no network)."""

    def __init__(self, *a, **k):
        self.balance = 100.0
        self.pnl = 0.0
        self.orders = []

    def get_account_balance(self):
        return [{"asset": "USDT", "balance": str(self.balance),
                 "crossUnPnl": str(self.pnl), "availableBalance": str(self.balance)}]

    def get_position_risk(self, *a):
        return []

    def create_order(self, *a, **k):
        self.orders.append((a, k))
        return {"orderId": len(self.orders), "avgPrice": "55.0"}

    def cancel_all_orders(self, *a):
        return {}


def make_bot():
    bot_framework.AsterClientV3 = FakeClient
    return bot_framework.TradingBot(["HYPEUSDT"])


class TestCalcQty(unittest.TestCase):
    def test_fixed_notional(self):
        bot = make_bot()
        q = bot.calc_qty(90, 55.0, 0.01, 0.01, 540.0)
        self.assertEqual(q, 9.81)

    def test_capped_by_balance(self):
        bot = make_bot()
        q = bot.calc_qty(30, 50.0, 0.01, 0.01, 540.0)
        self.assertEqual(q, 3.6)

    def test_below_min_returns_zero(self):
        bot = make_bot()
        # 名义 $6 时 qty=0.01 仍满足 min_qty → 返回 0.01
        q = bot.calc_qty(1, 500.0, 0.01, 0.01, 540.0)
        self.assertEqual(q, 0.01)
        # 名义太小 (< 最小名义) → 返回 0
        q2 = bot.calc_qty(0.5, 500.0, 0.01, 0.01, 540.0)
        self.assertEqual(q2, 0)

    def test_no_float_noise(self):
        bot = make_bot()
        q = bot.calc_qty(90.91, 55.146, 0.01, 0.01, 540.0)
        s = str(q)
        self.assertNotIn("9999", s)

    def test_ena_step_size(self):
        bot = make_bot()
        # ENA step=1, qty must be integer
        q = bot.calc_qty(90, 0.087, 1, 1, 540.0)
        self.assertEqual(q, round(q))


class TestTrading(unittest.TestCase):
    def test_open_position_places_stop(self):
        bot = make_bot()
        ok = bot.open_position("HYPEUSDT", "SHORT", 55.0, 9.81)
        self.assertTrue(ok)
        types = [o[0][2] for o in bot.client.orders]
        self.assertIn("MARKET", types)
        self.assertIn("STOP_MARKET", types)
        stop_kwargs = [o[1] for o in bot.client.orders if o[0][2] == "STOP_MARKET"][0]
        self.assertEqual(stop_kwargs.get("working_type"), "MARK_PRICE")
        self.assertEqual(stop_kwargs.get("price_protect"), "TRUE")

    def test_close_position_cancels_first(self):
        bot = make_bot()
        ok = bot.close_position("HYPEUSDT", 9.81)
        self.assertTrue(ok)
        self.assertEqual(bot.client.orders[0][0][0], "HYPEUSDT")


class TestBalance(unittest.TestCase):
    def test_total_funds(self):
        bot = make_bot()
        bot.client.balance = 90.74
        bot.client.pnl = -1.28
        v, err = bot.get_balance()
        self.assertIsNone(err)
        self.assertAlmostEqual(v, 89.46, places=2)


if __name__ == "__main__":
    unittest.main()
