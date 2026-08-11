"""
Aster Trading Bot Framework — 通用做空交易框架 (开源版)
========================================================
风控完备的交易框架: 止损/超时/冷却/持仓同步/双保险
策略信号通过子类实现 signal() 接口注入

用法:
    class MyStrategy(TradingBot):
        def signal(self, symbol) -> tuple|None:
            # 返回 (direction, price) 或 None
            ...

    MyStrategy().run()

安全: 私钥只从 .env 读取, 代码不含任何密钥
风险: 合约交易极高风险, 仅供学习研究
"""
import os, sys, time, math
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv()  # 从当前目录 .env 读取凭据

from .aster_client import AsterClientV3

# ===== 风控参数 (可按需调整) =====
STOP_PCT = 0.03        # 止损: 价格反向3%
MAX_HOLD_HOURS = 120   # 超时兜底
COOL_LOSSES = 2        # 连亏冷却触发次数
COOL_SECONDS = 6*3600  # 冷却时长
SCAN_INTERVAL = 60     # 扫描间隔秒
BAL_PCT = 0.30         # 单笔保证金占总资金比例
LEVERAGE = 20          # 杠杆

LOG_FILE = "bot.log"

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, 'a') as f:
        f.write(line + "\n")


class TradingBot:
    """通用合约交易框架: 开仓/止损/平仓/风控/持仓同步"""

    def __init__(self, symbols):
        self.symbols = symbols
        self.client = AsterClientV3(
            os.getenv("ASTER_USER"), os.getenv("ASTER_SIGNER"), os.getenv("ASTER_PRIVATE_KEY"))
        self.positions = {}   # symbol -> {qty, entry, sl, open_time}
        self.consecutive_losses = 0
        self.cool_until = 0

    # ---------- 策略接口 (子类必须实现) ----------
    def signal(self, symbol):
        """返回 (direction, price) 开仓信号, 无信号返回 None.
        direction: 'LONG' 或 'SHORT'. 示例子类见 examples/strategy_demo.py"""
        raise NotImplementedError

    def exit_signal(self, symbol):
        """返回 True 平仓. 默认: 无"""
        return False

    # ---------- 账户 ----------
    def get_balance(self):
        """总资金 = 钱包余额 + 持仓浮亏"""
        for attempt in range(3):
            try:
                bal = self.client.get_account_balance()
                u = [b for b in bal if b["asset"] == "USDT"]
                if not u:
                    return None, "无USDT资产"
                v = float(u[0]["balance"]) + float(u[0].get("crossUnPnl", 0) or 0)
                if v < 1.0:
                    return None, f"总资金异常(${v:.4f})"
                return v, None
            except Exception as e:
                if attempt == 2:
                    return None, str(e)
                time.sleep(1.5)
        return None, "总资金获取未知错误"

    def get_position(self, symbol):
        for attempt in range(3):
            try:
                pos = self.client.get_position_risk(symbol)
                if isinstance(pos, list):
                    for p in pos:
                        if p.get('symbol') == symbol and float(p.get('positionAmt', 0) or 0) != 0:
                            return p
                return None
            except Exception:
                if attempt == 2:
                    return None
                time.sleep(1.5)
        return None

    # ---------- 交易 ----------
    def open_position(self, symbol, direction, price, qty):
        """开仓 + 挂止损单 (MARK_PRICE 抗插针 + 触发保护)"""
        side = "SELL" if direction == "SHORT" else "BUY"
        try:
            r = self.client.create_order(symbol, side, "MARKET", qty)
            fill_price = price
            if isinstance(r, dict) and r.get('avgPrice'):
                try:
                    fill_price = float(r['avgPrice'])
                except:
                    pass
            log(f"  开仓 {symbol} {direction} {qty} @~${fill_price:.4f}")
            time.sleep(3)
            sl = fill_price * (1 + STOP_PCT) if direction == "SHORT" else fill_price * (1 - STOP_PCT)
            sl_side = "BUY" if direction == "SHORT" else "SELL"
            for attempt in range(3):
                try:
                    self.client.create_order(symbol, sl_side, "STOP_MARKET", qty,
                                             stop_price=sl, reduce_only=True,
                                             working_type="MARK_PRICE", price_protect="TRUE")
                    log(f"  止损单: {symbol} @${sl:.4f} (3%, MARK_PRICE+保护)")
                    break
                except Exception as e:
                    if attempt == 2:
                        log(f"  ⚠️ 止损单失败, 客户端监控兜底: {e}")
                    else:
                        time.sleep(2)
            return True
        except Exception as e:
            log(f"  开仓失败 {symbol}: {e}")
            return False

    def close_position(self, symbol, qty):
        try:
            try:
                self.client.cancel_all_orders(symbol)
            except Exception as e:
                log(f"  ⚠️ 撤止损单失败: {e}")
            self.client.create_order(symbol, "BUY", "MARKET", qty, reduce_only=True)
            log(f"  平仓 {symbol} {qty}")
            return True
        except Exception as e:
            log(f"  平仓失败 {symbol}: {e}")
            return False

    def calc_qty(self, bal, price, step, min_qty, notional_cap):
        """固定名义仓位, 不超总资金×BAL_PCT×LEVERAGE"""
        notional = min(notional_cap, bal * BAL_PCT * LEVERAGE)
        qty = notional / price
        qty = math.floor(qty / step) * step
        # 清浮点尾数
        step_str = format(step, 'f')
        dec = len(step_str.split('.')[-1]) if '.' in step_str else 0
        qty = round(qty, dec)
        if qty < min_qty:
            return 0
        return qty

    # ---------- 主循环 ----------
    def run(self):
        log("=" * 60)
        log(f"TradingBot 启动 | 品种 {self.symbols} | 杠杆{LEVERAGE}x | 止损{STOP_PCT*100:.0f}%")

        # 启动接管已有持仓
        try:
            pos_list = self.client.get_position_risk()
            if isinstance(pos_list, list):
                for p in pos_list:
                    amt = float(p.get('positionAmt', 0) or 0)
                    if amt == 0 or p.get('symbol', '') not in self.symbols:
                        continue
                    entry = float(p.get('entryPrice', 0) or 0)
                    direction = 'LONG' if amt > 0 else 'SHORT'
                    self.positions[p['symbol']] = {
                        'qty': abs(amt), 'entry': entry,
                        'sl': entry * (1 + STOP_PCT) if direction == 'SHORT' else entry * (1 - STOP_PCT),
                        'open_time': time.time()}
                    log(f"  接管已有{direction}仓 {p['symbol']}: {abs(amt)} @{entry:.4f}")
        except Exception as e:
            log(f"  ⚠️ 接管持仓失败: {e}")

        while True:
            try:
                bal, err = self.get_balance()
                if bal is None:
                    log(f"⚠️ 余额获取失败: {err}")
                    time.sleep(300)
                    continue
                now = time.time()

                # 持仓同步 (止损单触发后释放内存)
                try:
                    real_all = self.client.get_position_risk()
                    real_map = {}
                    if isinstance(real_all, list):
                        for p in real_all:
                            if abs(float(p.get('positionAmt', 0) or 0)) > 0:
                                real_map[p.get('symbol', '')] = abs(float(p['positionAmt']))
                    for sym in list(self.positions.keys()):
                        if real_map.get(sym, 0) <= 0:
                            log(f"  ⚠️ {sym} 实际持仓已清零, 释放记录")
                            del self.positions[sym]
                except Exception as e:
                    log(f"  ⚠️ 持仓同步失败: {e}")

                # 持仓管理
                for sym in list(self.positions.keys()):
                    pos = self.positions[sym]
                    try:
                        import requests as _rq
                        ticker = float(_rq.get(
                            f"https://fapi.asterdex.com/fapi/v3/ticker/price",
                            params={"symbol": sym}, timeout=15).json().get('price', 0))
                    except:
                        continue
                    held_h = (now - pos['open_time']) / 3600
                    if ticker >= pos['sl']:  # SHORT止损 (价格上行触发)
                        log(f"  🛑 止损 {sym} 价格{ticker:.4f} (线{pos['sl']:.4f})")
                        if self.close_position(sym, pos['qty']):
                            self.consecutive_losses += 1
                            if self.consecutive_losses >= COOL_LOSSES:
                                self.cool_until = now + COOL_SECONDS
                                log(f"  ❄️ 连亏{self.consecutive_losses}次, 冷却{COOL_SECONDS//3600}h")
                            del self.positions[sym]
                        continue
                    if self.exit_signal(sym):
                        log(f"  🎯 出场信号 {sym} 价格{ticker:.4f}")
                        if self.close_position(sym, pos['qty']):
                            self.consecutive_losses = 0
                            del self.positions[sym]
                        continue
                    if held_h >= MAX_HOLD_HOURS:
                        log(f"  ⏰ 超时平仓 {sym} 持仓{held_h:.0f}h")
                        if self.close_position(sym, pos['qty']):
                            del self.positions[sym]
                        continue

                # 冷却
                if self.consecutive_losses >= COOL_LOSSES:
                    if now < self.cool_until:
                        time.sleep(SCAN_INTERVAL)
                        continue
                    log("冷却结束, 恢复交易")
                    self.consecutive_losses = 0

                # 新开仓
                if len(self.positions) >= len(self.symbols):
                    time.sleep(SCAN_INTERVAL)
                    continue
                for sym in self.symbols:
                    if sym in self.positions:
                        continue
                    sig = self.signal(sym)
                    if sig and bal > 5:
                        direction, price = sig
                        qty = self.calc_qty(bal, price, 0.01, 0.01, 540.0)
                        if qty > 0:
                            log(f"  📉 信号 {sym} {direction} @${price:.4f} 数量{qty}")
                            if self.open_position(sym, direction, price, qty):
                                self.positions[sym] = {'qty': qty, 'entry': price,
                                                       'sl': price * (1 + STOP_PCT) if direction == "SHORT" else price * (1 - STOP_PCT),
                                                       'open_time': now}
                                self.consecutive_losses = 0
                            time.sleep(5)

                time.sleep(SCAN_INTERVAL)
            except KeyboardInterrupt:
                log("手动停止")
                break
            except Exception as e:
                log(f"主循环异常: {e}")
                time.sleep(60)


if __name__ == "__main__":
    print("这是框架库, 请参考 examples/strategy_demo.py 使用")
