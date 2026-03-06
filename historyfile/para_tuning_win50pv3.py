import os
import json
import logging
import pandas as pd
import optuna
from datetime import datetime

# 核心组件引入
from data_provider.cloudakpd import DataCenter
from data_provider.akshare_pd import AkShareProvider
from core.account import Portfolio
from core.engineBacktest import BacktestEngine
from strategies.trend import InstitutionalTrendStrategy
from utils.metrics import MetricsCalculator
from utils.logger import global_logger as logger
from utils.plotter import Plotter

# 💡 强制 Optuna 静默，完全由我们的自定义 Logger 接管输出
optuna.logging.set_verbosity(optuna.logging.WARNING)


def load_boss_portfolio_json(file_path="data/live_broker_account.json"):
    """
    📂 步骤 1: 解析老板的 JSON 持仓文件 (对齐规划)
    """
    logger.info(f"🔍 [步骤1/6] 正在解析持仓文件: {file_path}")
    if not os.path.exists(file_path):
        logger.warning(f"⚠️ 未找到持仓文件: {file_path}，将仅使用市场活跃票。")
        return [], 10000000.0

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        cash = data.get("available_cash", 10000000.0)
        positions = data.get("positions", [])

        # 提取并规范化代码为 6 位字符串
        symbols = [str(p['symbol']).zfill(6) for p in positions if 'symbol' in p]

        logger.info(f"✅ JSON 加载成功: 初始现金 {cash:,.2f} | 现有持仓: {symbols}")
        return list(set(symbols)), cash
    except Exception as e:
        logger.error(f"❌ JSON 解析崩溃: {e}")
        return [], 10000000.0


def run_portfolio_ai_optimization(data_dict, symbols, initial_capital, n_trials=500):
    """
    🧠 步骤 5: AI 贝叶斯寻优 (五位一体评分模型)
    目标：高胜率、高夏普、高卡玛、盈利增长、超低回撤
    """
    logger.info(f"🧠 [步骤5/6] 启动 AI 寻优引擎 | 标的总数: {len(symbols)} | 预设试验: {n_trials} 次")
    logger.info(f"🎯 寻优红线: 胜率 < 45% 或 最大回撤 > 15% 将触发评分熔断。")

    original_level = logger.level
    logger.setLevel(logging.ERROR)  # 寻优期间静默引擎内部日志

    best_metrics = None
    best_df_results = None

    def objective(trial):
        nonlocal best_metrics, best_df_results

        # --- 1. 参数搜索空间 (ma_short/mid/long, 止损/止盈比例, 仓位) ---
        ma_short = trial.suggest_int('ma_short', 3, 10)
        ma_mid = trial.suggest_int('ma_mid', 10, 30)
        ma_long = trial.suggest_int('ma_long', 60, 150, step=10)
        if ma_short >= ma_mid or ma_mid >= ma_long: raise optuna.TrialPruned()

        current_cfg = {
            'ma_short': ma_short, 'ma_mid': ma_mid, 'ma_long': ma_long,
            'bias_entry_limit': trial.suggest_float('bias_entry_limit', 1.05, 1.25, step=0.01),
            'stop_loss_pct': trial.suggest_float('stop_loss_pct', 0.03, 0.08, step=0.01),
            'trailing_stop_pct': trial.suggest_float('trailing_stop_pct', 0.10, 0.25, step=0.01),
            'profit_tier1': trial.suggest_float('profit_tier1', 0.15, 0.45, step=0.05),
            'trailing_tier1': trial.suggest_float('trailing_tier1', 0.10, 0.20, step=0.01),
            'unit_size': trial.suggest_categorical('unit_size', [0.20, 0.25, 0.33]),
            # 固定策略常数
            'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9, 'vol_ma_window': 20,
            'lot_size': 100, 'est_commission': 0.0003, 'max_units': int(1.0 // 0.25)
        }

        # --- 2. 运行回测引擎 ---
        account = Portfolio(initial_cash=initial_capital, symbols=symbols)
        strategy = InstitutionalTrendStrategy(cfg=current_cfg, symbols=symbols)
        engine = BacktestEngine(data_dict=data_dict, strategy=strategy, account=account)
        df_results = engine.run()

        if df_results.empty: return -100.0

        # --- 3. 复合评分逻辑 (五位一体) ---
        metrics = MetricsCalculator.calculate(df_results, initial_capital, account.trade_history)
        raw = metrics["_raw"]

        win_rate = raw.get("win_rate", 0.0)
        total_return = raw.get("total_return", 0.0)
        max_dd = raw.get("max_drawdown", 1.0)
        sharpe = raw.get("sharpe_ratio", 0.0)
        calmar = raw.get("calmar_ratio", 0.0)

        # 核心公式: Score = Sharpe * Calmar * (1 + Return) * (WinRate/0.5)^2 * (1 - MaxDD)
        # 任何一个指标过差，总分都会极速塌陷
        win_rate_factor = (win_rate / 0.5) ** 2
        dd_factor = (1.0 - max_dd)
        score = sharpe * calmar * (1.0 + total_return) * win_rate_factor * dd_factor

        # 💡 强制熔断红线
        if win_rate < 0.45 or max_dd > 0.15:
            score = -100.0

        if score > trial.study.user_attrs.get("best_score", -999.0):
            trial.study.set_user_attr("best_score", score)
            best_metrics = metrics
            best_df_results = df_results

            # 💡 关键：按要求显示【指标明细】+【对应参数】
            print(f"\n🔥 [突破! 局号:{trial.number}] 综合评分: {score:.4f}")
            print(
                f"📈 指标审计: 胜率 {win_rate * 100:.1f}% | 夏普 {sharpe:.2f} | 卡玛 {calmar:.2f} | 收益 {total_return * 100:.1f}% | 回撤 {max_dd * 100:.1f}%")
            print(
                f"👉 对应参数: 均线({ma_short}/{ma_mid}/{ma_long}) | 追高:{current_cfg['bias_entry_limit']:.2f} | 止损:{current_cfg['stop_loss_pct']:.2f} | 仓位:{current_cfg['unit_size']}")

        return score

    # 4. 执行 Optuna 搜索
    study = optuna.create_study(direction="maximize")
    study.set_user_attr("best_score", -999.0)
    study.optimize(objective, n_trials=n_trials)

    logger.setLevel(original_level)

    # --- 6. 结果保存 (步骤 6/6) ---
    # 💾 全量 CSV 保存
    df_trials = study.trials_dataframe(attrs=('number', 'value', 'params', 'state'))
    df_trials = df_trials[df_trials['state'] == 'COMPLETE'].sort_values(by='value', ascending=False)

    os.makedirs("../data/tuning_logs", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = f"data/tuning_logs/optuna_log_{ts}.csv"
    df_trials.to_csv(csv_path, index=False, encoding='utf-8-sig')
    logger.info(f"💾 [步骤6/6] 全量试验记录已存入: {csv_path}")

    # 💾 最优参数 JSON 导出
    best_cfg = {**study.best_params, "max_units": int(1.0 // study.best_params['unit_size'])}
    json_path = "../data/best_params_win50p.json"
    with open(json_path, "w", encoding='utf-8') as f:
        json.dump(best_cfg, f, indent=4, ensure_ascii=False)
    logger.info(f"💾 最优参数组已导出: {json_path}")

    return best_cfg, best_metrics, best_df_results


def main():
    logger.info("🚀 " + "=" * 50)
    logger.info("🚀 [MT_ALPHA] 高胜率/高卡玛 AI 寻优内核 v3.0")
    logger.info("🚀 " + "=" * 50)

    # 1. 加载持仓 (JSON)
    boss_symbols, initial_cash = load_boss_portfolio_json("../data/live_broker_account.json")

    # 2. 选股 (Cloud Snapshot)
    dc = DataCenter()
    logger.info("📡 [步骤2/6] 正在从云端读取快照选股...")
    snapshot_df = dc.get_snapshot_from_cloud()
    if snapshot_df.empty:
        logger.error("❌ 云端数据为空，请先运行数据中心同步脚本！")
        return

    # 筛选活跃活水
    active_df = snapshot_df[~snapshot_df['name'].str.contains('ST')]
    active_df = active_df[active_df['symbol'].str.startswith(('60', '00', '30'))]
    active_df = active_df.sort_values(by='amount', ascending=False).head(15)
    active_symbols = active_df['symbol'].tolist()

    # 3. 股票池大合兵
    full_symbols = list(set(active_symbols + boss_symbols))
    name_map = dict(zip(snapshot_df['symbol'], snapshot_df['name']))

    # 打印最终寻优池 (代码+名称)
    pool_display = [f"{s}({name_map.get(s, '持仓股')})" for s in full_symbols]
    logger.info(f"🎯 [步骤3/6] 寻优池已锁定 ({len(full_symbols)}只): {' | '.join(pool_display)}")

    # 4. 搬运 K 线 (进度实时 Logger)
    logger.info("🚚 [步骤4/6] 正在搬运历史 K 线数据 (AkShareProvider)...")
    provider = AkShareProvider()
    data_dict = {}
    for i, sym in enumerate(full_symbols):
        try:
            df = provider.get_data(sym)
            if not df.empty:
                data_dict[sym] = df
            if (i + 1) % 5 == 0:
                logger.info(f"   ▫️ 加载进度: {i + 1}/{len(full_symbols)} ({((i + 1) / len(full_symbols)) * 100:.0f}%)")
        except Exception as e:
            logger.warning(f"   ⚠️ 标的 {sym} 加载异常: {e}")

    if len(data_dict) == 0:
        logger.error("❌ 数据环境构建失败，程序终止。")
        return

    # 5. 启动寻优与结果落袋
    best_params, best_metrics, best_df_res = run_portfolio_ai_optimization(
        data_dict, list(data_dict.keys()), initial_cash, n_trials=500
    )

    # 最终可视化出图
    if best_params and best_metrics:
        logger.info("📈 [审计完成] 正在绘制回测业绩曲线图...")
        Plotter.plot_portfolio(
            df_res=best_df_res, symbols=full_symbols,
            symbol_names={s: name_map.get(s, '未知') for s in full_symbols},
            strategy_name="AI_WinRate_Final", save_dir="../data/charts"
        )
        logger.info("🎉 寻优任务圆满结束。")


if __name__ == "__main__":
    main()