import pandas as pd
import os
from datetime import datetime
from strategies.sma520 import SMA520Strategy
from core.account import Portfolio
from utils.logger import global_logger as logger
from utils.plotter import Plotter  # 💡 引入绘图器

from data_provider.akshare_pd import AkShareProvider



def test_multi_stock_real_data():
    logger.info("🚀 开始测试 SMA520 均线策略 (带有完整数据流与可视化)")
    print("=" * 70)

    test_ledger = "data/test_multi_ledger.csv"
    test_positions = "data/test_multi_positions.csv"
    for path in [test_ledger, test_positions]:
        if os.path.exists(path): os.remove(path)

    symbols = ["300502", "300308"]
    provider = AkShareProvider()
    real_data_dict = {}

    for sym in symbols:
        df = provider.get_data(sym)
        if not df.empty:
            real_data_dict[sym] = df

    if not real_data_dict: return

    all_dates = set()
    for df in real_data_dict.values():
        all_dates.update(df.index)
    sorted_dates = sorted(list(all_dates))

    account = Portfolio(initial_cash=100000.0, ledger_path=test_ledger)
    strategy = SMA520Strategy(symbols=list(real_data_dict.keys()))
    prepared_data = strategy.prepare(real_data_dict)

    # 💡 核心升级：用于收集每一天快照的列表
    daily_history = []

    logger.info("⏳ 开启时间机器，多线程推进...")

    for current_date in sorted_dates:
        date_str = current_date.strftime("%Y-%m-%d")

        # 初始化当天的快照字典
        daily_record = {'date': current_date}
        total_market_value = 0.0  # 当日所有股票的持仓总市值

        for symbol, df in real_data_dict.items():
            if current_date in df.index:
                bar = df.loc[current_date]
                price = bar['close']

                # 记录当天的股价
                daily_record[f"{symbol}_price"] = price

                # 策略思考
                action, shares = strategy.on_bar(bar, account, symbol)

                # 记录交易信号 (如果有)
                if action == "BUY":
                    res = account.execute_trade(symbol, action, shares, price, current_time=date_str)
                    if res['success']: daily_record[f"{symbol}_buy_signal"] = price

                elif action == "SELL":
                    res = account.execute_trade(symbol, action, shares, price, current_time=date_str)
                    if res['success']: daily_record[f"{symbol}_sell_signal"] = price

                # 💡 Engine 负责计算当天的市价浮动市值 (Mark-to-Market)
                # 这也是为什么不需要 Account 来算最新价的原因！
                held_shares = account.get_shares(symbol)
                stock_market_value =  held_shares * price
                total_market_value += held_shares * price
                # 💡 新增：收集给 2x2 图表用的深度财务数据
                daily_record[f"{symbol}_shares"] = held_shares
                daily_record[f"{symbol}_avg_price"] = account.get_avg_price(symbol)
                daily_record[f"{symbol}_cost"] = account.get_position_cost(symbol)
                daily_record[f"{symbol}_market_value"] = stock_market_value

        # 每天收盘后，Engine 结算账户今日的“总动态权益”
        daily_record['cash'] = account.cash
        daily_record['equity'] = account.cash + total_market_value

        # 将当天的快照存入历史
        daily_history.append(daily_record)

    print("=" * 70)
    logger.info("🎉 回测结束！正在生成 Pandas DataFrame 与可视化图表...")

    # 将列表转化为 DataFrame，交由画图器处理
    df_results = pd.DataFrame(daily_history).set_index('date')

    # 💡 调用可视化模块
    Plotter.plot_portfolio(df_results, symbols=symbols, symbol_names={"300502": "新易盛", "300308": "中际旭创"}, strategy_name="SMA520 双均线", save_dir="data/charts")

    logger.info(f"📊 最终账户动态总资产: {df_results['equity'].iloc[-1]:.2f} 元")
    logger.info(f"📁 图表已保存在 data/charts 目录下，快去查看吧！")


if __name__ == "__main__":
    test_multi_stock_real_data()