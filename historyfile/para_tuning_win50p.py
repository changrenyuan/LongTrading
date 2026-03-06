import os
import logging
import pandas as pd
import optuna
from datetime import datetime

# 💡 核心逻辑：DataCenter 选股，AkShareProvider 拿 K 线
from data_provider.cloudakpd import DataCenter
from data_provider.akshare_pd import AkShareProvider
from core.account import Portfolio
from core.engineBacktest import BacktestEngine
from strategies.trend import InstitutionalTrendStrategy
from utils.metrics import MetricsCalculator
from utils.logger import global_logger as logger
from utils.plotter import Plotter

optuna.logging.set_verbosity(optuna.logging.WARNING)


def run_portfolio_ai_optimization(data_dict, symbols, initial_capital, n_trials=500):
    """
    🧠 贝叶斯寻优：高胜率优先模式 (Win-Rate > 50% 强制约束)
    """
    logger.info(f"🧠 AI 开始【多股联合盘】寻优，目标：强行拉升胜率至 50% 以上！")

    original_level = logger.level
    logger.setLevel(logging.ERROR)

    best_metrics = None
    best_df_results = None

    def objective(trial):
        nonlocal best_metrics, best_df_results

        # 1. 参数搜索空间 (ma_short/mid/long, 止损等)
        ma_short = trial.suggest_int('ma_short', 3, 10)
        ma_mid = trial.suggest_int('ma_mid', 10, 30)
        ma_long = trial.suggest_int('ma_long', 60, 150, step=10)
        if ma_short >= ma_mid or ma_mid >= ma_long: raise optuna.TrialPruned()

        current_cfg = {
            'ma_short': ma_short, 'ma_mid': ma_mid, 'ma_long': ma_long,
            'bias_entry_limit': trial.suggest_float('bias_entry_limit', 1.05, 1.20, step=0.01),
            'stop_loss_pct': trial.suggest_float('stop_loss_pct', 0.03, 0.08, step=0.01),  # 💡 强行收紧硬止损
            'trailing_stop_pct': trial.suggest_float('trailing_stop_pct', 0.10, 0.25, step=0.01),
            'profit_tier1': trial.suggest_float('profit_tier1', 0.15, 0.40, step=0.05),
            'unit_size': trial.suggest_categorical('unit_size', [0.20, 0.25, 0.33]),
            'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9, 'vol_ma_window': 20,
            'lot_size': 100, 'est_commission': 0.0003, 'max_units': int(1.0 // 0.25)
        }

        # 2. 回测执行
        account = Portfolio(initial_cash=initial_capital, symbols=symbols)
        strategy = InstitutionalTrendStrategy(cfg=current_cfg, symbols=symbols)
        engine = BacktestEngine(data_dict=data_dict, strategy=strategy, account=account)
        df_results = engine.run()

        if df_results.empty: return -999.0

        # 3. 绩效计算
        metrics = MetricsCalculator.calculate(df_results, initial_capital, account.trade_history)
        raw = metrics["_raw"]

        win_rate = raw.get("win_rate", 0.0)
        total_return = raw.get("total_return", 0.0)
        max_dd = raw.get("max_drawdown", 1.0)

        # 4. 🔥 核心：胜率惩罚目标函数
        # 目标：Score = 收益率 * (当前胜率 / 0.5) 的平方 / 最大回撤
        win_rate_factor = (win_rate / 0.5) ** 2
        score = total_return * win_rate_factor / max(max_dd, 0.05)

        # 💡 强行红线：胜率低于 45% 的直接淘汰或给地狱分
        if win_rate < 0.45:
            score = -10.0 + win_rate

        if score > trial.study.user_attrs.get("best_score", -999.0):
            trial.study.set_user_attr("best_score", score)
            best_metrics = metrics
            best_df_results = df_results
            print(
                f"🚀 突破! 胜率:{win_rate * 100:.1f}% | 收益:{metrics.get('累计收益率')} | 夏普:{metrics.get('夏普比率')} | 分数:{score:.2f}")

        return score

    study = optuna.create_study(direction="maximize")
    study.set_user_attr("best_score", -999.0)
    study.optimize(objective, n_trials=n_trials)

    logger.setLevel(original_level)
    return study.best_params, best_metrics, best_df_results


def main():
    initial_capital = 10000000.0
    dc = DataCenter()

    # 1. 💡 从云端读取最新全貌选股
    logger.info("📡 正在从云端读取最新市场全貌...")
    snapshot_df = dc.get_snapshot_from_cloud()
    if snapshot_df.empty:
        logger.error("❌ 云端快照为空，请确认同步脚本已运行！")
        return

    # 筛选成交额前 15 的非 ST 个股
    top_df = snapshot_df[~snapshot_df['name'].str.contains('ST')]
    top_df = top_df[top_df['symbol'].str.startswith(('60', '00', '30'))]
    top_df = top_df.sort_values(by='amount', ascending=False).head(15)

    symbols = top_df['symbol'].tolist()

    # 💡 改进 1：打印时显示 代码(名称)
    target_display = [f"{row['symbol']}({row['name']})" for _, row in top_df.iterrows()]
    logger.info(f"🎯 已锁定活跃标的: {target_display}")

    # 💡 改进 2：使用 AkShareProvider.get_data 获取历史 K 线
    provider = AkShareProvider()
    data_dict = {}
    for sym in symbols:
        df = provider.get_data(sym)  # 调用您要求的 get_data 函数
        if not df.empty:
            data_dict[sym] = df

    if not data_dict:
        logger.error("❌ 未能成功获取任何 K 线历史数据！")
        return

    # 3. 运行 AI 调优
    best_params, best_metrics, best_df_results = run_portfolio_ai_optimization(
        data_dict, list(data_dict.keys()), initial_capital, n_trials=500
    )

    if best_params and best_metrics:
        logger.info("==================================================")
        logger.info(f"🏆 AI 调优大功告成！高胜率参数组如下:")
        for k, v in best_params.items():
            logger.info(f"   {k}: {v}")
        logger.info("-" * 50)
        logger.info(f"🎯 核心胜率: {best_metrics.get('胜率')} | 盈亏比: {best_metrics.get('盈亏比')}")
        logger.info(f"📈 累计收益: {best_metrics.get('累计收益率')} | 夏普: {best_metrics.get('夏普比率')}")
        logger.info("==================================================")

        # 4. 存盘可视化
        Plotter.plot_portfolio(
            df_res=best_df_results, symbols=symbols,
            symbol_names={row['symbol']: row['name'] for _, row in top_df.iterrows()},
            strategy_name="AI_WinRate_Optimized", save_dir="data/charts"
        )


if __name__ == "__main__":
    main()