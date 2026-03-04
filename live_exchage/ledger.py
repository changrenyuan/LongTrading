import os
import json
import pandas as pd
from utils.logger import global_logger as logger


class LedgerManager:
    def __init__(self, manual_file="data/live_broker_account.json", system_file="data/system_account.json",
                 rich_ledger_file="data/live_trade_ledger.csv"):
        self.manual_file = manual_file
        self.system_file = system_file
        self.rich_ledger_file = rich_ledger_file
        self.nav_file = "data/daily_nav.csv"

    def load_and_reconcile_ledgers(self):
        if not os.path.exists(self.manual_file):
            os.makedirs(os.path.dirname(self.manual_file), exist_ok=True)
            with open(self.manual_file, 'w', encoding='utf-8') as f:
                json.dump({"available_cash": 10000000.0, "positions": []}, f, indent=4, ensure_ascii=False)
            return None, None

        with open(self.manual_file, 'r', encoding='utf-8') as f:
            manual_data = json.load(f)

        system_data = None
        if os.path.exists(self.system_file):
            with open(self.system_file, 'r', encoding='utf-8') as f:
                system_data = json.load(f)

        man_pos = {p['symbol']: p['shares'] for p in manual_data.get('positions', [])}
        sys_pos = {p['symbol']: p['shares'] for p in system_data.get('positions', [])} if system_data else {}

        # 💡 核心修复：严谨的订单审计与核销逻辑
        if os.path.exists(self.rich_ledger_file):
            try:
                df_orders = pd.read_csv(self.rich_ledger_file, dtype=str)
                if 'Status' not in df_orders.columns: df_orders['Status'] = '已记录'

                modified = False
                for idx, row in df_orders.iterrows():
                    if row.get('Status') == '待确认':
                        sym = str(row.get('Symbol', '')).zfill(6)

                        # 只有系统的预期股数和老板的真实股数【完全一致】，才算听从了建议
                        sys_shares = sys_pos.get(sym, 0)
                        man_shares = man_pos.get(sym, 0)

                        if sys_shares == man_shares:
                            df_orders.at[idx, 'Status'] = '✅ 老板已执行'
                        else:
                            df_orders.at[idx, 'Status'] = '❌ 建议未执行(忽略)'
                        modified = True

                if modified: df_orders.to_csv(self.rich_ledger_file, index=False)
            except Exception as e:
                logger.error(f"订单状态对账失败: {e}")

        # 记录对账异常并准备回退
        if system_data:
            all_syms = set(list(sys_pos.keys()) + list(man_pos.keys()))
            for sym in all_syms:
                if sys_pos.get(sym, 0) != man_pos.get(sym, 0):
                    logger.warning(
                        f"🚨 【对账异常】 {sym} 系统应有 {sys_pos.get(sym, 0)} 与 真实持有 {man_pos.get(sym, 0)}不一致。系统已强制以人工为准重新校准！")

        return float(manual_data.get("available_cash", 0.0)), manual_data.get("positions", [])
    def save_system_ledger(self, account, strategy, universe_manager):
        sys_data = {"available_cash": account.total_cash, "positions": []}
        for sym, pos in account.positions.items():
            peak = strategy.pos_state.get(sym, {}).get('peak_price', pos.avg_price)
            curr_price = universe_manager.get_spot_val(sym, universe_manager.price_col)
            try:
                curr_price_float = float(curr_price) if curr_price else pos.avg_price
                cost_value = pos.shares * pos.avg_price
                market_value = pos.shares * curr_price_float
                pnl = market_value - cost_value
                pnl_pct = (pnl / cost_value * 100) if cost_value > 0 else 0.0
            except:
                curr_price_float, pnl, pnl_pct = pos.avg_price, 0.0, 0.0

            sys_data["positions"].append({
                "symbol": sym, "name": universe_manager.get_sym_name(sym), "shares": pos.shares,
                "cost_price": round(pos.avg_price, 3), "current_price": round(curr_price_float, 3),
                "pnl": round(pnl, 2), "pnl_pct": f"{pnl_pct:+.2f}%", "highest_price": round(peak, 3),
                "buy_date": getattr(pos, 'buy_date', '未知'), "buy_reason": getattr(pos, 'buy_reason', '未知')
            })
        with open(self.system_file, 'w', encoding='utf-8') as f:
            json.dump(sys_data, f, indent=4, ensure_ascii=False)

    def append_live_ledger_with_reason(self, date_str, symbol, name, action, shares, price, reason, status="待确认"):
        file_exists = os.path.exists(self.rich_ledger_file)
        with open(self.rich_ledger_file, 'a', encoding='utf-8') as f:
            if not file_exists: f.write("Date,Symbol,Name,Action,Shares,Price,Reason,Status\n")
            f.write(f"{date_str},{symbol},{name},{action},{shares},{price},{str(reason).replace(',', '，')},{status}\n")

    def record_daily_nav(self, date_str, total_equity):
        file_exists = os.path.exists(self.nav_file)
        if file_exists:
            df = pd.read_csv(self.nav_file)
            if not df.empty and df.iloc[-1]['Date'] == date_str:
                df.at[df.index[-1], 'Equity'] = total_equity
                df.to_csv(self.nav_file, index=False)
                return
        with open(self.nav_file, 'a', encoding='utf-8') as f:
            if not file_exists: f.write("Date,Equity\n")
            f.write(f"{date_str},{total_equity}\n")