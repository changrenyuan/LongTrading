import os
import logging
import pandas as pd
import optuna  # 💡 引入 AI 调参大脑

from data_provider.akshare_pd import AkShareProvider
from core.account import Portfolio
from core.engineBacktest import BacktestEngine
from strategies.trend import InstitutionalTrendStrategy
from utils.metrics import MetricsCalculator
from utils.logger import global_logger as logger
from utils.plotter import Plotter

# 压制 optuna 刷屏日志，只看结果
optuna.logging.set_verbosity(optuna.logging.WARNING)


def run_ai_optimization(data_df, symbol, initial_capital, n_trials=100):
    """
    🧠 AI 贝叶斯优化器：基于 Optuna 的智能调参
    """
    logger.info(f"🧠 唤醒 AI 调参大脑，开始对 {symbol} 进行 {n_trials} 次智能进化推演...")

    # 关闭回测期间的流水日志
    original_level = logger.level
    logger.setLevel(logging.ERROR)
    data_dict = {symbol: data_df}

    # 用于记录最优过程的附加信息
    best_metrics = None
    best_df_results = None

    def objective(trial):
        """
        AI 的“考卷”：AI 会不断改变这里的参数，目标是让 return 出来的夏普比率最大化
        """
        nonlocal best_metrics, best_df_results

        # 1. 让 AI 在连续的空间里自由发挥 (不再是干瘪的列表，而是范围区间！)
        ma_short = trial.suggest_int('ma_short', 3, 10)
        ma_mid = trial.suggest_int('ma_mid', 10, 30)

        # 💡 AI 逻辑防呆：短线不能大于中线，否则直接判零分(Prune)
        if ma_short >= ma_mid:
            raise optuna.TrialPruned()

        # 核心买卖微操参数，让 AI 寻找极值
        stop_loss_pct = trial.suggest_float('stop_loss_pct', 0.05, 0.15, step=0.01)
        trailing_stop_pct = trial.suggest_float('trailing_stop_pct', 0.15, 0.30, step=0.01)
        profit_tier1 = trial.suggest_float('profit_tier1', 0.30, 0.80, step=0.05)

        bias_entry_limit = trial.suggest_float('bias_entry_limit', 1.05, 1.25, step=0.02)
        pullback_support_upper = trial.suggest_float('pullback_support_upper', 1.02, 1.15, step=0.01)
        add_pos_min_profit = trial.suggest_float('add_pos_min_profit', 0.0, 0.05, step=0.01)

        unit_size = trial.suggest_categorical('unit_size', [0.25, 0.33, 0.50])

        current_cfg = {
            # 固定底座参数
            'profit_tier2': 1.20, 'trailing_tier2': 0.10,
            'trailing_tier1': 0.15, 'ma_long': 60,
            'pullback_support_lower': 0.90, 'pullback_bias_limit': 1.25,
            'trend_broken_lower': 0.90, 'trend_broken_vol': 1.5,
            'breakout_window': 10, 'breakout_vol_limit': 1.1,
            'trend_strength_buffer': 1.0,

            # AI 填写的参数
            'ma_short': ma_short,
            'ma_mid': ma_mid,
            'stop_loss_pct': stop_loss_pct,
            'trailing_stop_pct': trailing_stop_pct,
            'profit_tier1': profit_tier1,
            'bias_entry_limit': bias_entry_limit,
            'pullback_support_upper': pullback_support_upper,
            'add_pos_min_profit': add_pos_min_profit,
            'unit_size': unit_size,
            'max_units': int(1.0 // unit_size)
        }

        ledger_path = f"data/temp_optuna_ledger.csv"
        if os.path.exists(ledger_path): os.remove(ledger_path)

        account = Portfolio(initial_cash=initial_capital, symbols=[symbol], ledger_path=ledger_path)
        strategy = InstitutionalTrendStrategy(cfg=current_cfg, symbols=[symbol])
        engine = BacktestEngine(data_dict=data_dict, strategy=strategy, account=account)

        df_results = engine.run()

        if df_results.empty:
            return -999.0

        df_results['pnl'] = df_results['equity'] - initial_capital
        metrics = MetricsCalculator.calculate(df_results, initial_capital, account.trade_history)
        sharpe = float(metrics.get('夏普比率', -999.0))

        # 保存全局最优战报
        if sharpe > trial.study.user_attrs.get("best_sharpe", -999.0):
            trial.study.set_user_attr("best_sharpe", sharpe)
            best_metrics = metrics
            best_df_results = df_results
            # 实时播报一下 AI 找到的新高度
            print(
                f"   🚀 AI 突破新高! 发现夏普 {sharpe:.2f} | 收益 {metrics.get('累计收益率')} | 回撤 {metrics.get('最大回撤')}")

        return sharpe

    # 创建 AI 学习实例 (目标是最大化 Sharpe)
    study = optuna.create_study(direction="maximize")
    study.set_user_attr("best_sharpe", -999.0)

    # 启动 100 次智能试错迭代
    study.optimize(objective, n_trials=n_trials)

    # 恢复日志
    logger.setLevel(original_level)

    # 获取 AI 最终交出的顶级参数
    best_params = study.best_params

    # 将完整的最佳配置合并返回
    final_best_cfg = {**best_params}
    final_best_cfg['max_units'] = int(1.0 // final_best_cfg['unit_size'])

    print("\n" + "★" * 80)
    print(f"🏆 AI 进化完成！最优基因序列已提取")
    print("★" * 80)
    for k, v in best_params.items():
        print(f"   - {k:<25}: {v}")
    print("★" * 80 + "\n")

    return final_best_cfg, best_metrics, best_df_results


def main():
    initial_capital = 100000.0
    target_symbol = "300308"
    target_name = "中际旭创"

    logger.info("==========================================")
    logger.info(f"🔬 启动 AI 智能参数寻优系统 (Optuna): {target_name} ({target_symbol})")
    logger.info("==========================================")

    provider = AkShareProvider()
    data_df = provider.get_data(target_symbol)

    if data_df.empty:
        logger.error(f"无法获取历史数据！")
        return

    # 设定让 AI 跑 150 局 (速度极快，远胜网格1024局，且结果更好)
    best_cfg, best_metrics, best_df_results = run_ai_optimization(data_df, target_symbol, initial_capital, n_trials=150)

    if best_cfg and best_metrics:
        logger.info("==================================================")
        logger.info(f"🎯 终极成绩单 (AI 寻优极限性能)")
        logger.info("==================================================")
        logger.info(
            f"   ⚖️ 核心评分  | 夏普比率: {best_metrics.get('夏普比率')}  |  卡玛比率: {best_metrics.get('卡玛比率')}")
        logger.info(
            f"   💰 收益指标  | 累计收益: {best_metrics.get('累计收益率')} |  年化收益: {best_metrics.get('年化收益率')}")
        logger.info(
            f"   🛡️ 风险指标  | 最大回撤: {best_metrics.get('最大回撤')} |  下行波动: {best_metrics.get('下行波动率')}")
        logger.info(f"   🎯 交易统计  | 胜    率: {best_metrics.get('胜率')} |  盈 亏 比: {best_metrics.get('盈亏比')}")
        logger.info(
            f"   📊 样本数据  | 交易次数: {best_metrics.get('平仓次数')} 次   |  盈利次数: {best_metrics.get('盈利次数')} 次")
        logger.info("==================================================")
        logger.info(f"💡 最强参数组合已锁定，系统将自动生成该最优参数的分析图。")


        Plotter.plot_portfolio(
            df_res=best_df_results,
            symbols=[target_symbol],
            symbol_names={target_symbol: target_name},
            strategy_name=f"AI_Opt_{target_name}",
            save_dir="data/charts"
        )


if __name__ == "__main__":
    main()