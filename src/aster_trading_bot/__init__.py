"""
aster_trading_bot — production-oriented trading framework for Aster DEX futures.

Modules:
    aster_client   — signed REST client for the Aster FAPI V3 API (EIP-712 auth)
    bot_framework  — TradingBot base class: risk management + strategy interface
    indicators     — pure technical indicators (EMA, RSI, Bollinger, ATR)
"""
from .bot_framework import TradingBot
from .aster_client import AsterClientV3

__version__ = "0.2.0"
__all__ = ["TradingBot", "AsterClientV3", "indicators"]
