import os
import glob
import json
import pandas as pd
from datetime import datetime

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
    logger.info(f"📡 正在扫描全市场成交额 Top {top_n}...")
    csv_files = glob.glob("data_provider/test_cache_data/*spot*.csv") + glob.glob(
        "data_provider/test_cache_data/*snapshot*.csv") + glob.glob("data/*snapshot*.csv")

    if not csv_files:
        logger.warning("未找到本地全景快照，使用兜底股票...")
        return ["300308", "601138"], {"300308": "中际旭创", "601138": "工业富联"}

    csv_path = csv_files[0]
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
    🏦 会计与审计部：合并雷达目标与真实持仓，全面接管资金！
    """
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
    print("\n" + "█" * 80)
    print(f" 🚀 启动量化交易实盘指挥中心 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print("█" * 80)

    # 1. 加载实验室寻优参数
    live_cfg = get_latest_live_params()

    # 2. 雷达先行：扫出全市场 Top 50 热点股票
    radar_symbols, symbol_names = get_live_target_pool(top_n=3)

    # 3. 会计部介入：拿着雷达池子，去和老板的账本合并，完成大管家初始化
    account, df_pos, final_target_symbols = sync_broker_account(radar_symbols)
    if account is None:
        return  # 等待老板填数据

    # 4. 实例化原汁原味的策略大脑
    provider = AkShareProvider()
    strategy = InstitutionalTrendStrategy(cfg=live_cfg, symbols=final_target_symbols)

    # 5. 准备数据并喂给大脑
    data_dict = {}
    for sym in final_target_symbols:
        df = provider.get_data(sym)
        if not df.empty and len(df) >= live_cfg['ma_long']:
            data_dict[sym] = df

    if not data_dict:
        return logger.error("数据源异常，未拉取到任何有效数据！")

    # 策略大脑统一计算指标！
    try:
        indicators_dict = strategy.prepare(data_dict)
    except Exception as e:
        return logger.error(f"大脑计算指标异常: {e}")

    # 💡 审计部动作：将会计账本里的“历史最高价”注入策略状态！
    if not df_pos.empty:
        for _, row in df_pos.iterrows():
            sym = str(row.get('symbol', ''))
            if sym in strategy.pos_state and int(row.get('shares', 0)) > 0:
                strategy.pos_state[sym]['units_held'] = 1
                strategy.pos_state[sym]['peak_price'] = float(row.get('highest_price', 0.0))

    buy_orders, sell_orders, hold_reports = [], [], []

    # 6. 生成实盘指令
    for symbol, df_analyzed in indicators_dict.items():
        name = symbol_names.get(symbol, symbol)
        today_bar = df_analyzed.iloc[-1]
        data_date = today_bar.name.strftime("%Y-%m-%d") if hasattr(today_bar, 'name') else str(
            today_bar.get('date', 'UNKNOWN'))

        current_date = datetime.now().strftime("%Y-%m-%d")
        if data_date != current_date:
            logger.warning(f"⚠️ 【注意时效】{symbol} 最新K线日期是 {data_date}，不是今天！请确认是否收盘或需清理缓存。")

        # 🟢 调用 trend.py 进行裁决
        action, shares = strategy.on_bar(today_bar, account, symbol)

        price = today_bar['close']
        cost = account.get_avg_price(symbol)
        held_shares = account.get_shares(symbol)

        if action == "SELL":
            profit_pct = (price - cost) / cost if cost > 0 else 0
            reason = strategy.intended_signals[-1]['reason'] if strategy.intended_signals else "未知防守原因"
            sell_orders.append(
                f"🔴 【清仓/减仓指令】 {symbol} ({name}) | 当日收盘价: {price:.2f}\n"
                f"   - 操作: 卖出 {shares} 股 (当前持仓: {held_shares} 股，成本: {cost:.2f})\n"
                f"   - 审计结论: {reason} (最终盈亏: {profit_pct * 100:.2f}%)"
            )
        elif action == "BUY":
            reason = strategy.intended_signals[-1]['reason'] if strategy.intended_signals else "捕获买点"
            status = "建仓" if held_shares == 0 else "加仓"
            buy_orders.append(
                f"🟢 【{status}指令】 {symbol} ({name}) | 当日收盘价: {price:.2f}\n"
                f"   - 操作: 买入 {shares} 股 (预计消耗资金: {shares * price:,.2f} 元)\n"
                f"   - 策略逻辑: {reason}"
            )
        else:
            if held_shares > 0:
                profit_pct = (price - cost) / cost if cost > 0 else 0
                peak = strategy.pos_state[symbol]['peak_price']
                hold_reports.append(
                    f"🛡️ 【持仓审计通过】 {symbol} ({name}) | 当前持仓: {held_shares} 股\n"
                    f"   - 现价: {price:.2f} | 成本: {cost:.2f} | 历史最高: {peak:.2f}\n"
                    f"   - 浮盈: {profit_pct * 100:.2f}% (大管家未下达卖出指令，继续安心持有)"
                )

    # 打印最终报告
    print("\n🚨 【清仓 / 防守指令】" + ("-" * 50))
    for o in sell_orders: print(o)
    if not sell_orders: print("   (无防守动作，阵地安全)")

    print("\n🎯 【建仓 / 加仓指令】" + ("-" * 50))
    for o in buy_orders: print(o)
    if not buy_orders:
        print("   (无攻击动作，耐心等待)")
    elif len(buy_orders) > 5:
        print("   ⚠️ 提示: 买入信号超载，请老板择优挑选执行！")

    print("\n📊 【持仓审计流水】" + ("-" * 50))
    for o in hold_reports: print(o)
    if not hold_reports: print("   (当前账户为空仓状态)")

    print("\n" + "█" * 80 + "\n")


if __name__ == "__main__":
    main()