"""
Aster FAPI V3 客户端 — 完全按官方文档实现
API 文档: https://github.com/asterdex/api-docs
"""
import time
import threading
import urllib.parse
import requests
from typing import Any, Dict, Optional
from eth_account.messages import encode_typed_data as encode_structured_data
from eth_account import Account

EIP712_DOMAIN = {
    "name": "AsterSignTransaction",
    "version": "1",
    "chainId": 1666,
    "verifyingContract": "0x0000000000000000000000000000000000000000",
}

TYPED_DATA_TEMPLATE = {
    "types": {
        "EIP712Domain": [
            {"name": "name", "type": "string"},
            {"name": "version", "type": "string"},
            {"name": "chainId", "type": "uint256"},
            {"name": "verifyingContract", "type": "address"},
        ],
        "Message": [{"name": "msg", "type": "string"}],
    },
    "primaryType": "Message",
    "domain": EIP712_DOMAIN,
    "message": {"msg": ""},
}

class AsterClientV3:
    def __init__(self, user: str, signer: str, private_key: str,
                 base_url: str = "https://fapi.asterdex.com"):
        self.user = user.strip()
        self.signer = signer.strip()
        self._private_key = private_key.strip()
        if not self._private_key.startswith("0x"):
            self._private_key = "0x" + self._private_key
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
        })
        self._last_sec = 0
        self._seq = 0
        self._lock = threading.Lock()

    def _get_nonce(self) -> str:
        with self._lock:
            now_sec = int(time.time())
            if now_sec == self._last_sec:
                self._seq += 1
            else:
                self._last_sec = now_sec
                self._seq = 0
            return str(now_sec * 1_000_000 + self._seq)

    def _sign(self, params: Dict[str, Any]) -> str:
        param_str = urllib.parse.urlencode(params)
        td = dict(TYPED_DATA_TEMPLATE)
        td["message"] = {"msg": param_str}
        message = encode_structured_data(full_message=td)
        signed = Account.sign_message(message, private_key=self._private_key)
        return signed.signature.hex()

    def _request(self, method: str, endpoint: str,
                 params: Optional[Dict[str, Any]] = None, signed: bool = False) -> Any:
        p = dict(params or {})
        if signed:
            p["nonce"] = self._get_nonce()
            p["user"] = self.user
            p["signer"] = self.signer
            p["signature"] = self._sign(p)

        method = method.upper()
        if method == "GET":
            resp = self.session.get(self.base_url + endpoint, params=p, timeout=30)
        elif method == "POST":
            resp = self.session.post(self.base_url + endpoint, data=p, timeout=30)
        elif method == "DELETE":
            resp = self.session.delete(self.base_url + endpoint, data=p, timeout=30)
        else:
            raise ValueError(f"Unsupported method: {method}")
        resp.raise_for_status()
        return resp.json()

    def ping(self): return self._request("GET", "/fapi/v3/ping")
    def get_server_time(self): return self._request("GET", "/fapi/v3/time")

    def get_exchange_info(self, symbol=None):
        p = {}
        if symbol: p["symbol"] = symbol
        return self._request("GET", "/fapi/v3/exchangeInfo", params=p)

    def get_account_balance(self):
        return self._request("GET", "/fapi/v3/balance", signed=True)

    def get_account_info(self):
        return self._request("GET", "/fapi/v3/account", signed=True)

    def get_position_risk(self, symbol=None):
        p = {}
        if symbol: p["symbol"] = symbol
        return self._request("GET", "/fapi/v3/positionRisk", params=p, signed=True)

    def change_leverage(self, symbol, leverage):
        return self._request("POST", "/fapi/v3/leverage",
                            params={"symbol": symbol, "leverage": str(leverage)}, signed=True)

    def create_order(self, symbol, side, order_type, quantity, price=None, reduce_only=False,
                     stop_price=None, callback_rate=None, working_type=None, price_protect=None,
                     close_position=None):
        p = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": str(quantity),
        }
        if price is not None: p["price"] = str(price)
        if reduce_only: p["reduceOnly"] = "true"
        if stop_price is not None: p["stopPrice"] = str(stop_price)
        if callback_rate is not None: p["callbackRate"] = str(callback_rate)
        if working_type is not None: p["workingType"] = working_type
        if price_protect is not None: p["priceProtect"] = price_protect
        if close_position is not None: p["closePosition"] = close_position
        return self._request("POST", "/fapi/v3/order", params=p, signed=True)

    def get_open_orders(self, symbol=None):
        p = {}
        if symbol: p["symbol"] = symbol
        return self._request("GET", "/fapi/v3/openOrders", params=p, signed=True)

    def cancel_all_orders(self, symbol):
        return self._request("DELETE", "/fapi/v3/allOpenOrders",
                            params={"symbol": symbol}, signed=True)
