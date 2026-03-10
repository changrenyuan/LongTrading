import os
import json
import pandas as pd
from utils.logger import global_logger as logger
from utils.metrics import MetricsCalculator
from data_provider.cloudakpd import DataCenter # 确保引入云端数据中心
class LedgerManager:
    def __init__(self, manual_file="data/live_broker_account.json", system_file="data/system_account.json",
                 rich_ledger_file="data/live_trade_ledger.csv",summary_file="data/portfolio_assets.json"):
        self.manual_file = manual_file
        self.system_file = system_file
        self.rich_ledger_file = rich_ledger_file
        self.nav_file = "data/daily_nav.csv"
        self.summary_file = summary_file

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

    def sync_manual_to_system(self, universe_manager):
        """
        💡 核心逻辑：人工账本 -> 系统账本 (全量补全)
        调用 UniverseManager 实时补全名称、现价、盈亏。
        """
        if not os.path.exists(self.manual_file):
            logger.error("❌ 同步失败：人工账本不存在。")
            return False

        try:
            # 1. 读取人工输入的“干货” (只有代码、股数、成本)
            with open(self.manual_file, 'r', encoding='utf-8') as f:
                manual_data = json.load(f)

            # 2. 读取旧系统账本用于保留“最高价”等记忆
            old_sys_lookup = {}
            if os.path.exists(self.system_file):
                with open(self.system_file, 'r', encoding='utf-8') as f:
                    old_sys_lookup = {p['symbol']: p for p in json.load(f).get('positions', [])}

            new_sys_data = {
                "available_cash": manual_data.get("available_cash", 0.0),
                "positions": []
            }

            # 3. 遍历人工持仓，利用云端数据“点石成金”
            for m_pos in manual_data.get("positions", []):
                sym = m_pos['symbol']
                shares = m_pos.get('shares', 0)
                cost_price = m_pos.get('cost_price', 0.0)

                # 从 UniverseManager (云端快照) 拿现成的数据
                name = universe_manager.get_sym_name(sym)
                curr_price = universe_manager.get_spot_val(sym, universe_manager.price_col)
                curr_price = float(curr_price) if curr_price else cost_price

                # 计算实时盈亏
                cost_value = shares * cost_price
                market_value = shares * curr_price
                pnl = market_value - cost_value
                pnl_pct = (pnl / cost_value * 100) if cost_value > 0 else 0.0

                # 保留最高价记忆，用于计算回撤
                highest = old_sys_lookup.get(sym, {}).get('highest_price', curr_price)
                highest = max(highest, curr_price)

                new_sys_data["positions"].append({
                    "symbol": sym,
                    "name": name,
                    "shares": shares,
                    "cost_price": round(cost_price, 3),
                    "current_price": round(curr_price, 3),
                    "pnl": round(pnl, 2),
                    "pnl_pct": f"{pnl_pct:+.2f}%",
                    "highest_price": round(highest, 3),
                    "buy_date": old_sys_lookup.get(sym, {}).get('buy_date', '手动录入'),
                    "buy_reason": old_sys_lookup.get(sym, {}).get('buy_reason', '手动同步')
                })

            # 4. 存盘
            with open(self.system_file, 'w', encoding='utf-8') as f:
                json.dump(new_sys_data, f, indent=4, ensure_ascii=False)

            logger.info("✅ 账本同步完成：已根据云端快照补全所有持仓明细。")
            return True
        except Exception as e:
            logger.error(f"❌ 同步过程崩溃: {e}")
            return False


    def update_assets_snapshot(self):
        """
        🎯 核心资产审计：云端价格对齐 + 15分钟保鲜期校验 + 实时精算存盘
        """
        # 1. 💡 云端数据对齐 (处理您要求的 15 分钟逻辑)
        dc = DataCenter()
        # sync_market_snapshot 内部已包含：判断交易日、检查上次更新是否超过 15 分钟
        # 如果超过 15 分钟，它会自动调用云端 API 刷新数据库
        dc.sync_market_snapshot(refresh_interval_hours=0.1)
        df_cloud = dc.get_snapshot_from_cloud()

        if df_cloud.empty:
            logger.warning("⚠️ 云端行情读取为空，将使用系统账本中的历史价格进行精算")
            price_lookup = {}
        else:
            # 建立 {代码: 最新价} 的快速查询表
            price_lookup = dict(zip(df_cloud['symbol'], df_cloud['latest_price']))

        # 2. 读取系统账本（包含当前现金和持仓股数）
        if not os.path.exists(self.system_file):
            return None
        with open(self.system_file, 'r', encoding='utf-8') as f:
            sys_raw = json.load(f)

        cash = float(sys_raw.get("available_cash", 0.0))
        positions = sys_raw.get("positions", [])

        # 3. 🛠️ 实时精算：使用云端最新价格更新所有持仓
        total_market_value = 0.0
        total_cost_value = 0.0

        for p in positions:
            sym = p['symbol']
            shares = float(p.get('shares', 0))
            cost_price = float(p.get('cost_price', 0))

            # 优先级：云端最新价 > 账本原有价 > 成本价
            curr_price = price_lookup.get(sym, p.get('current_price', cost_price))

            p['current_price'] = round(curr_price, 3)
            p['pnl'] = round((curr_price - cost_price) * shares, 2)
            p['pnl_pct'] = f"{((curr_price / cost_price) - 1) * 100:+.2f}%" if cost_price > 0 else "0.00%"

            total_market_value += (curr_price * shares)
            total_cost_value += (cost_price * shares)

        # 4. 账户维度精算
        current_equity = round(cash + total_market_value, 2)
        position_pnl = round(total_market_value - total_cost_value, 2)

        # 当日盈亏计算 (基于今日实时总资产与昨日 NAV 存盘的差值)
        daily_pnl = 0.0
        daily_pnl_pct = 0.0
        if os.path.exists(self.nav_file):
            df_nav = pd.read_csv(self.nav_file)
            if not df_nav.empty:
                last_equity = df_nav.iloc[-1]['Equity']
                daily_pnl = round(current_equity - last_equity, 2)
                daily_pnl_pct = round((daily_pnl / last_equity) * 100, 2) if last_equity > 0 else 0.0

        # 5. 组装全量资产快照
        snapshot = {
            "available_cash": cash,
            "positions": positions,
            "pnl_summary": {
                "position_pnl": position_pnl,
                "daily_pnl": daily_pnl,
                "daily_pnl_pct": daily_pnl_pct
            },
            "metrics": {
                "total_equity": current_equity,
                "total_pnl": round(position_pnl, 2),
                "market_value": round(total_market_value, 2),
                "annualized_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "calmar_ratio": 0.0
                # 这里可以根据需要计算年化、夏普等...
            },
            "updated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # 6. 💾 物理落盘 (API 接口读取的唯一来源)
        assets_json = os.path.join(os.path.dirname(self.system_file), "portfolio_assets.json")
        with open(assets_json, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=4, ensure_ascii=False)

        logger.info(f"✅ 资产审计完成。当前净资产: {current_equity}, 云端对齐已完成。")
        return snapshot