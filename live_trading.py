import os
import glob
import json
import pandas as pd
from datetime import datetime
import re

# ==========================================
# 🔴 核心模块导入：全面接管会计与策略模块
# ==========================================
from data_provider.akshare_pd import AkShareProvider
from strategies.trend import InstitutionalTrendStrategy
from core.account import Portfolio, Position
from utils.logger import global_logger as logger


def get_latest_live_params(log_dir="data/tuning_logs"):
    """提取最新量化实验室参数"""
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
                live_params[key] = val

    base_cfg = {
        'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9, 'vol_ma_window': 20,
        'trend_ma_diff': 5, 'trend_strength_buffer': 1.05, 'pullback_bias_limit': 1.05,
        'pullback_support_lower': 0.95, 'trend_broken_lower': 0.98, 'trend_broken_vol': 1.2,
        'lot_size': 100, 'est_commission': 0.0003, 'enable_partial_exit': False
    }
    live_params.update(base_cfg)
    if 'unit_size' in live_params: live_params['max_units'] = int(1.0 // live_params['unit_size'])
    return live_params


def get_live_target_pool(top_n=5):
    """提取实盘关注的雷达股票池 (只返回代码列表)"""
    csv_files = glob.glob("data_provider/test_cache_data/*spot*.csv") + glob.glob(
        "data_provider/test_cache_data/*snapshot*.csv") + glob.glob("data/*snapshot*.csv")

    if not csv_files:
        return ["300308", "601138"], "UNKNOWN"

    csv_path = max(csv_files, key=os.path.getmtime)
    filename = os.path.basename(csv_path)

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


def load_broker_json():
    """纯粹读取本地 JSON 账本"""
    ACCOUNT_FILE = "data/live_broker_account.json"
    if not os.path.exists(ACCOUNT_FILE):
        os.makedirs(os.path.dirname(ACCOUNT_FILE), exist_ok=True)
        template = {
            "available_cash": 500000.00,
            "positions": [
                {"symbol": "300308", "shares": 1000, "cost_price": 120.50, "highest_price": 150.00}
            ]
        }
        with open(ACCOUNT_FILE, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=4, ensure_ascii=False)
        return None, []

    with open(ACCOUNT_FILE, 'r', encoding='utf-8') as f:
        broker_data = json.load(f)

    available_cash = float(broker_data.get("available_cash", 0.0))
    positions_list = broker_data.get("positions", [])
    return available_cash, positions_list


def main():
    logger.info("=" * 80)
    logger.info(f" 🚀 启动量化交易实盘中心 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    logger.info("=" * 80)

    live_cfg = get_latest_live_params()
    provider = AkShareProvider()

    # ==========================================================
    # 🟢 模块 1：行情总线挂载与智能字段映射
    # ==========================================================
    price_col, open_col, high_col, low_col, vol_col, turn_col, name_col = [None] * 7
    try:
        spot_df = provider.get_market_snapshot()
        if not spot_df.empty:
            code_raw = '代码' if '代码' in spot_df.columns else ('code' if 'code' in spot_df.columns else 'symbol')
            spot_df['clean_code'] = spot_df[code_raw].astype(str).str.extract(r'(\d{6})')
            spot_df = spot_df.dropna(subset=['clean_code'])
            spot_df.set_index('clean_code', inplace=True)

            # 智能映射
            price_col = '最新价' if '最新价' in spot_df.columns else ('trade' if 'trade' in spot_df.columns else None)
            open_col = '今开' if '今开' in spot_df.columns else 'open'
            high_col = '最高' if '最高' in spot_df.columns else 'high'
            low_col = '最低' if '最低' in spot_df.columns else 'low'
            vol_col = '成交量' if '成交量' in spot_df.columns else 'volume'
            turn_col = '换手率' if '换手率' in spot_df.columns else 'turnoverratio'
            name_col = '名称' if '名称' in spot_df.columns else ('name' if 'name' in spot_df.columns else None)
    except Exception as e:
        logger.warning(f"获取全市场快照异常，将退回纯日线数据: {e}")
        spot_df = pd.DataFrame()

    def get_spot_val(sym, col_name, fallback=None):
        """安全读取快照单行字段的辅助函数"""
        if spot_df.empty or sym not in spot_df.index or not col_name: return fallback
        info = spot_df.loc[sym]
        if isinstance(info, pd.DataFrame): info = info.iloc[0]
        val = info.get(col_name)
        if pd.isna(val) or val == '-' or val == '': return fallback
        return val

    # 获取全市场统一名称字典
    def get_sym_name(sym):
        return str(get_spot_val(sym, name_col, sym))

    # ==========================================================
    # 🟢 模块 2：透明化审计账本 (合并雷达池与真实持仓)
    # ==========================================================
    radar_symbols, source_file = get_live_target_pool(top_n=5)

    json_result = load_broker_json()
    if json_result[0] is None:
        return logger.error("🚨 已生成券商同步账本模板，请填入真实的【可用现金】与【持仓】后重试！")

    available_cash, positions_list = json_result
    held_symbols = [str(pos.get('symbol', '')) for pos in positions_list if int(pos.get('shares', 0)) > 0]

    # 执行去重合并
    overlap = set(radar_symbols) & set(held_symbols)
    final_target_symbols = list(dict.fromkeys(held_symbols + radar_symbols))

    logger.info(f" 📡 [数据溯源] 成功加载行情快照源: {source_file}")
    logger.info("-" * 80)

    logger.info(f"🎯 【雷达热点池 (Top {len(radar_symbols)})】")
    for sym in radar_symbols:
        _price = get_spot_val(sym, price_col, "N/A")
        logger.info(f"   - {sym} ({get_sym_name(sym)}) | 现价: {_price}")

    logger.info(f"\n💼 【会计部真实持仓 ({len(held_symbols)} 只)】")
    for pos in positions_list:
        _sym = str(pos.get('symbol', ''))
        if int(pos.get('shares', 0)) > 0:
            logger.info(
                f"   - {_sym} ({get_sym_name(_sym)}) | 成本: {pos.get('cost_price')} | 持股: {pos.get('shares')}")

    logger.info(f"\n🔄 【审计合并去重结论】")
    logger.info(f"   - 发现重合标的: {list(overlap) if overlap else '无'}")
    logger.info(f"   - 最终确立实盘监控大名单: 共 {len(final_target_symbols)} 只。开始拉取底层 K 线...")
    logger.info("-" * 80)

    # 实例化大管家
    account = Portfolio(initial_cash=available_cash, symbols=final_target_symbols)
    for pos_data in positions_list:
        sym = str(pos_data.get('symbol', ''))
        shares = int(pos_data.get('shares', 0))
        cost = float(pos_data.get('cost_price', 0.0))
        if shares > 0 and cost > 0 and sym:
            pos_obj = Position(sym)
            pos_obj.shares = shares
            pos_obj.avg_price = cost
            account.positions[sym] = pos_obj

    # ==========================================================
    # 🟢 模块 3：盘前资产风控看板 (Pre-Trade NAV Dashboard)
    # ==========================================================
    total_cost = 0.0
    total_market_value = 0.0

    for sym, pos_obj in account.positions.items():
        current_price = get_spot_val(sym, price_col)
        if current_price:
            current_price = float(current_price)
            total_cost += pos_obj.cost
            total_market_value += pos_obj.shares * current_price
        else:
            total_cost += pos_obj.cost
            total_market_value += pos_obj.cost

    current_equity = account.total_cash + total_market_value
    floating_pnl = total_market_value - total_cost
    floating_pnl_pct = (floating_pnl / total_cost * 100) if total_cost > 0 else 0.0

    logger.info("【盘前资产风控评估 (Pre-Trade NAV Dashboard)】")
    logger.info(f"   - 可用现金 (Available Cash) : {account.total_cash:,.2f}")
    logger.info(f"   - 持仓成本 (Total Cost)     : {total_cost:,.2f}")
    logger.info(f"   - 持仓市值 (Market Value)   : {total_market_value:,.2f}")
    logger.info(f"   - 净 资 产 (Total Equity)   : {current_equity:,.2f}")
    logger.info(f"   - 账面浮盈 (Floating PnL)   : {floating_pnl:,.2f} ({floating_pnl_pct:.2f}%)")
    logger.info("-" * 80)

    # ==========================================================
    # 🟢 模块 4：获取历史数据及实盘切片注入 (附尾部检查)
    # ==========================================================
    data_dict = {}
    current_date_str = datetime.now().strftime("%Y-%m-%d")

    for sym in final_target_symbols:
        df = provider.get_data(sym)
        if df.empty or len(df) < live_cfg['ma_long']:
            continue

        sym_name = get_sym_name(sym)
        last_date = pd.to_datetime(df.index[-1]).strftime("%Y-%m-%d")

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
                    logger.info(f"⚡ [{sym} {sym_name}] 盘中脉搏注入成功！(跳动现价: {today_kline.iloc[0]['close']})")
                else:
                    logger.warning(f"[{sym} {sym_name}] 价格解析异常，跳过注入。")
            except Exception as e:
                logger.error(f"[{sym} {sym_name}] 实时切片注入报错: {e}")

        data_dict[sym] = df

        # 💡 强力校验点：打印每个标的最新 3 行数据让老板审阅！
        logger.debug(f"\n📊 [{sym} {sym_name}] 最新 3 行数据切片检查:\n{df.tail(3).to_string()}")

    if not data_dict:
        return logger.error("获取行情数据失败，程序终止。")

    # ==========================================================
    # 🟢 模块 5：实例化策略与指标计算
    # ==========================================================
    strategy = InstitutionalTrendStrategy(cfg=live_cfg, symbols=final_target_symbols)

    def live_get_current_row(sym):
        return strategy.indicators[sym].iloc[-1] if sym in strategy.indicators else None

    strategy.get_current_row = live_get_current_row

    try:
        indicators_dict = strategy.prepare(data_dict)
    except Exception as e:
        return logger.error(f"计算指标异常: {e}")

    df_pos = pd.DataFrame(positions_list) if positions_list else pd.DataFrame()
    if not df_pos.empty:
        for _, row in df_pos.iterrows():
            sym = str(row.get('symbol', ''))
            if sym in strategy.pos_state and int(row.get('shares', 0)) > 0:
                strategy.pos_state[sym]['units_held'] = 1
                strategy.pos_state[sym]['peak_price'] = float(row.get('highest_price', 0.0))

    # ==========================================================
    # 🟢 模块 6：策略指令生成与合规审批
    # ==========================================================
    buy_orders, sell_orders, hold_reports, rejected_orders = [], [], [], []
    sold_symbols_today = []  # 追踪今日清仓的股票，防止出现在监控池

    for symbol, df_analyzed in indicators_dict.items():
        sym_name = get_sym_name(symbol)
        today_bar = df_analyzed.iloc[-1]

        data_date = today_bar.name.strftime("%Y-%m-%d") if hasattr(today_bar, 'name') else str(
            today_bar.get('date', 'UNKNOWN'))
        if data_date != current_date_str:
            logger.warning(f"⚠️ 【注意时效】{symbol} 最新K线日期是 {data_date}，不是今天！")

        action, intent_shares = strategy.on_bar(today_bar, account, symbol)

        price = today_bar['close']
        cost = account.get_avg_price(symbol)
        held_shares = account.get_shares(symbol)

        if action in ["BUY", "SELL"]:
            reason = strategy.intended_signals[-1]['reason'] if strategy.intended_signals else "捕获买卖点"

            trade_result = account.execute_trade(
                symbol=symbol,
                action=action,
                shares=intent_shares,
                price=price,
                current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            if trade_result['success']:
                filled_shares = trade_result['filled_shares']
                fee = trade_result['fee']
                trade_value = trade_result['trade_value']

                if action == "SELL":
                    sold_symbols_today.append(symbol)
                    profit_pct = (price - cost) / cost if cost > 0 else 0
                    sell_orders.append(
                        f"🔴 【会计部批准卖出】 {symbol} ({sym_name}) | 当日收盘价: {price:.2f}\n"
                        f"   - 操作: 卖出 {filled_shares} 股 (当前余股: {held_shares - filled_shares})\n"
                        f"   - 财务核算: 回笼资金 {trade_value:,.2f} 元 (扣减税费 {fee:.2f} 元)\n"
                        f"   - 策略逻辑: {reason} (单笔盈亏: {profit_pct * 100:.2f}%)"
                    )
                else:
                    status = "首次建仓" if held_shares == 0 else "加仓追击"
                    buy_orders.append(
                        f"🟢 【策略建议并会计部批准买入】 {symbol} ({sym_name}) | 当日收盘价: {price:.2f}\n"
                        f"   - 操作: {status} {filled_shares} 股 \n"
                        f"   - 财务核算: 专项预算划拨 {trade_value:,.2f} 元 (预扣佣金 {fee:.2f} 元)\n"
                        f"   - 策略逻辑: {reason}"
                    )
            else:
                reject_reason = trade_result['message']
                rejected_orders.append(
                    f"⛔ 【风控部驳回申请】 {symbol} ({sym_name})\n"
                    f"   - 策略部意图: 申请 {action} {intent_shares} 股\n"
                    f"   - 驳回原因: {reject_reason} ！！！"
                )

        else:
            if held_shares > 0:
                profit_pct = (price - cost) / cost if cost > 0 else 0
                peak = strategy.pos_state[symbol]['peak_price']
                hold_reports.append(
                    f"🛡️ 【持仓审计通过】 {symbol} ({sym_name}) | 当前持仓: {held_shares} 股\n"
                    f"   - 现价: {price:.2f} | 成本: {cost:.2f} | 历史最高: {peak:.2f}\n"
                    f"   - 浮盈: {profit_pct * 100:.2f}% (当前策略未触发卖出信号，继续持有)"
                )

    # ==========================================================
    # 🟢 模块 7：标准化日志记录与排版美化 (Standardized Reporting)
    # ==========================================================
    logger.info("=" * 80)
    logger.info("【操作审批纪要 (Execution Summary)】")

    if sell_orders:
        logger.info(" [减仓/清仓指令]")
        for order in sell_orders: logger.info(order)
    else:
        logger.info(" [减仓/清仓指令] 无需操作。")

    if buy_orders:
        logger.info("\n [建仓/加仓指令]")
        for order in buy_orders: logger.info(order)
    else:
        logger.info("\n [建仓/加仓指令] 暂无符合安全边际之标的。")

    if rejected_orders:
        logger.warning("\n [风控拦截记录]")
        for order in rejected_orders: logger.warning(order)

    logger.info("\n【持仓状态确认 (Positions Audit)】")
    if hold_reports:
        for report in hold_reports: logger.info(report)
    else:
        logger.info("   - 当前未持有任何底层资产。")

    logger.info("=" * 80)

    logger.info("👀 【交易额最大监控池 (拒绝交易名单)】")
    watched_count = 0
    for symbol, df_analyzed in indicators_dict.items():
        # 💡 强力排查：只有账户真的空仓，并且【今天没有发生卖出动作】的股票，才列入监控！
        if account.get_shares(symbol) == 0 and symbol not in sold_symbols_today:
            today_bar = df_analyzed.iloc[-1]
            bias = today_bar.get('Bias', 999)
            is_bullish = today_bar.get('Strong_Trend', False)
            if not is_bullish:
                reason = "未形成核心多头排列"
            elif bias > live_cfg['bias_entry_limit']:
                reason = f"乖离率过高 ({bias:.2f})，严禁追高"
            else:
                reason = "未满足缩量回踩或放量金叉条件"
            logger.info(f"   - 🚫 放弃买入 {symbol} ({get_sym_name(symbol)}): {reason}")
            watched_count += 1

    if watched_count == 0:
        logger.info("   (监控池无可用信息)")

    logger.info("=" * 80)


if __name__ == "__main__":
    main()