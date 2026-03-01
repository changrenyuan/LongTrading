import os
import logging
import itertools
import pandas as pd

from data_provider.akshare_pd import AkShareProvider
from core.account import Portfolio
from core.engineBacktest import BacktestEngine
from strategies.trend import InstitutionalTrendStrategy
from utils.metrics import MetricsCalculator
from utils.logger import global_logger as logger
from utils.plotter import Plotter


def run_single_stock_deep_grid_search(data_df, symbol, initial_capital):
    """
    深度网格寻优：针对单只十倍牛股，展开大规模的参数交叉测试
    """
    base_cfg = {
        'stop_loss_pct': 0.10, 'trailing_stop_pct': 0.20,
        'profit_tier2': 1.00, 'trailing_tier2': 0.10,
        'ma_long': 20,
        'trend_strength_buffer': 1.0, 'bias_entry_limit': 1.20,
        'pullback_support_lower': 0.90, 'pullback_bias_limit': 1.25,
        'trend_broken_lower': 0.90, 'trend_broken_vol': 1.5,
        'add_pos_min_profit': 0.02, 'breakout_window': 10, 'breakout_vol_limit': 1.1,
    }

    # 🔥 超级参数网格：你可以任意增减这里面的列表，机器会自动做笛卡尔积组合
    # 目前组合数：2(ma_short) * 3(ma_mid) * 2(tier1) * 2(support) * 2(unit_size) = 48 组
    param_grid = {
        'ma_short': [5, 10],  # 冲锋线：5日极速 vs 10日稳健
        'ma_mid': [10, 15, 20],  # 生命线：10日(疯牛) vs 15日(波段) vs 20日(长线)
        'profit_tier1': [0.40, 0.60],  # 一档止盈门槛：赚 40% 防守 vs 赚 60% 才防守
        'pullback_support_upper': [1.05, 1.15],  # 回踩容忍度：严格靠近均线 vs 宽容高位加油
        'unit_size': [0.33, 0.50],  # 仓位管理：分 3 批 vs 分 2 批
    }

    # 生成笛卡尔积
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    grid_combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]

    logger.info(f"📐 构建参数网格完成，共需测试 {len(grid_combinations)} 组策略变体！")

    combination_records = []

    best_sharpe = -999.0
    best_params = None
    best_metrics = None
    best_df_results = None

    # 关闭回测期间的日常打印日志，防止 48 组流水刷爆终端
    original_level = logger.level
    logger.setLevel(logging.ERROR)

    data_dict = {symbol: data_df}

    for idx, params in enumerate(grid_combinations):
        current_cfg = {**base_cfg, **params}
        current_cfg['max_units'] = int(1.0 // current_cfg['unit_size'])

        # 使用固定的临时账本即可，因为我们是串行跑的
        ledger_path = f"data/temp_deep_grid_ledger.csv"
        if os.path.exists(ledger_path): os.remove(ledger_path)
        if os.path.exists(ledger_path.replace("ledger", "positions")): os.remove(
            ledger_path.replace("ledger", "positions"))

        account = Portfolio(initial_cash=initial_capital, symbols=[symbol], ledger_path=ledger_path)
        strategy = InstitutionalTrendStrategy(cfg=current_cfg, symbols=[symbol])
        engine = BacktestEngine(data_dict=data_dict, strategy=strategy, account=account)

        df_results = engine.run()

        if not df_results.empty:
            df_results['pnl'] = df_results['equity'] - initial_capital
            metrics = MetricsCalculator.calculate(df_results, initial_capital, account.trade_history)
            sharpe = float(metrics.get('夏普比率', 0))

            # 记录成绩
            combination_records.append({
                'params': params,
                'sharpe': sharpe,
                'return': metrics.get('累计收益率'),
                'win_rate': metrics.get('胜率'),
                'drawdown': metrics.get('最大回撤'),
                'trades': metrics.get('平仓次数')
            })

            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = current_cfg
                best_metrics = metrics
                best_df_results = df_results

    # 恢复日志打印级别
    logger.setLevel(original_level)

    # 对记录进行排序 (按夏普比率降序)
    combination_records.sort(key=lambda x: x['sharpe'], reverse=True)

    # 打印排位榜单
    print("\n" + "★" * 90)
    print(f"📊 【{symbol}】深度参数网格寻优排行榜 (共 {len(grid_combinations)} 组参数)")
    print("★" * 90)
    print(
        f"{'排名':<4} | {'夏普':<5} | {'收益率':<8} | {'胜率':<7} | {'最大回撤':<8} | {'交易数':<4} | {'核心参数组合'}")
    print("-" * 90)

    for idx, rec in enumerate(combination_records):
        p = rec['params']
        # 格式化参数字符串，方便查看
        p_str = f"短线={p['ma_short']}, 生命线={p['ma_mid']}, 一档={p['profit_tier1']}, 回踩={p['pullback_support_upper']}, 仓位={p['unit_size']}"
        print(
            f"Top {idx + 1:<2} | {rec['sharpe']:<5.2f} | {rec['return']:>7} | {rec['win_rate']:>6} | {rec['drawdown']:>7} | {rec['trades']:>5} | {p_str}")

    print("★" * 90 + "\n")

    return best_params, best_metrics, best_df_results


def main():
    initial_capital = 100000.0

    # 🎯 目标：专门解剖十倍牛股中际旭创
    target_symbol = "300308"
    target_name = "中际旭创"

    logger.info("==========================================")
    logger.info(f"🔬 启动单资产深度网格寻优: {target_name} ({target_symbol})")
    logger.info("==========================================")

    provider = AkShareProvider()
    data_df = provider.get_data(target_symbol)

    if data_df.empty:
        logger.error(f"无法获取 {target_name} 的历史数据！")
        return

    best_cfg, best_metrics, best_df_results = run_single_stock_deep_grid_search(data_df, target_symbol, initial_capital)

    if best_cfg and best_metrics:
        logger.info(f"🏆 寻优结束！最高夏普比率: {best_metrics.get('夏普比率')}")
        logger.info(f"💡 最强参数组合已锁定，系统将自动生成该最优参数的 2x2 分析图。")

        # 为最好的那一组参数画图
        Plotter.plot_portfolio(
            df_res=best_df_results,
            symbols=[target_symbol],
            symbol_names={target_symbol: target_name},
            strategy_name=f"DeepOpt_{target_name}_Best",
            save_dir="data/charts"
        )
    else:
        logger.warning("回测期间无有效交易。")


if __name__ == "__main__":
    main()