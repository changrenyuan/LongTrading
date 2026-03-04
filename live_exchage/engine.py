import os
import pandas as pd
from datetime import datetime
from data_provider.akshare_pd import AkShareProvider
from strategies.trend import InstitutionalTrendStrategy
from core.account import Portfolio, Position
from utils.logger import global_logger as logger
from utils.notifier import MessagePusher

from .config import LiveConfig
from .universe import UniverseManager
from .ledger import LedgerManager
from .executor import TradeExecutor


class LiveEngine:
    def __init__(self):
        self.config = LiveConfig.get_latest_live_params()
        self.provider = AkShareProvider()
        self.universe = UniverseManager(self.provider)
        self.ledger = LedgerManager()
        self.executor = TradeExecutor(self.ledger)

    def run_daily_routine(self):
        logger.info("=" * 80)
        logger.info(f" 🚀 启动量化交易实盘中心 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        logger.info(f"   - 📒 人工比对账本 : {os.path.abspath(self.ledger.manual_file)}")
        logger.info(f"   - 💸 审计交易流水 : {os.path.abspath(self.ledger.rich_ledger_file)}")
        logger.info("=" * 80)

        # 1. 读账与核销
        available_cash, positions_list = self.ledger.load_and_reconcile_ledgers()
        if available_cash is None: return logger.error("🚨 请填入真实的 live_broker_account.json！")

        # 2. 活水股票池构建
        held_symbols = [str(pos.get('symbol', '')) for pos in positions_list if int(pos.get('shares', 0)) > 0]
        logger.info("📡 正在全盘扫描历史数据与近期快照，构建动态监控池...")
        target_symbols, scanned_days = self.universe.build_dynamic_stock_pool(held_symbols, max_size=20)
        logger.info(f"🏦 会计部接管完毕: 可用现金 【{available_cash:,.2f} 元】，真实持仓 【{len(held_symbols)} 只】，雷达标的 【{len(target_symbols)} 只】。")
        logger.info(f"🎯 监控池构建完毕: 汇聚近 {scanned_days} 日霸榜标的，实盘监控总数: 【{len(target_symbols)} 只】。")

        # 3. 初始化账户 (内部流水隔离，交由 ledger 写入 CSV)
        account = Portfolio(initial_cash=available_cash, symbols=target_symbols,
                            ledger_path="data/system_internal_ledger.csv")
        for pos_data in positions_list:
            sym = str(pos_data.get('symbol', ''))
            shares = int(pos_data.get('shares', 0))
            if shares > 0 and sym:
                pos_obj = Position(sym)
                pos_obj.shares = shares
                pos_obj.avg_price = float(pos_data.get('cost_price', 0.0))
                pos_obj.buy_date = pos_data.get('buy_date', '历史遗留')
                pos_obj.buy_reason = pos_data.get('buy_reason', '未知建仓逻辑')
                account.positions[sym] = pos_obj

        # 计算资产
        total_cost, total_market_value = 0.0, 0.0
        for sym, pos_obj in account.positions.items():
            curr_price = self.universe.get_spot_val(sym, self.universe.price_col)
            total_cost += pos_obj.cost
            total_market_value += pos_obj.shares * float(curr_price) if curr_price else pos_obj.cost

        current_equity = account.total_cash + total_market_value
        floating_pnl = total_market_value - total_cost
        floating_pnl_pct = (floating_pnl / total_cost * 100) if total_cost > 0 else 0.0

        # 💡 补回丢失的：盘前宏观资产核算看板 (NAV Dashboard)
        logger.info("-" * 80)
        logger.info("【盘前资产风控评估 (Pre-Trade NAV Dashboard)】")
        logger.info(f"   - 可用现金 (Available Cash) : {account.total_cash:,.2f}")
        logger.info(f"   - 持仓成本 (Total Cost)     : {total_cost:,.2f}")
        logger.info(f"   - 持仓市值 (Market Value)   : {total_market_value:,.2f}")
        logger.info(f"   - 净 资 产 (Total Equity)   : {current_equity:,.2f}")
        logger.info(f"   - 账面浮盈 (Floating PnL)   : {floating_pnl:,.2f} ({floating_pnl_pct:.2f}%)")
        logger.info("-" * 80)

        # 4. 数据拉取与切片注入
        data_dict = {}
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        for sym in target_symbols:
            df = self.provider.get_data(sym)
            if df.empty or len(df) < self.config['ma_long']: continue
            last_date = pd.to_datetime(df.index[-1]).strftime("%Y-%m-%d")
            sym_name = self.universe.get_sym_name(sym)

            if last_date != current_date_str and not self.universe.spot_df.empty and sym in self.universe.spot_df.index and self.universe.price_col:
                try:
                    last_close = float(df.iloc[-1]['close'])
                    today_kline = pd.DataFrame([{
                        'open': float(self.universe.get_spot_val(sym, self.universe.open_col, last_close)),
                        'high': float(self.universe.get_spot_val(sym, self.universe.high_col, last_close)),
                        'low': float(self.universe.get_spot_val(sym, self.universe.low_col, last_close)),
                        'close': float(self.universe.get_spot_val(sym, self.universe.price_col, last_close)),
                        'volume': float(self.universe.get_spot_val(sym, self.universe.vol_col, 0.0)),
                        'turnover': float(self.universe.get_spot_val(sym, self.universe.turn_col, 0.0))
                    }], index=[pd.to_datetime(current_date_str)])
                    today_kline.index.name = 'date'
                    if today_kline.iloc[0]['close'] > 0:
                        df = pd.concat([df, today_kline])
                        logger.info(f"⚡ [{sym} {sym_name}] 盘中数据注入成功！(跳动现价: {today_kline.iloc[0]['close']})")
                except Exception as e:
                    logger.error(f"[{sym} {sym_name}] 盘中注入失败: {e}")

            data_dict[sym] = df
            logger.debug(f"\n📊 [{sym} {sym_name}] 最新 3 行切片检查:\n{df.tail(3).to_string()}\n")

        if not data_dict: return logger.error("数据注入失败，无可用标的。")

        # 5. 策略执行
        strategy = InstitutionalTrendStrategy(cfg=self.config, symbols=target_symbols)

        def live_get_current_row(sym):
            return strategy.indicators[sym].iloc[-1] if sym in strategy.indicators else None

        strategy.get_current_row = live_get_current_row
        indicators_dict = strategy.prepare(data_dict)

        if positions_list:
            for pos in positions_list:
                sym = str(pos.get('symbol', ''))
                if sym in strategy.pos_state and int(pos.get('shares', 0)) > 0:
                    strategy.pos_state[sym]['units_held'] = 1
                    strategy.pos_state[sym]['peak_price'] = float(pos.get('highest_price', 0.0))

        buy_orders, sell_orders, hold_reports, rejected_orders, sold_symbols_today = [], [], [], [], []

        for symbol, df_analyzed in indicators_dict.items():
            sym_name = self.universe.get_sym_name(symbol)
            today_bar = df_analyzed.iloc[-1]
            action, intent_shares = strategy.on_bar(today_bar, account, symbol)
            price = today_bar['close']
            held_shares = account.get_shares(symbol)

            if action in ["BUY", "SELL"]:
                reason = strategy.intended_signals[-1]['reason'] if strategy.intended_signals else "触发买卖点"
                success, log_msg, order_type = self.executor.execute(symbol, sym_name, action, intent_shares, price,
                                                                     reason, account, current_date_str)
                if success:
                    if order_type == "SELL":
                        sold_symbols_today.append(symbol)
                        sell_orders.append(log_msg)
                    else:
                        buy_orders.append(log_msg)
                else:
                    rejected_orders.append(log_msg)
            else:
                if held_shares > 0:
                    profit_pct = (price - account.get_avg_price(symbol)) / account.get_avg_price(
                        symbol) if account.get_avg_price(symbol) > 0 else 0
                    b_date = getattr(account.positions[symbol], 'buy_date', '未知')
                    b_reason = getattr(account.positions[symbol], 'buy_reason', '未知')
                    hold_reports.append(
                        f"🛡️ {symbol} ({sym_name}) | 持仓 {held_shares} 股 | 现价: {price:.2f} | 浮盈: {profit_pct * 100:.2f}%\n"
                        f"   └─ 买入日期: {b_date} | 开仓逻辑: {b_reason}"
                    )


        # 6. 落库记忆、报告与净值
        self.ledger.save_system_ledger(account, strategy, self.universe)
        self.ledger.record_daily_nav(current_date_str, current_equity)  # 💡 新增：记录每日净值

        logger.info("=" * 80)
        logger.info("【操作审批纪要 (Execution Summary)】")
        for o in sell_orders: logger.info(o)
        for o in buy_orders: logger.info(o)
        if not sell_orders and not buy_orders: logger.info("   无操作指令。")
        for o in rejected_orders: logger.warning(o)

        logger.info("\n【持仓状态确认 (Positions Audit)】")
        if hold_reports:
            for report in hold_reports: logger.info(report)
        else:
            logger.info("   - 当前未持有任何底层资产。")

        logger.info("=" * 80)
        logger.info("👀 【交易额最大动态监控池 (优胜劣汰拒绝名单)】")
        for symbol, df_analyzed in indicators_dict.items():
            if account.get_shares(symbol) == 0 and symbol not in sold_symbols_today:
                today_bar = df_analyzed.iloc[-1]
                bias = today_bar.get('Bias', 999)
                if not today_bar.get('Strong_Trend', False):
                    reason = "未形成多头排列"
                elif bias > self.config['bias_entry_limit']:
                    reason = f"乖离率偏高 ({bias:.2f})"
                else:
                    reason = "未满足缩量回踩或放量突破"
                logger.info(f"   - 🚫 观望 {symbol} ({self.universe.get_sym_name(symbol)}): {reason}")

        # 推送消息
# ==========================================
        # 💡 高颜值机构级 Markdown 战报构建
        # ==========================================
        md_content = (
            f"🌈\n###  资产战报与密令    \n\n"
            f"- **净资产评估**：<font color='#1f77b4'>{current_equity:,.2f}</font> 元\n"
            f"- **今日总浮盈**：<font color='#ff7f0e'>{floating_pnl:,.2f}</font> 元\n\n"
            f"---\n\n"
            f"🎠\n###  防守与清仓\n"
        )
        if sell_orders:
            for o in sell_orders:
                # 使用标准的 blockquote 引用块包裹订单，看起来更具审批感
                md_content += f"> {o}\n\n"
        else:
            md_content += "> 🍵 \n暂无防守动作，系统静默持仓观望。\n\n"

        md_content += f"---\n\n㊙️\n ### 进攻与建仓\n"
        if buy_orders:
            for o in buy_orders:
                md_content += f"> {o}\n\n"
        else:
            md_content += "> 🍵 \n暂无进攻动作，耐心等待猎物出现。\n\n"

        # 发送终极优化的消息
        MessagePusher().push_message(title="37密码", content=md_content)