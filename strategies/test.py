import pandas as pd
import os
from datetime import datetime
from strategies.sma520 import SMA520Strategy
from core.account import Portfolio
from utils.logger import global_logger as logger

# 假设 akshare_pd.py 放在项目根目录的 data 文件夹下
from data_provider.akshare_pd import AkShareProvider



def test_multi_stock_real_data():
    logger.info("🚀 开始测试 SMA520 均线策略 (多股票并发回测)")
    print("=" * 70)

    # 1. 清理旧账本
    test_ledger = "data/test_multi_ledger.csv"
    test_positions = "data/test_multi_positions.csv"
    for path in [test_ledger, test_positions]:
        if os.path.exists(path):
            os.remove(path)

    # ==========================================
    # 2. 从 AkShare 拉取【CPO双雄】真实日 K 线
    # ==========================================
    symbols = ["300502", "300308"]  # 新易盛, 中际旭创
    provider = AkShareProvider()
    real_data_dict = {}

    for sym in symbols:
        logger.info(f"⏳ 正在拉取 {sym} 最近 500 个交易日的真实数据...")
        df = provider.get_data(sym)
        if not df.empty:
            real_data_dict[sym] = df
            logger.info(f"   ✅ {sym} 数据就绪 ({len(df)} 天)")
        else:
            logger.error(f"   ❌ {sym} 数据拉取失败！")

    if not real_data_dict:
        logger.error("❌ 所有股票数据均拉取失败，退出测试。")
        return

    # ==========================================
    # 3. 构建统一的“时间轴日历” (Engine 的核心思路)
    # ==========================================
    # 把所有股票的交易日期合并去重并排序，防止某只股票某天停牌报错
    all_dates = set()
    for df in real_data_dict.values():
        all_dates.update(df.index)
    sorted_dates = sorted(list(all_dates))

    logger.info(f"📅 统一时间轴构建完毕，总计 {len(sorted_dates)} 个交易日。")
    print("-" * 70)

    # ==========================================
    # 4. 初始化会计管家与策略大脑
    # ==========================================
    account = Portfolio(initial_cash=100000.0, ledger_path=test_ledger)
    strategy = SMA520Strategy(symbols=list(real_data_dict.keys()))

    # 策略预计算 (Pandas 向量化极速处理)
    logger.info("⏳ 策略大脑开始全量计算多股票的均线指标...")
    prepared_data = strategy.prepare(real_data_dict)

    # ==========================================
    # 5. 模拟时间机器，多股并发回测
    # ==========================================
    logger.info("⏳ 开启时间机器，多线程推进...")
    trade_count = 0

    # 外层循环：历史时间轴一天一天往前走
    for current_date in sorted_dates:
        date_str = current_date.strftime("%Y-%m-%d")

        # 内层循环：每一天，分别检查所有的股票
        for symbol, df in real_data_dict.items():
            # 如果这只股票今天没停牌，有 K 线数据
            if current_date in df.index:
                bar = df.loc[current_date]
                price = bar['close']

                # 1. 策略大脑思考
                action, shares = strategy.on_bar(bar, account, symbol)

                # 2. 如果发出了指令，叫会计去办事
                if action:
                    logger.info(f"[{date_str}] 💡 策略指示 [{symbol}]: {action} {shares} 股 @ {price:.2f}")

                    res = account.execute_trade(
                        symbol=symbol,
                        action=action,
                        shares=shares,
                        price=price,
                        current_time=date_str
                    )

                    if res['success']:
                        logger.info(f"   ✅ [会计回复] {symbol} 订单执行成功！剩余现金: {account.cash:.2f}")
                        trade_count += 1
                    else:
                        logger.error(f"   ❌ [会计回复] {symbol} 订单被拦截: {res.get('message')}")

    print("=" * 70)
    logger.info(f"🎉 并发回测结束！共触发成功交易 {trade_count} 笔。")
    logger.info(f"📊 最终账户总资产 (账面纯现金+持仓成本): {account.get_book_value():.2f} 元")
    logger.info(f"📁 流水账本: {test_ledger}")
    logger.info(f"📁 持仓底稿: {test_positions}")


if __name__ == "__main__":
    test_multi_stock_real_data()