import os
import glob
import json
import pandas as pd
from datetime import datetime
import re
# ==========================================
# 🔴 核心模块导入：全面接管会计与策略模块！
# ==========================================
from data_provider.akshare_pd import AkShareProvider
from strategies.trend import InstitutionalTrendStrategy
from core.account import Portfolio, Position  # 💡 确保引入 Position 类
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


def get_live_target_pool(top_n=3):
    """提取实盘关注的雷达股票池"""
    logger.info(f" 正在读取全市场成交额 Top {top_n}...")
    csv_files = glob.glob("data_provider/test_cache_data/*spot*.csv") + glob.glob(
        "data_provider/test_cache_data/*snapshot*.csv") + glob.glob("data/*snapshot*.csv")

    if not csv_files:
        logger.warning("未找到本地全景快照，使用兜底股票...")
        return ["300308", "601138"], {"300308": "中际旭创", "601138": "工业富联"}

    # 1. 确定要读取的文件
    # 💡 优化：按照文件的修改时间排序，确保永远读取“最新”生成的那一份快照
    csv_path = max(csv_files, key=os.path.getmtime)
    filename = os.path.basename(csv_path)
    # 2. 动态提取日期：优先从文件名提取 (如 20260303)，提取不到则用文件物理修改时间
    date_match = re.search(r'(\d{8})', filename)
    if date_match:
        raw_date = date_match.group(1)
        display_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
    else:
        mtime = os.path.getmtime(csv_path)
        display_date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')

    # 3. 严谨播报：打印具体日期和数据源文件
    logger.info(f"正在读取【{display_date}】全市场成交额 Top {top_n} (数据源: {filename})...")
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

        symbols = spot_df['clean_code'].tolist()
        symbol_names = dict(zip(spot_df['clean_code'], spot_df[name_col])) if name_col in spot_df.columns else {s: s for
                                                                                                                s in
                                                                                                                symbols}
        return symbols, symbol_names
    except Exception as e:
        logger.error(f"提取股票失败: {e}")
        return [], {}


def sync_broker_account(radar_symbols):
    """
    会计与审计部：合并近期热点目标与真实持仓，全面接管资金！
    """
    ACCOUNT_FILE = "../data/live_broker_account.json"

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
        logger.info(f"🚨 已生成券商同步账本 {ACCOUNT_FILE}。请填入真实的【可用现金】与【持仓】后重试！")
        return None, None, None

    with open(ACCOUNT_FILE, 'r', encoding='utf-8') as f:
        broker_data = json.load(f)

    available_cash = float(broker_data.get("available_cash", 0.0))
    positions_list = broker_data.get("positions", [])

    # 提取已持有的股票代码
    held_symbols = [str(pos.get('symbol', '')) for pos in positions_list if int(pos.get('shares', 0)) > 0]

    # 💡 核心修复：把雷达扫出的 Top50 股票和老板已经持有的股票合并，作为大管家的总管辖范围！
    final_target_symbols = list(dict.fromkeys(held_symbols + radar_symbols))

    # 初始化大管家：分配预算！
    account = Portfolio(initial_cash=available_cash, symbols=final_target_symbols)

    # 强制覆盖为真实可用余额
    account.cash = available_cash

    # 将 JSON 里的持仓数据，转化为大管家认可的 Position 对象
    for pos_data in positions_list:
        sym = str(pos_data.get('symbol', ''))
        shares = int(pos_data.get('shares', 0))
        cost = float(pos_data.get('cost_price', 0.0))

        if shares > 0 and cost > 0 and sym:
            pos_obj = Position(sym)
            pos_obj.shares = shares
            pos_obj.avg_price = cost
            account.positions[sym] = pos_obj  # 严谨注入对象！

    logger.info(f"🏦 会计部接管完毕: 真实可用现金 【{available_cash:,.2f} 元】，真实持仓 【{len(held_symbols)} 只】。")

    df_pos = pd.DataFrame(positions_list) if positions_list else pd.DataFrame()
    return account, df_pos, final_target_symbols


def main():
    logger.info("=" * 80)
    logger.info(f" 启动量化交易实盘中心 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    logger.info("=" * 80)
    # 1. 加载实验室寻优参数
    live_cfg = get_latest_live_params()

    # 2. 雷达先行：扫出全市场 Top 50 热点股票
    topvolume_symbols, symbol_names = get_live_target_pool(top_n=5)

    # 3. 会计部初始化账本
    account, df_pos, final_target_symbols = sync_broker_account(topvolume_symbols)
    if account is None:
        return  #
    # 3. 会计部初始化账本
    account, df_pos, final_target_symbols = sync_broker_account(topvolume_symbols)
    if account is None:
        return  # 首次运行等待老板填写真实数据

    # ==========================================================
    # 5. 获取数据及指标计算 (包含实盘切片注入)
    # ==========================================================
    data_dict = {}
    provider = AkShareProvider()

    # 尝试拉取全市场实时行情快照作为 Cache
    try:
        spot_df = provider.get_market_snapshot()
        if not spot_df.empty:
            # 确保代码列是字符串类型，并设为索引方便查询
            code_col = '代码' if '代码' in spot_df.columns else 'symbol'
            spot_df[code_col] = spot_df[code_col].astype(str)
            spot_df.set_index(code_col, inplace=True)
    except Exception as e:
        logger.warning(f"获取全市场快照异常，将退回纯日线数据: {e}")
        spot_df = pd.DataFrame()

    current_date_str = datetime.now().strftime("%Y-%m-%d")

    # 遍历目标股票池，准备历史数据与今日切片
    for sym in final_target_symbols:
        df = provider.get_data(sym)
        if df.empty or len(df) < live_cfg['ma_long']:
            continue

        # 💡 修复 1：date 已经是时间索引 (DatetimeIndex)，必须通过 df.index 获取最后一天日期
        last_date = pd.to_datetime(df.index[-1]).strftime("%Y-%m-%d")

        # 实时数据切片注入 (向历史日线末尾拼接今日跳动 K 线)
        if last_date != current_date_str and not spot_df.empty and sym in spot_df.index:
            try:
                live_info = spot_df.loc[sym]

                # 💡 修复 2：构造标准化的 DataFrame 单行切片，并严格保持 datetime 索引结构
                today_kline = pd.DataFrame([{
                    'open': float(live_info.get('今开', df.iloc[-1]['close'])),
                    'high': float(live_info.get('最高', df.iloc[-1]['close'])),
                    'low': float(live_info.get('最低', df.iloc[-1]['close'])),
                    'close': float(live_info.get('最新价', df.iloc[-1]['close'])),
                    'volume': float(live_info.get('成交量', 0)),
                    'turnover': float(live_info.get('换手率', 0))  # 确保列名与历史日线一致
                }], index=[pd.to_datetime(current_date_str)])
                today_kline.index.name = 'date'

                if float(live_info.get('最新价', 0)) > 0:
                    # 去除 ignore_index=True，实现时间序列的完美无缝对接
                    df = pd.concat([df, today_kline])
            except Exception as e:
                logger.debug(f"[{sym}] 盘中实时切片注入失败，将退回日线状态 ({e})")

        data_dict[sym] = df

    if not data_dict:
        return logger.error("获取行情数据失败，程序终止。")

    # ==========================================================
    # 🟢 模块 1：计算宏观资产看板 (Executive Dashboard)
    # ==========================================================
    total_cost = 0.0
    total_market_value = 0.0

    # 💡 架构解耦与三重降级：优先查阅【实时快照】，退而查阅【日线】，最后【成本】保底
    for sym, pos_obj in account.positions.items():
        current_price = None

        # 🛡️ 第一优先级：使用内存中刚刚拉取的实时快照 (spot_df)
        if not spot_df.empty and sym in spot_df.index:
            try:
                live_price = float(spot_df.loc[sym].get('最新价', 0.0))
                if live_price > 0:
                    current_price = live_price
            except Exception:
                pass

        # 🛡️ 第二优先级：如果快照里没拉到，退回使用本地拼接后数据 (data_dict) 的最新收盘价
        if current_price is None and sym in data_dict:
            current_price = data_dict[sym].iloc[-1]['close']
            logger.debug(f"[{sym}] 实时快照缺失，采用日线最新收盘价: {current_price}")

        # 🎯 最终核算市值
        if current_price and current_price > 0:
            total_cost += pos_obj.cost
            total_market_value += pos_obj.shares * current_price
        else:
            # 🛡️ 第三优先级：极端异常兜底，假装没涨没跌，避免净值计算暴雷
            logger.warning(f"无法获取 [{sym}] 的任何市场价格，将以历史买入成本计入市值。")
            total_cost += pos_obj.cost
            total_market_value += pos_obj.cost

    current_equity = account.total_cash + total_market_value
    floating_pnl = total_market_value - total_cost
    floating_pnl_pct = (floating_pnl / total_cost * 100) if total_cost > 0 else 0.0

    logger.info("-" * 80)
    logger.info("【资产风控评估 (NAV Dashboard)】")
    logger.info(f"   - 可用现金 (Available Cash) : {account.total_cash:,.2f}")
    logger.info(f"   - 持仓成本 (Total Cost)     : {total_cost:,.2f}")
    logger.info(f"   - 持仓市值 (Market Value)   : {total_market_value:,.2f}")
    logger.info(f"   - 净 资 产 (Total Equity)   : {current_equity:,.2f}")
    logger.info(f"   - 账面浮盈 (Floating PnL)   : {floating_pnl:,.2f} ({floating_pnl_pct:.2f}%)")
    logger.info("-" * 80)

    # 4. 实例化策略

    strategy = InstitutionalTrendStrategy(cfg=live_cfg, symbols=final_target_symbols)

    # 抹平历史回测时间差，强制获取当日最新状态
    def live_get_current_row(sym):
        return strategy.indicators[sym].iloc[-1] if sym in strategy.indicators else None

    strategy.get_current_row = live_get_current_row


    # 策略大脑统一计算指标！
    try:
        indicators_dict = strategy.prepare(data_dict)
    except Exception as e:
        return logger.error(f"计算指标异常: {e}")

    # 💡 审计部动作：将会计账本里的“历史最高价”注入策略状态！
    if not df_pos.empty:
        for _, row in df_pos.iterrows():
            sym = str(row.get('symbol', ''))
            if sym in strategy.pos_state and int(row.get('shares', 0)) > 0:
                strategy.pos_state[sym]['units_held'] = 1
                strategy.pos_state[sym]['peak_price'] = float(row.get('highest_price', 0.0))


    # ==========================================================
    # 🟢 模块 2：策略指令生成与合规审批
    # ==========================================================


    buy_orders, sell_orders, hold_reports = [], [], []
    rejected_orders = []  # 💡 新增：被会计部驳回的废单记录
    # 6. 生成实盘指令 策略部提单 -> 会计部审批 -> 发通知
    for symbol, df_analyzed in indicators_dict.items():
        name = symbol_names.get(symbol, symbol)
        today_bar = df_analyzed.iloc[-1]
        data_date = today_bar.name.strftime("%Y-%m-%d") if hasattr(today_bar, 'name') else str(
            today_bar.get('date', 'UNKNOWN'))

        current_date = datetime.now().strftime("%Y-%m-%d")
        if data_date != current_date:
            logger.warning(f"⚠️ 【注意时效】{symbol} 最新K线日期是 {data_date}，不是今天！请确认是否收盘或需清理缓存。")

        # 🟢 第一步：军师 (策略) 进行判断
        action, intent_shares = strategy.on_bar(today_bar, account, symbol)

        price = today_bar['close']
        cost = account.get_avg_price(symbol)
        held_shares = account.get_shares(symbol)
        # 🟡 第二步：会计部 (大管家) 严格审批

        if action in ["BUY", "SELL"]:
            reason = strategy.intended_signals[-1]['reason'] if strategy.intended_signals else "捕获买卖点"

            # 💡 核心修复：正式向会计部提交交易申请！接受风控洗礼！
            trade_result = account.execute_trade(
                symbol=symbol,
                action=action,
                shares=intent_shares,
                price=price,
                current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            # 🟢 第三步：出具审批结论
            if trade_result['success']:
                # 审批通过！会计部已冻结额度/计入流水
                filled_shares = trade_result['filled_shares']
                fee = trade_result['fee']
                trade_value = trade_result['trade_value']

                if action == "SELL":
                    profit_pct = (price - cost) / cost if cost > 0 else 0
                    sell_orders.append(
                        f"🔴 【会计部批准卖出】 {symbol} ({name}) | 当日收盘价: {price:.2f}\n"
                        f"   - 操作: 卖出 {filled_shares} 股 (当前余股: {held_shares - filled_shares})\n"
                        f"   - 财务核算: 回笼资金 {trade_value:,.2f} 元 (扣减税费 {fee:.2f} 元)\n"
                        f"   - 策略逻辑: {reason} (单笔盈亏: {profit_pct * 100:.2f}%)"
                    )
                else:
                    status = "首次建仓" if held_shares == 0 else "加仓追击"
                    buy_orders.append(
                        f"🟢 【策略建议并会计部批准买入】 {symbol} ({name}) | 当日收盘价: {price:.2f}\n"
                        f"   - 操作: {status} {filled_shares} 股 \n"
                        f"   - 财务核算: 专项预算划拨 {trade_value:,.2f} 元 (预扣佣金 {fee:.2f} 元)\n"
                        f"   - 策略逻辑: {reason}"
                    )
            else:
                # ❌ 审批驳回！触发会计部风控拦截 (如：单票占比超 40%、子预算不足等)
                reject_reason = trade_result['message']
                rejected_orders.append(
                    f"⛔ 【风控部驳回申请】 {symbol} ({name})\n"
                    f"   - 策略部意图: 申请 {action} {intent_shares} 股\n"
                    f"   - 驳回原因: {reject_reason} ！！！"
                )

        else:
            if held_shares > 0:
                profit_pct = (price - cost) / cost if cost > 0 else 0
                peak = strategy.pos_state[symbol]['peak_price']
                hold_reports.append(
                    f"🛡️ 【持仓审计通过】 {symbol} ({name}) | 当前持仓: {held_shares} 股\n"
                    f"   - 现价: {price:.2f} | 成本: {cost:.2f} | 历史最高: {peak:.2f}\n"
                    f"   - 浮盈: {profit_pct * 100:.2f}% (当前策略未触发卖出信号，继续持有)"
                )
            else:
                # 💡 终极透明度：为什么空仓的股票没买？
                bias = today_bar.get('Bias', 999)
                is_bullish = today_bar.get('Strong_Trend', False)
                reason_str = ""
                if not is_bullish:
                    reason_str = "未形成核心多头排列"
                elif bias > live_cfg['bias_entry_limit']:
                    reason_str = f"乖离率过高 ({bias:.3f})，严防追高"
                else:
                    reason_str = "未满足金叉或放量突破等微观买点"

                # 你可以把这段打印加到 buy_orders 里（或者新建一个 watchlist 列表打印在最后）
                # 这里为了不干扰核心战报，我们用 logger 在后台静默记录，或者你可以根据喜好打印出来
                logger.debug(f"👀 【观望】 {symbol} ({name}) | 现价: {price:.2f} | 拒绝开仓原因: {reason_str}")

    # 🟢 模块 3：标准化日志记录 (Standardized Reporting)
    # ==========================================================
    logger.info("【操作审批纪要 (Execution Summary)】")

    if sell_orders:
        logger.info(" [减仓/清仓指令]")
        for order in sell_orders: logger.info(f"   - {order}")
    else:
        logger.info(" [减仓/清仓指令] 无需操作。")

    if buy_orders:
        logger.info(" [建仓/加仓指令]")
        for order in buy_orders: logger.info(f"   - {order}")
    else:
        logger.info(" [建仓/加仓指令] 暂无符合安全边际之标的。")

    if rejected_orders:
        logger.warning(" [风控拦截记录]")
        for order in rejected_orders: logger.warning(f"   - {order}")

    logger.info("【持仓状态确认 (Positions Audit)】")
    if hold_reports:
        for report in hold_reports: logger.info(f"   - {report}")
    else:
        logger.info("   - 当前未持有任何底层资产。")

    logger.info("=" * 80)

    # 💡 加上这一段，告诉老板雷达剔除了哪些垃圾！
    logger.info("\n👀 【交易额最大监控池 (拒绝交易名单)】" + ("-" * 50))
    watched_count = 0
    for symbol, df_analyzed in indicators_dict.items():
        if account.get_shares(symbol) == 0:
            today_bar = df_analyzed.iloc[-1]
            bias = today_bar.get('Bias', 999)
            is_bullish = today_bar.get('Strong_Trend', False)
            if not is_bullish:
                reason = "未形成核心多头排列"
            elif bias > live_cfg['bias_entry_limit']:
                reason = f"乖离率过高 ({bias:.2f})，严禁追高"
            else:
                reason = "未满足缩量回踩或放量金叉条件"
            logger.info(f"   - 🚫 放弃买入 {symbol} ({symbol_names.get(symbol, symbol)}): {reason}")
            watched_count += 1
    if watched_count == 0: print("   (交易额最大的股票池中的股票均已发起攻击，无遗漏)")



if __name__ == "__main__":
    main()