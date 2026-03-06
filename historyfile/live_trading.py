import os
import glob
import json
import pandas as pd
from datetime import datetime
import re

# ==========================================
# 🔴 核心模块导入
# ==========================================
from data_provider.akshare_pd import AkShareProvider
from strategies.trend import InstitutionalTrendStrategy
from core.account import Portfolio, Position
from utils.logger import global_logger as logger
from utils.notifier import MessagePusher  # 💡 导入新增的推送模块

# 常量定义
MANUAL_ACCOUNT_FILE = "data/live_broker_account.json"  # 人工维护的真实账本
SYSTEM_ACCOUNT_FILE = "data/system_account.json"  # 系统自动生成的预期账本


def get_latest_live_params(log_dir="data/tuning_logs"):
    csv_files = glob.glob(f"{log_dir}/optuna_log_*.csv") + glob.glob("optuna_log_*.csv")
    if not csv_files:
        logger.warning("未找到调参日志，将使用备用默认参数！")
        return {'ma_short': 5, 'ma_mid': 12, 'ma_long': 50, 'bias_entry_limit': 1.05,
                'pullback_support_upper': 1.04, 'stop_loss_pct': 0.10, 'trailing_stop_pct': 0.20,
                'profit_tier2': 1.10, 'trailing_tier2': 0.06}

    latest_csv = max(csv_files, key=os.path.getmtime)
    df = pd.read_csv(latest_csv)
    top1 = df.sort_values(by="value", ascending=False).iloc[0]

    live_params = {}
    for col in top1.index:
        if col.startswith("params_"):
            key = col.replace("params_", "")
            val = top1[col]
            if pd.isna(val): continue
            if isinstance(val, float) and val.is_integer():
                live_params[key] = int(val)
            else:
                live_params[key] = round(val, 4) if isinstance(val, float) else val

    base_cfg = {
        'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9, 'vol_ma_window': 20,
        'trend_ma_diff': 5, 'trend_strength_buffer': 1.05, 'pullback_bias_limit': 1.05,
        'pullback_support_lower': 0.95, 'trend_broken_lower': 0.98, 'trend_broken_vol': 1.2,
        'lot_size': 100, 'est_commission': 0.0003, 'enable_partial_exit': False
    }
    live_params.update(base_cfg)
    if 'unit_size' in live_params: live_params['max_units'] = int(1.0 // live_params['unit_size'])

    # 💡 透明汇报读取到的核心参数与来源
    logger.info("-" * 80)
    logger.info(f"⚙️ 【策略参数装载与核对】")
    logger.info(f"   - 寻优参数文件路径 : {os.path.abspath(latest_csv)}")
    dynamic_params = {k: v for k, v in live_params.items() if k not in base_cfg}
    param_str = ", ".join([f"{k}: {v}" for k, v in dynamic_params.items()])
    logger.info(f"   - 注入动态寻优参数 : {param_str}")
    logger.info("-" * 80)

    return live_params


def get_live_target_pool(top_n=5):
    csv_files = glob.glob("data_provider/test_cache_data/*spot*.csv") + glob.glob(
        "data_provider/test_cache_data/*snapshot*.csv") + glob.glob("data/*snapshot*.csv")
    if not csv_files: return ["300308", "601138"], "UNKNOWN"

    csv_path = max(csv_files, key=os.path.getmtime)
    filename = os.path.basename(csv_path)
    logger.info(f"📡 正在读取全市场成交额 Top {top_n} (数据源: {filename})...")

    try:
        spot_df = pd.read_csv(csv_path, dtype=str)
        code_col = '代码' if '代码' in spot_df.columns else 'symbol'
        amount_col = '成交额' if '成交额' in spot_df.columns else 'amount'
        name_col = '名称' if '名称' in spot_df.columns else 'name'
        spot_df['clean_code'] = spot_df[code_col].str.extract(r'(\d{6})')
        spot_df = spot_df.dropna(subset=['clean_code'])
        if name_col in spot_df.columns:
            spot_df = spot_df[~spot_df[name_col].astype(str).str.contains('ST')]
        spot_df = spot_df[spot_df['clean_code'].str.startswith(('60', '00', '30'))]
        spot_df[amount_col] = pd.to_numeric(spot_df[amount_col], errors='coerce').fillna(0)
        spot_df = spot_df.sort_values(by=amount_col, ascending=False).head(top_n)
        return spot_df['clean_code'].tolist(), filename
    except Exception as e:
        logger.error(f"提取股票失败: {e}")
        return [], "ERROR"


def load_and_reconcile_ledgers():
    """读取并核对系统应有账本与人工真实账本"""
    if not os.path.exists(MANUAL_ACCOUNT_FILE):
        os.makedirs(os.path.dirname(MANUAL_ACCOUNT_FILE), exist_ok=True)
        with open(MANUAL_ACCOUNT_FILE, 'w', encoding='utf-8') as f:
            json.dump({"available_cash": 1000000.0, "positions": []}, f, indent=4, ensure_ascii=False)
        return None, None

    with open(MANUAL_ACCOUNT_FILE, 'r', encoding='utf-8') as f:
        manual_data = json.load(f)

    system_data = None
    if os.path.exists(SYSTEM_ACCOUNT_FILE):
        with open(SYSTEM_ACCOUNT_FILE, 'r', encoding='utf-8') as f:
            system_data = json.load(f)

    if system_data:
        logger.info("⚖️ 正在执行【双账本对账】...")
        sys_pos = {p['symbol']: p['shares'] for p in system_data.get('positions', [])}
        man_pos = {p['symbol']: p['shares'] for p in manual_data.get('positions', [])}

        all_syms = set(list(sys_pos.keys()) + list(man_pos.keys()))
        for sym in all_syms:
            sys_shares = sys_pos.get(sym, 0)
            man_shares = man_pos.get(sym, 0)

            if sys_shares != man_shares:
                if sys_shares > 0 and man_shares == 0:
                    logger.error(
                        f"🚨 【对账异常】 {sym} 系统应有 {sys_shares} 股，真实账本 0 股。判定: 老板未执行买入/手工平仓。已强制回退基准！")
                elif sys_shares == 0 and man_shares > 0:
                    logger.error(
                        f"🚨 【对账异常】 {sym} 系统应有 0 股，真实账本 {man_shares} 股。判定: 老板未执行卖出。重新接管防守！")
                else:
                    logger.warning(
                        f"🚨 【对账异常】 {sym} 数量不符 (系统{sys_shares} != 真实{man_shares})。强制修正为真实数量！")

    return float(manual_data.get("available_cash", 0.0)), manual_data.get("positions", [])


def save_system_ledger(account, strategy):
    """实盘结束后，将系统今日执行后的最新状态持久化"""
    sys_data = {
        "available_cash": account.total_cash,
        "positions": []
    }
    for sym, pos in account.positions.items():
        peak = strategy.pos_state.get(sym, {}).get('peak_price', pos.avg_price)
        sys_data["positions"].append({
            "symbol": sym,
            "shares": pos.shares,
            "cost_price": pos.avg_price,
            "highest_price": peak
        })

    with open(SYSTEM_ACCOUNT_FILE, 'w', encoding='utf-8') as f:
        json.dump(sys_data, f, indent=4, ensure_ascii=False)
    logger.info(f"💾 【系统账本】已更新，明日对账将以此为依据: {SYSTEM_ACCOUNT_FILE}")


def main():
    logger.info("=" * 80)
    logger.info(f" 🚀 启动量化交易实盘中心 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")

    # 动态打印所有文件的物理路径
    sys_log_path = "logs/ 系统可能未开启文件日志"
    if logger.handlers:
        for handler in logger.handlers:
            if hasattr(handler, 'baseFilename'):
                sys_log_path = handler.baseFilename
                break

    logger.info(f"   - 📝 系统运行日志 : {sys_log_path}")
    logger.info(f"   - 📒 人工比对账本 : {os.path.abspath(MANUAL_ACCOUNT_FILE)}")
    logger.info(f"   - 💾 系统预演账本 : {os.path.abspath(SYSTEM_ACCOUNT_FILE)}")
    logger.info(f"   - 💸 实盘交易流水 : {os.path.abspath('data/live_trade_ledger.csv')}")
    logger.info("=" * 80)

    # 1. 载入参数与快照数据总线
    live_cfg = get_latest_live_params()
    provider = AkShareProvider()

    price_col, open_col, high_col, low_col, vol_col, turn_col, name_col = [None] * 7
    try:
        spot_df = provider.get_market_snapshot()
        if not spot_df.empty:
            code_raw = '代码' if '代码' in spot_df.columns else ('code' if 'code' in spot_df.columns else 'symbol')
            spot_df['clean_code'] = spot_df[code_raw].astype(str).str.extract(r'(\d{6})')
            spot_df = spot_df.dropna(subset=['clean_code'])
            spot_df.set_index('clean_code', inplace=True)
            price_col = '最新价' if '最新价' in spot_df.columns else ('trade' if 'trade' in spot_df.columns else None)
            open_col = '今开' if '今开' in spot_df.columns else 'open'
            high_col = '最高' if '最高' in spot_df.columns else 'high'
            low_col = '最低' if '最低' in spot_df.columns else 'low'
            vol_col = '成交量' if '成交量' in spot_df.columns else 'volume'
            turn_col = '换手率' if '换手率' in spot_df.columns else 'turnoverratio'
            name_col = '名称' if '名称' in spot_df.columns else ('name' if 'name' in spot_df.columns else None)
    except Exception as e:
        logger.warning(f"获取全市场快照异常，退回日线: {e}")
        spot_df = pd.DataFrame()

    def get_spot_val(sym, col_name, fallback=None):
        if spot_df.empty or sym not in spot_df.index or not col_name: return fallback
        info = spot_df.loc[sym]
        if isinstance(info, pd.DataFrame): info = info.iloc[0]
        val = info.get(col_name)
        if pd.isna(val) or val == '-' or val == '': return fallback
        return val

    def get_sym_name(sym):
        return str(get_spot_val(sym, name_col, sym))

    # 2. 执行双账本审计与接管
    radar_symbols, source_file = get_live_target_pool(top_n=5)
    available_cash, positions_list = load_and_reconcile_ledgers()
    if available_cash is None:
        return logger.error("🚨 请填入真实的 live_broker_account.json 后重试！")

    held_symbols = [str(pos.get('symbol', '')) for pos in positions_list if int(pos.get('shares', 0)) > 0]
    final_target_symbols = list(dict.fromkeys(held_symbols + radar_symbols))

    # 💡 恢复遗失的特性：向老板汇报接管情况
    logger.info(
        f"🏦 会计部接管完毕: 真实可用现金 【{available_cash:,.2f} 元】，真实持仓 【{len(held_symbols)} 只】，雷达标的 【{len(radar_symbols)} 只】。")

    # 3. 初始化大管家 (指派专属实盘交易流水 CSV)
    live_ledger_file = "data/live_trade_ledger.csv"
    account = Portfolio(initial_cash=available_cash, symbols=final_target_symbols, ledger_path=live_ledger_file)
    # account.central_vault = available_cash
    for pos_data in positions_list:
        sym = str(pos_data.get('symbol', ''))
        shares = int(pos_data.get('shares', 0))
        cost = float(pos_data.get('cost_price', 0.0))
        if shares > 0 and cost > 0 and sym:
            pos_obj = Position(sym)
            pos_obj.shares = shares
            pos_obj.avg_price = cost
            account.positions[sym] = pos_obj

    # 4. 💡 恢复遗失的特性：盘前宏观资产核算看板 (NAV Dashboard)
    total_cost, total_market_value = 0.0, 0.0
    for sym, pos_obj in account.positions.items():
        current_price = get_spot_val(sym, price_col)
        if current_price:
            total_cost += pos_obj.cost
            total_market_value += pos_obj.shares * float(current_price)
        else:
            total_cost += pos_obj.cost
            total_market_value += pos_obj.cost

    current_equity = account.total_cash + total_market_value
    floating_pnl = total_market_value - total_cost
    floating_pnl_pct = (floating_pnl / total_cost * 100) if total_cost > 0 else 0.0

    logger.info("-" * 80)
    logger.info("【盘前资产风控评估 (Pre-Trade NAV Dashboard)】")
    logger.info(f"   - 可用现金 (Available Cash) : {account.total_cash:,.2f}")
    logger.info(f"   - 持仓成本 (Total Cost)     : {total_cost:,.2f}")
    logger.info(f"   - 持仓市值 (Market Value)   : {total_market_value:,.2f}")
    logger.info(f"   - 净 资 产 (Total Equity)   : {current_equity:,.2f}")
    logger.info(f"   - 账面浮盈 (Floating PnL)   : {floating_pnl:,.2f} ({floating_pnl_pct:.2f}%)")
    logger.info("-" * 80)

    # 5. K线历史拉取与当日脉搏注入
    data_dict = {}
    current_date_str = datetime.now().strftime("%Y-%m-%d")

    for sym in final_target_symbols:
        df = provider.get_data(sym)
        if df.empty or len(df) < live_cfg['ma_long']: continue

        last_date = pd.to_datetime(df.index[-1]).strftime("%Y-%m-%d")
        sym_name = get_sym_name(sym)

        if last_date != current_date_str and not spot_df.empty and sym in spot_df.index and price_col:
            try:
                last_close = float(df.iloc[-1]['close'])
                today_kline = pd.DataFrame([{
                    'open': float(get_spot_val(sym, open_col, last_close)),
                    'high': float(get_spot_val(sym, high_col, last_close)),
                    'low': float(get_spot_val(sym, low_col, last_close)),
                    'close': float(get_spot_val(sym, price_col, last_close)),
                    'volume': float(get_spot_val(sym, vol_col, 0.0)),
                    'turnover': float(get_spot_val(sym, turn_col, 0.0))
                }], index=[pd.to_datetime(current_date_str)])
                today_kline.index.name = 'date'

                if today_kline.iloc[0]['close'] > 0:
                    df = pd.concat([df, today_kline])
                    logger.info(f"⚡ [{sym} {sym_name}] 盘中数据注入成功！(今日跳动现价: {today_kline.iloc[0]['close']})")
            except Exception as e:
                logger.error(f"[{sym} {sym_name}] 盘中数据注入失败: {e}")

        data_dict[sym] = df

        # 💡 恢复遗失的特性：强力打印最新 3 行数据让老板检查
        logger.debug(f"\n📊 [{sym} {sym_name}] 最新 3 行数据切片检查:\n{df.tail(3).to_string()}\n" + "-" * 60)

    if not data_dict: return logger.error("数据注入失败，无可用标的，程序终止。")

    # 6. 策略计算与指令生成
    strategy = InstitutionalTrendStrategy(cfg=live_cfg, symbols=final_target_symbols)

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

    buy_orders, sell_orders, hold_reports, rejected_orders = [], [], [], []
    sold_symbols_today = []

    for symbol, df_analyzed in indicators_dict.items():
        sym_name = get_sym_name(symbol)
        today_bar = df_analyzed.iloc[-1]
        action, intent_shares = strategy.on_bar(today_bar, account, symbol)
        price = today_bar['close']
        cost = account.get_avg_price(symbol)
        held_shares = account.get_shares(symbol)

        if action in ["BUY", "SELL"]:
            reason = strategy.intended_signals[-1]['reason'] if strategy.intended_signals else "触发买卖点"
            trade_result = account.execute_trade(symbol=symbol, action=action, shares=intent_shares, price=price,
                                                 current_time=current_date_str)

            if trade_result['success']:
                filled_shares = trade_result['filled_shares']
                fee = trade_result['fee']
                trade_value = trade_result['trade_value']

                if action == "SELL":
                    sold_symbols_today.append(symbol)
                    profit_pct = (price - cost) / cost if cost > 0 else 0
                    sell_orders.append(
                        f"🔴 {symbol} ({sym_name}) 卖出 {filled_shares} 股 | 现价: {price:.2f}\n"
                        f"   - 回笼资金: {trade_value:,.2f} 元 (扣减税费 {fee:.2f} 元)\n"
                        f"   - 逻辑: {reason} (单笔盈亏: {profit_pct * 100:.2f}%)"
                    )
                else:
                    status = "建仓" if held_shares == 0 else "加仓"
                    buy_orders.append(
                        f"🟢 {symbol} ({sym_name}) {status} {filled_shares} 股 | 现价: {price:.2f}\n"
                        f"   - 动用资金: {trade_value:,.2f} 元 (预扣佣金 {fee:.2f} 元)\n"
                        f"   - 逻辑: {reason}"
                    )
            else:
                rejected_orders.append(
                    f"⛔ {symbol} ({sym_name}) 拦截: 试图 {action} {intent_shares} 股。原因: {trade_result['message']}")
        else:
            if held_shares > 0:
                profit_pct = (price - cost) / cost if cost > 0 else 0
                peak = strategy.pos_state[symbol]['peak_price']
                hold_reports.append(
                    f"🛡️ {symbol} ({sym_name}) 持仓 {held_shares} 股 | 现价: {price:.2f} | 浮盈: {profit_pct * 100:.2f}%")

    # 7. 落库记录与手机推送
    save_system_ledger(account, strategy)

    logger.info("=" * 80)
    logger.info("【操作审批纪要 (Execution Summary)】")
    if sell_orders:
        for o in sell_orders: logger.info(o)
    if buy_orders:
        for o in buy_orders: logger.info(o)
    if not sell_orders and not buy_orders:
        logger.info("   无操作指令。")
    if rejected_orders:
        for o in rejected_orders: logger.warning(o)

    logger.info("\n【持仓状态确认 (Positions Audit)】")
    if hold_reports:
        for report in hold_reports: logger.info(report)
    else:
        logger.info("   - 当前未持有任何底层资产。")

    logger.info("=" * 80)
    logger.info("👀 【交易额最大监控池 (拒绝交易名单)】")
    watched_count = 0
    for symbol, df_analyzed in indicators_dict.items():
        if account.get_shares(symbol) == 0 and symbol not in sold_symbols_today:
            today_bar = df_analyzed.iloc[-1]
            bias = today_bar.get('Bias', 999)
            is_bullish = today_bar.get('Strong_Trend', False)
            if not is_bullish:
                reason = "未形成多头排列"
            elif bias > live_cfg['bias_entry_limit']:
                reason = f"乖离率偏高 ({bias:.2f})"
            else:
                reason = "未满足缩量回踩或放量突破"
            logger.info(f"   - 🚫 观望 {symbol} ({get_sym_name(symbol)}): {reason}")
            watched_count += 1

    if watched_count == 0: logger.info("   (无监控池或已全部发车)")

    # 推送手机 Markdown 战报
    pusher = MessagePusher()
    md_content = f"**净资产评估**: {current_equity:,.2f} 元\n" \
                 f"**今日总浮盈**: {floating_pnl:,.2f} 元\n\n" \
                 f"### 🛑 清仓/防守指令:\n" + (
                     "\n".join([f"- {o}" for o in sell_orders]) if sell_orders else "- 无\n") + "\n" \
                                                                                                f"### 🎯 建仓/加仓指令:\n" + (
                     "\n".join([f"- {o}" for o in buy_orders]) if buy_orders else "- 无\n")

    pusher.push_message(title="【MT_Alpha】实盘交易指令核对", content=md_content)


if __name__ == "__main__":
    main()