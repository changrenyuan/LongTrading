import os
import glob
import logging
import pandas as pd
import optuna

from data_provider.akshare_pd import AkShareProvider
from core.account import Portfolio
from core.engineBacktest import BacktestEngine
from strategies.trend import InstitutionalTrendStrategy
from utils.metrics import MetricsCalculator
from utils.logger import global_logger as logger
from utils.plotter import Plotter

optuna.logging.set_verbosity(optuna.logging.WARNING)


def get_top_stocks_from_local_csv(csv_path="data/market_snapshot.csv", top_n=5):
    """
    从本地提取 Top N 龙头，组成我们的【联合测试组合】
    """
    logger.info(f"正在从本地读取市场快照: {csv_path}")
    try:
        if not os.path.exists(csv_path):
            csv_files = glob.glob("data_provider/test_cache_data/*spot*.csv") + glob.glob(
                "data_provider/test_cache_data/*snapshot*.csv")
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
    """
    🧠 投资组合级 AI 贝叶斯寻优 (全维度参数解禁版)
    """
    logger.info(f"🧠 AI 开始【多股联合盘】智能推演，全维度参数已解禁，目标：寻找最高通用夏普！")

    original_level = logger.level
    logger.setLevel(logging.ERROR)

    best_metrics = None
    best_df_results = None

    def objective(trial):
        nonlocal best_metrics, best_df_results

        # ==========================================
        # 🧠 AI 全维度参数寻优考卷 (Full Parameters)
        # ==========================================

        # 1. 均线周期 (解禁了长期均线)
        ma_short = trial.suggest_int('ma_short', 3, 10)
        ma_mid = trial.suggest_int('ma_mid', 10, 25)
        ma_long = trial.suggest_int('ma_long', 40, 120, step=10)
        if ma_short >= ma_mid or ma_mid >= ma_long:
            raise optuna.TrialPruned()  # 均线必须多头排列，否则掐死

        # 2. 开仓与加仓限制 (进场微操)
        bias_entry_limit = trial.suggest_float('bias_entry_limit', 1.05, 1.25, step=0.01)
        pullback_support_upper = trial.suggest_float('pullback_support_upper', 1.01, 1.15, step=0.01)
        add_pos_min_profit = trial.suggest_float('add_pos_min_profit', 0.0, 0.08, step=0.01)

        # 3. 突破指标 (解禁空中加油参数)
        breakout_window = trial.suggest_int('breakout_window', 5, 20)
        breakout_vol_limit = trial.suggest_float('breakout_vol_limit', 1.1, 1.5, step=0.1)

        # 4. 基础风控与底线
        stop_loss_pct = trial.suggest_float('stop_loss_pct', 0.05, 0.15, step=0.01)
        trailing_stop_pct = trial.suggest_float('trailing_stop_pct', 0.15, 0.30, step=0.01)

        # 5. 分档止盈体系 (全解禁：一档和二档全交由AI控制)
        profit_tier1 = trial.suggest_float('profit_tier1', 0.20, 0.60, step=0.05)
        trailing_tier1 = trial.suggest_float('trailing_tier1', 0.10, 0.20, step=0.01)

        profit_tier2 = trial.suggest_float('profit_tier2', 0.60, 1.50, step=0.10)
        trailing_tier2 = trial.suggest_float('trailing_tier2', 0.05, 0.15, step=0.01)

        # 逻辑防呆：二档利润必须高于一档，二档回撤必须严于一档
        if profit_tier1 >= profit_tier2 or trailing_tier1 <= trailing_tier2:
            raise optuna.TrialPruned()

        # 6. 分批止盈落袋机制 (解禁开关与比例)
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
            # 依然被锁死的“定海神针”参数
            'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9, 'vol_ma_window': 20,
            'trend_ma_diff': 5, 'trend_strength_buffer': 1.05,
            'pullback_bias_limit': 1.05, 'pullback_support_lower': 0.95,
            'trend_broken_lower': 0.98, 'trend_broken_vol': 1.2,
            'lot_size': 100, 'est_commission': 0.0003,

            # --- 以下全是 AI 动态生成的参数 ---
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

        # ==========================================
        # ⚙️ 引擎执行与结果返回 (上次你可能漏复制了这里)
        # ==========================================
        ledger_path = "data/temp_portfolio_ledger.csv"
        if os.path.exists(ledger_path): os.remove(ledger_path)
        if os.path.exists(ledger_path.replace("ledger", "positions")): os.remove(
            ledger_path.replace("ledger", "positions"))

        # 让这 5 只股票在一个大管家下联合回测
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

    # 创建 AI 学习实例 (目标是最大化 Sharpe)
    study = optuna.create_study(direction="maximize")
    study.set_user_attr("best_sharpe", -999.0)

    # 启动智能试错迭代
    study.optimize(objective, n_trials=n_trials)

    # 恢复日志
    logger.setLevel(original_level)
    best_params = study.best_params

    final_best_cfg = {**best_params}
    final_best_cfg['max_units'] = int(1.0 // final_best_cfg['unit_size'])

    print("\n" + "★" * 80)
    print(f"🏆 【多股通用】全维度反人性核心参数已提取！")
    print("★" * 80)
    for k, v in best_params.items():
        print(f"   - {k:<25}: {v}")
    print("★" * 80 + "\n")

    return final_best_cfg, best_metrics, best_df_results
def main():
    initial_capital = 1000000.0  # 大资金：100万

    logger.info("==========================================")
    logger.info("🌍 启动【多股联合盘】防过拟合 AI 寻优...")
    logger.info("==========================================")

    # 💡 选出全市场最猛的 5 只龙头，作为我们的联合考验篮子
    csv_path = "data_provider/test_cache_data/market_snapshot_20260228.csv"  # 指向你本地的数据
    symbols, symbol_names = get_top_stocks_from_local_csv(csv_path, top_n=5)
    if not symbols: return

    provider = AkShareProvider()
    data_dict = {}
    for sym in symbols:
        df = provider.get_data(sym)
        if not df.empty:
            data_dict[sym] = df

    if not data_dict:
        logger.error("数据拉取失败！")
        return

    # 让 AI 在这 5 只票上同时跑 200 局
    best_cfg, best_metrics, best_df_results = run_portfolio_ai_optimization(data_dict, list(data_dict.keys()),
                                                                            initial_capital, n_trials=200)

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

        # 将绘制这个组合资金曲线的终极图表
        Plotter.plot_portfolio(
            df_res=best_df_results,
            symbols=symbols,
            symbol_names=symbol_names,
            strategy_name=f"AI_Portfolio_Master",
            save_dir="data/charts"
        )


if __name__ == "__main__":
    main()