"""
Aster Account Monitor — WebSocket real-time account monitor (read-only)
======================================================================
Streams account events to console + log file:
  ACCOUNT_UPDATE      balance/position changes (orders, funding, liquidation)
  ORDER_TRADE_UPDATE  order status changes (new/fill/trigger/cancel)
  MARGIN_CALL         margin-call warning (liquidation risk alert)
  listenKeyExpired    listenKey expired

Usage:
  pip install python-dotenv websocket-client requests eth-account
  cp ../.env.example ../.env   # fill with a READ-ONLY API key
  python account_monitor.py

Recommended: use a separate read-only API key (USER_STREAM permission, no trade/withdraw).
"""
import os, sys, json, time, threading
from datetime import datetime, timezone, timedelta

# project root on path for aster_client import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from aster_client import AsterClientV3

BJ = timezone(timedelta(hours=8))
LOG_FILE = os.path.join(os.path.dirname(__file__), '..', 'account_monitor.log')
WS_BASE = "wss://fstream.asterdex.com"


def log(msg):
    ts = datetime.now(BJ).strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + "\n")


def fmt_account_update(data):
    a = data.get('a', {})
    m = a.get('m', '?')
    lines = [f"ACCOUNT_UPDATE (reason:{m})"]
    for b in a.get('B', []):
        lines.append(f"  balance {b.get('a')}: wallet={b.get('wb')} avail={b.get('cw')} change={b.get('bc')}")
    for p in a.get('P', []):
        amt = float(p.get('pa', 0))
        side = 'LONG' if amt > 0 else 'SHORT'
        lines.append(f"  position {p.get('s')} {side} {abs(amt)} @{p.get('ep')} uPnL={p.get('up')}")
    return "\n".join(lines)


def fmt_order_update(data):
    o = data.get('o', {})
    return (f"ORDER_TRADE_UPDATE: {o.get('s')} {o.get('S')} qty={o.get('q')} "
            f"status={o.get('X')} type={o.get('o')} fillPrice={o.get('L')} "
            f"stopPrice={o.get('sp')}")


def fmt_margin_call(data):
    lines = ["⚠️ MARGIN_CALL warning!"]
    for p in data.get('p', []):
        lines.append(f"  {p.get('s')} {p.get('ps')} pos={p.get('pa')} "
                     f"mark={p.get('mp')} uPnL={p.get('up')} maintMargin={p.get('mm')}")
    return "\n".join(lines)


def fmt_event(data):
    e = data.get('e', '?')
    if e == 'ACCOUNT_UPDATE':
        return fmt_account_update(data)
    elif e == 'ORDER_TRADE_UPDATE':
        return fmt_order_update(data)
    elif e == 'MARGIN_CALL':
        return fmt_margin_call(data)
    elif e == 'listenKeyExpired':
        return "listenKey expired, need refresh"
    else:
        return f"unknown event: {json.dumps(data, ensure_ascii=False)[:200]}"


def keepalive(client, stop_event):
    """Extend listenKey every 50 min (validity 60 min)"""
    while not stop_event.is_set():
        stop_event.wait(50 * 60)
        if stop_event.is_set():
            break
        try:
            client.session.put(client.base_url + "/fapi/v3/listenKey", timeout=30)
            log("🔑 listenKey extended (50min auto)")
        except Exception as e:
            log(f"⚠️ listenKey extend failed: {e}")


def main():
    log("=" * 60)
    log("Aster Account Monitor v1 (WebSocket, read-only)")
    client = AsterClientV3(os.getenv("ASTER_USER"), os.getenv("ASTER_SIGNER"), os.getenv("ASTER_PRIVATE_KEY"))

    try:
        r = client._request("POST", "/fapi/v3/listenKey", signed=True)
        listen_key = r.get('listenKey')
        if not listen_key:
            log(f"❌ listenKey creation failed: {r}")
            return
        log("🔑 listenKey obtained")
    except Exception as e:
        log(f"❌ listenKey creation error: {e}")
        return

    stop_event = threading.Event()
    th = threading.Thread(target=keepalive, args=(client, stop_event), daemon=True)
    th.start()

    import websocket
    ws_url = f"{WS_BASE}/ws/{listen_key}"
    log(f"🔌 connecting {ws_url[:60]}...")

    def on_message(ws, message):
        try:
            data = json.loads(message)
            log(fmt_event(data))
        except Exception as e:
            log(f"⚠️ message parse error: {e}")

    def on_error(ws, error):
        log(f"❌ WebSocket error: {error}")

    def on_close(ws, code, msg):
        log(f"🔌 connection closed ({code} {msg})")

    def on_open(ws):
        log("✅ WebSocket connected, monitoring...")

    ws = websocket.WebSocketApp(ws_url,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close,
                                on_open=on_open)
    try:
        ws.run_forever(ping_interval=30, ping_timeout=10)
    except KeyboardInterrupt:
        log("stopped by user")
    finally:
        stop_event.set()
        log("monitor exited")


if __name__ == "__main__":
    main()
