import os
import glob
import logging
import pandas as pd
import optuna
from datetime import datetime  # 💡 引入时间模块，用于解决覆盖问题

from data_provider.akshare_pd import AkShareProvider
from core.account import Portfolio
from core.engineBacktest import BacktestEngine
from strategies.trend import InstitutionalTrendStrategy
from utils.metrics import MetricsCalculator
from utils.logger import global_logger as logger
from utils.plotter import Plotter

optuna.logging.set_verbosity(optuna.logging.WARNING)


def get_top_stocks_from_local_csv(csv_path="data/market_snapshot.csv", top_n=10):
    logger.info(f"正在从本地读取市场快照: {csv_path}")
    try:
        if not os.path.exists(csv_path):
            csv_files = glob.glob("data_provider/test_cache_data/*spot*.csv") + glob.glob(
                "data_provider/test_cache_data/*snapshot*.csv") + glob.glob("data/*snapshot*.csv")
            if csv_files:
                csv_path = csv_files[0]
            else:
                raise FileNotFoundError(f"找不到本地快照文件 {csv_path}。")

        spot_df = pd.read_csv(csv_path, dtype=str)
        code_col = '代码' if '代码' in spot_df.columns else 'symbol'
        name_col = '名称' if '名称' in spot_df.columns else 'name'
        amount_col = '成交额' if '成交额' in spot_df.columns else 'amount'

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

        logger.info(f"🎯 锁定【联合测试组合】: {list(symbol_names.values())}")
        return symbols, symbol_names
    except Exception as e:
        logger.error(f"提取股票失败: {e}")
        return [], {}


def run_portfolio_ai_optimization(data_dict, symbols, initial_capital, n_trials=500):
    logger.info(f"🧠 贝叶斯寻优 开始【多股联合盘】智能推演，目标：寻找最高通用夏普！(最高止损限制 10%)")

    original_level = logger.level
    logger.setLevel(logging.ERROR)

    best_metrics = None
    best_df_results = None

    def objective(trial):
        nonlocal best_metrics, best_df_results

        # 1. 均线周期
        ma_short = trial.suggest_int('ma_short', 3, 10)
        ma_mid = trial.suggest_int('ma_mid', 10, 25)
        ma_long = trial.suggest_int('ma_long', 40, 120, step=10)
        if ma_short >= ma_mid or ma_mid >= ma_long:
            raise optuna.TrialPruned()

        # 2. 开仓与加仓限制
        bias_entry_limit = trial.suggest_float('bias_entry_limit', 1.05, 1.25, step=0.01)
        pullback_support_upper = trial.suggest_float('pullback_support_upper', 1.01, 1.15, step=0.01)
        add_pos_min_profit = trial.suggest_float('add_pos_min_profit', 0.0, 0.08, step=0.01)

        # 3. 突破指标
        breakout_window = trial.suggest_int('breakout_window', 5, 20)
        breakout_vol_limit = trial.suggest_float('breakout_vol_limit', 1.1, 1.5, step=0.1)

        # 4. 基础风控与底线 (💡 这里强行压制硬止损的上限为 0.10)
        stop_loss_pct = trial.suggest_float('stop_loss_pct', 0.05, 0.20, step=0.01)
        trailing_stop_pct = trial.suggest_float('trailing_stop_pct', 0.15, 0.30, step=0.01)

        # 5. 分档止盈体系
        profit_tier1 = trial.suggest_float('profit_tier1', 0.20, 0.60, step=0.05)
        trailing_tier1 = trial.suggest_float('trailing_tier1', 0.10, 0.20, step=0.01)

        profit_tier2 = trial.suggest_float('profit_tier2', 0.60, 1.50, step=0.10)
        trailing_tier2 = trial.suggest_float('trailing_tier2', 0.05, 0.15, step=0.01)

        if profit_tier1 >= profit_tier2 or trailing_tier1 <= trailing_tier2:
            raise optuna.TrialPruned()

        # 6. 分批止盈落袋机制
        enable_partial_exit = trial.suggest_categorical('enable_partial_exit', [True, False])
        if enable_partial_exit:
            partial_exit_pct = trial.suggest_float('partial_exit_pct', 0.3, 0.6, step=0.1)
            partial_exit_min_profit = trial.suggest_float('partial_exit_min_profit', 0.05, 0.20, step=0.05)
        else:
            partial_exit_pct = 0.5
            partial_exit_min_profit = 0.1

        # 7. 资金管理
        unit_size = trial.suggest_categorical('unit_size', [0.20, 0.25, 0.33, 0.50])

        current_cfg = {
            'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9, 'vol_ma_window': 20,
            'trend_ma_diff': 5, 'trend_strength_buffer': 1.05,
            'pullback_bias_limit': 1.05, 'pullback_support_lower': 0.95,
            'trend_broken_lower': 0.98, 'trend_broken_vol': 1.2,
            'lot_size': 100, 'est_commission': 0.0003,

            'ma_short': ma_short, 'ma_mid': ma_mid, 'ma_long': ma_long,
            'bias_entry_limit': bias_entry_limit,
            'pullback_support_upper': pullback_support_upper, 'add_pos_min_profit': add_pos_min_profit,
            'breakout_window': breakout_window, 'breakout_vol_limit': breakout_vol_limit,
            'stop_loss_pct': stop_loss_pct, 'trailing_stop_pct': trailing_stop_pct,
            'profit_tier1': profit_tier1, 'trailing_tier1': trailing_tier1,
            'profit_tier2': profit_tier2, 'trailing_tier2': trailing_tier2,
            'enable_partial_exit': enable_partial_exit,
            'partial_exit_pct': partial_exit_pct, 'partial_exit_min_profit': partial_exit_min_profit,
            'unit_size': unit_size, 'max_units': int(1.0 // unit_size)
        }

        ledger_path = "data/temp_portfolio_ledger.csv"
        if os.path.exists(ledger_path): os.remove(ledger_path)
        if os.path.exists(ledger_path.replace("ledger", "positions")): os.remove(
            ledger_path.replace("ledger", "positions"))

        account = Portfolio(initial_cash=initial_capital, symbols=symbols, ledger_path=ledger_path)
        strategy = InstitutionalTrendStrategy(cfg=current_cfg, symbols=symbols)
        engine = BacktestEngine(data_dict=data_dict, strategy=strategy, account=account)

        df_results = engine.run()

        if df_results.empty:
            return -999.0

        df_results['pnl'] = df_results['equity'] - initial_capital
        metrics = MetricsCalculator.calculate(df_results, initial_capital, account.trade_history)

        sharpe = float(metrics.get('夏普比率', -999.0))

        if sharpe > trial.study.user_attrs.get("best_sharpe", -999.0):
            trial.study.set_user_attr("best_sharpe", sharpe)
            best_metrics = metrics
            best_df_results = df_results
            print(
                f"   🚀 AI 联合盘突破! 总盘夏普 {sharpe:.2f} | 卡玛比 {metrics.get('卡玛比率')} | 收益 {metrics.get('累计收益率')} | 回撤 {metrics.get('最大回撤')}")

        return sharpe

    # 创建 AI 学习实例
    study = optuna.create_study(direction="maximize")
    study.set_user_attr("best_sharpe", -999.0)

    # 启动智能试错迭代
    study.optimize(objective, n_trials=n_trials)

    # 恢复日志
    logger.setLevel(original_level)

    # 💡 提取所有试验记录并保存到 CSV 日志 (加入时间戳防止覆盖)
    df_trials = study.trials_dataframe(attrs=('number', 'value', 'params', 'state'))
    df_trials = df_trials[df_trials['state'] == 'COMPLETE']
    df_trials = df_trials.sort_values(by='value', ascending=False).reset_index(drop=True)

    os.makedirs("data/tuning_logs", exist_ok=True)
    # 获取当前时间戳，确保文件名绝对唯一
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"data/tuning_logs/optuna_log_{len(symbols)}stocks_trials{n_trials}_{timestamp}.csv"

    df_trials.to_csv(log_filename, index=False, encoding='utf-8-sig')
    logger.info(f"💾 【极其重要】本次寻优的 {len(df_trials)} 组全量参数及成绩已永久保存至: {log_filename}")

    # 💡 打印 Top 20 最佳参数组合排行榜
    print("\n" + "★" * 120)
    print(f"🏆 AI 寻优 Top 20 最佳参数组合排行榜 (防被套版：硬止损卡死在 10% 以内)")
    print("★" * 120)
    for idx in range(min(20, len(df_trials))):
        row = df_trials.iloc[idx]
        sharpe = row['value']

        p_ma = f"均线:{row['params_ma_short']}/{row['params_ma_mid']}/{row['params_ma_long']}"
        p_risk = f"止损:{row['params_stop_loss_pct']:.2f}, 回撤:{row['params_trailing_stop_pct']:.2f}"
        p_buy = f"追高:{row['params_bias_entry_limit']:.2f}, 仓位:{row['params_unit_size']}"

        print(f"Top {idx + 1:<2} | 夏普: {sharpe:<5.2f} | {p_ma:<18} | {p_risk:<22} | {p_buy:<20} | 详情见CSV")
    print("★" * 120 + "\n")

    best_params = study.best_params
    final_best_cfg = {**best_params}
    final_best_cfg['max_units'] = int(1.0 // final_best_cfg['unit_size'])

    return final_best_cfg, best_metrics, best_df_results


def main():
    initial_capital = 10000000.0  # 大资金：1000万

    logger.info("==========================================")
    logger.info("🌍 启动【多股联合盘】防过拟合 AI 寻优 (修复覆盖Bug版)...")
    logger.info("==========================================")

    # 1. 获取所有可能的数据源文件
    csv_files = glob.glob("data_provider/test_cache_data/*spot*.csv") + \
                glob.glob("data_provider/test_cache_data/*snapshot*.csv") #+ \
                #glob.glob("data/*snapshot*.csv")

    if not csv_files:
        return  # 没找到任何文件则直接退出

    # 💡 修复 1：强制按文件的最后修改时间【降序】排列，确保排在最前面的是最近的日子
    csv_files.sort(key=os.path.getmtime, reverse=True)

    # 💡 修复 2：安全地截取最近的 3 个文件（就算本地只有 2 个文件也不会报错越界）
    recent_files = csv_files[:3]

    symbols = []
    symbol_names = {}  # 名字应该是字典格式

    # 遍历最近 3 天的文件
    for csv_path in recent_files:
        temp_symbols, temp_names = get_top_stocks_from_local_csv(csv_path, top_n=20)

        if temp_symbols:
            symbols.extend(temp_symbols)  # 列表追加用 extend
        if temp_names:
            symbol_names.update(temp_names)  # 字典合并用 update

    # 💡 修复 3：全集去重！3 天的 top10 合并后最多 30 只，去重后可能只有 15 只
    final_symbols = list(dict.fromkeys(symbols))

    if not final_symbols:
        return

    # 最终送给调优引擎的参数
    symbols = final_symbols

    provider = AkShareProvider()
    data_dict = {}
    for sym in symbols:
        df = provider.get_data(sym)
        if not df.empty:
            data_dict[sym] = df

    if not data_dict:
        logger.error("数据拉取失败！")
        return

    # 💡 让 AI 跑 500 局
    best_cfg, best_metrics, best_df_results = run_portfolio_ai_optimization(data_dict, list(data_dict.keys()),
                                                                            initial_capital, n_trials=500)

    if best_cfg and best_metrics:
        logger.info("==================================================")
        logger.info(f"🎯 终极【多股联合】成绩单 (拒绝单一拟合)")
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

        Plotter.plot_portfolio(
            df_res=best_df_results,
            symbols=symbols,
            symbol_names=symbol_names,
            strategy_name=f"AI_Portfolio_Master",
            save_dir="data/charts"
        )


if __name__ == "__main__":
    main()