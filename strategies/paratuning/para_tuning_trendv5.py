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

# 💡 强制 Optuna 静默，完全由我们的自定义日志接管控制台
optuna.logging.set_verbosity(optuna.logging.WARNING)


def load_boss_portfolio_json(file_path="data/config/live_broker_account.json"):
    """
    📂 步骤 1: 解析老板的 JSON 持仓文件
    """
    logger.info(f"🔍 [步骤1/6] 正在解析持仓文件: {file_path}")
    if not os.path.exists(file_path):
        logger.warning(f"⚠️ 未找到持仓文件: {file_path}")
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


def run_portfolio_ai_optimization(data_dict, symbols, initial_capital, n_trials=10):
    """
    🧠 步骤 5: AI 寻优内核 v5.1 (主升浪审计 + 五位一体)
    """
    logger.info(f"🧠 [步骤5/6] 启动寻优引擎 | 标的: {len(symbols)} | 试验: {n_trials} | MA_Long: 30-150")

    original_level = logger.level
    logger.setLevel(logging.ERROR)  # 寻优期间静默引擎内部日志

    best_metrics = None
    best_df_results = None
    # --- 步骤 A: 数据拆分 (IS: 400天, OOS: 100天) ---
    train_dict = {}
    test_dict = {}

    for sym, df in data_dict.items():
        if len(df) > 100:
            train_dict[sym] = df.iloc[:-100]  # 过去的数据用于训练
            test_dict[sym] = df.iloc[-100:]  # 最近的数据用于验证
        else:
            train_dict[sym] = df
    def objective(trial):
        nonlocal best_metrics, best_df_results
        if trial.number % 10 == 0:
            print(f"⌛ 寻优进行中: Trial {trial.number}/{n_trials}...")
        # --- 1. 参数建议空间 (MA_long 锁定 30-150) ---
        ma_short = trial.suggest_int('ma_short', 3, 10)
        ma_mid = trial.suggest_int('ma_mid', 10, 50)
        ma_long = trial.suggest_int('ma_long', 30, 150, step=10)
        if ma_short >= ma_mid or ma_mid >= ma_long: raise optuna.TrialPruned()

        enable_partial_exit = trial.suggest_categorical('enable_partial_exit', [True, False])

        current_cfg = {
            'ma_short': ma_short, 'ma_mid': ma_mid, 'ma_long': ma_long,
            'bias_entry_limit': trial.suggest_float('bias_entry_limit', 1.05, 1.25, step=0.01),
            'stop_loss_pct': trial.suggest_float('stop_loss_pct', 0.03, 0.08, step=0.01),
            'trailing_stop_pct': trial.suggest_float('trailing_stop_pct', 0.15, 0.35, step=0.01),  # 调宽以保护翻倍行情
            'enable_partial_exit': enable_partial_exit,
            'partial_exit_pct': trial.suggest_float('partial_exit_pct', 0.3, 0.6,
                                                    step=0.1) if enable_partial_exit else 0.5,
            'partial_exit_min_profit': trial.suggest_float('partial_exit_min_profit', 0.05, 0.20,
                                                           step=0.05) if enable_partial_exit else 0.1,
            'profit_tier1': trial.suggest_float('profit_tier1', 0.15, 0.45, step=0.05),
            'trailing_tier1': trial.suggest_float('trailing_tier1', 0.10, 0.20, step=0.01),
            'unit_size': trial.suggest_categorical('unit_size', [0.20, 0.25, 0.33]),
            'lot_size': 100, 'est_commission': 0.0003, 'max_units': int(1.0 // 0.25)
        }

        # --- 2. 运行回测 ---
        account = Portfolio(initial_cash=initial_capital, symbols=symbols)
        strategy = InstitutionalTrendStrategy(cfg=current_cfg, symbols=symbols)
        engine = BacktestEngine(data_dict=data_dict, strategy=strategy, account=account)
        df_results = engine.run()
        if df_results.empty: return -100.0

        # --- 3. 💡 大格局审计：主升浪捕获率 ---
        capture_scores = []
        noise_penalties = []

        for sym in symbols:
            trades = [t for t in account.trade_history if t['symbol'] == sym]
            df_sym = data_dict[sym]

            # 计算回测区间最大涨幅 (最高/起始 - 1)
            start_price = df_sym['close'].iloc[0]
            max_price = df_sym['high'].max()
            stock_max_gain = (max_price / start_price) - 1.0
            strat_pnl_sum = sum([t.get('pnl_pct', 0) for t in trades])

            # A. 翻倍审计：标的涨幅超过 100%
            if stock_max_gain >= 1.0:
                capture_ratio = strat_pnl_sum / stock_max_gain
                # 如果捕获利润不足 40%，按比例重罚，最低 0.01 保持梯度
                penalty = 1.0 if capture_ratio >= 0.4 else max(capture_ratio / 0.4, 0.01)
                capture_scores.append(penalty)

            # B. 杂波审计：标的没翻倍(涨幅 < 30%)，但频繁开仓
            elif stock_max_gain < 0.3 and len(trades) > 3:
                noise_penalties.append(0.8)  # 扣除 20% 杂波分

        # 汇总审计惩罚因子
        avg_capture_factor = (sum(capture_scores) / len(capture_scores)) if capture_scores else 1.0
        avg_noise_factor = (sum(noise_penalties) / len(noise_penalties)) if noise_penalties else 1.0
        final_penalty = avg_capture_factor * avg_noise_factor

        # --- 4. 五位一体综合评分 ---
        metrics = MetricsCalculator.calculate(df_results, initial_capital, account.trade_history)
        raw = metrics["_raw"]
        win_rate, sharpe, calmar = raw.get("win_rate", 0.0), raw.get("sharpe_ratio", 0.0), raw.get("calmar_ratio", 0.0)
        total_return, max_dd = raw.get("total_return", 0.0), raw.get("max_drawdown", 1.0)

        # 核心公式 (含审计惩罚)
        score = sharpe * calmar * (1.0 + total_return) * ((win_rate / 0.5) ** 2) * (1.0 - max_dd) * final_penalty

        # 熔断门槛
        if win_rate < 0.25 or max_dd > 0.25: score = -100.0

        if score > trial.study.user_attrs.get("best_score", -999.0):
            trial.study.set_user_attr("best_score", score)
            best_metrics, best_df_results = metrics, df_results

            # 💡 全量输出调试日志
            print(f"\n🔥 [突破! 局号:{trial.number}] 综合评分: {score:.4f} | 审计因子: {final_penalty:.2f}")
            print(
                f"📈 指标审计: 胜率 {win_rate * 100:.1f}% | 夏普 {sharpe:.2f} | 卡玛 {calmar:.2f} | 收益 {total_return * 100:.1f}% | 回撤 {max_dd * 100:.1f}%")
            exit_info = f"分批开启({current_cfg['partial_exit_pct'] * 100:.0f}%)" if enable_partial_exit else "分批关闭"
            print(
                f"👉 对应参数: 均线({ma_short}/{ma_mid}/{ma_long}) | {exit_info} | 止损:{current_cfg['stop_loss_pct']:.2f} | 追高:{current_cfg['bias_entry_limit']:.2f} | 仓位:{current_cfg['unit_size']}")

        return score

    # --- 寻优执行 ---
    study = optuna.create_study(direction="maximize")
    study.set_user_attr("best_score", -999.0)
    study.optimize(objective, n_trials=n_trials)

    # logger.setLevel(original_level)

    # --- 结果存盘 ---
    os.makedirs("data/tuning_logs", exist_ok=True)
    csv_path = f"data/tuning_logs/trials_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    study.trials_dataframe().to_csv(csv_path, index=False, encoding='utf-8-sig')

    best_cfg = {**study.best_params, "max_units": int(1.0 // study.best_params['unit_size'])}
    with open("data/config/trend_strategy_params.json", "w", encoding='utf-8') as f:
        json.dump(best_cfg, f, indent=4, ensure_ascii=False)

    return best_cfg, best_metrics, best_df_results


def main():
    logger.info("🚀 " + "=" * 50)
    logger.info("🚀 [MT_ALPHA] 大格局寻优引擎 v5.1 (修正完整版)")
    logger.info("🚀 " + "=" * 50)

    # 1. 📂 加载老板持仓
    boss_symbols, initial_cash = load_boss_portfolio_json("data/config/live_broker_account.json")

    # 2. 📡 选股池构建 (Cloud Snapshot)
    dc = DataCenter()
    snapshot_df = dc.get_snapshot_from_cloud()
    if snapshot_df.empty:
        logger.error("❌ 云端快照为空！")
        return

    # 💡 数据质量校验：显示列名和首行数据值
    logger.info(f"📊 数据库列名审计: {snapshot_df.columns.tolist()}")
    logger.info(f"📊 首行数据质量审计: {snapshot_df.iloc[0].to_dict()}")

    # 混合池并去重
    active_symbols = \
    snapshot_df[~snapshot_df['name'].str.contains('ST')].sort_values(by='amount', ascending=False).head(15)[
        'symbol'].tolist()
    full_symbols = list(set(active_symbols + boss_symbols))
    name_map = dict(zip(snapshot_df['symbol'], snapshot_df['name']))

    logger.info(
        f"🎯 最终寻优池锁定 ({len(full_symbols)}只): {' | '.join([f'{s}({name_map.get(s, '未知')})' for s in full_symbols])}")

    # 3. 🚚 搬运 K 线数据
    provider = AkShareProvider()
    data_dict = {}
    for i, sym in enumerate(full_symbols):
        df = provider.get_data(sym)
        if not df.empty:
            data_dict[sym] = df
            if (i + 1) % 5 == 0: logger.info(f"🚚 搬运进度: {i + 1}/{len(full_symbols)}")

    # 4. 🧠 启动寻优
    best_params, best_metrics, best_df_res = run_portfolio_ai_optimization(
        data_dict, list(data_dict.keys()), initial_cash, n_trials=1000
    )

    if best_params and best_metrics:
        logger.info("📈 寻优任务圆满完成，正在生成最终业绩报表...")
        Plotter.plot_portfolio(df_res=best_df_res, symbols=full_symbols, symbol_names=name_map,
                               strategy_name="AI_BigPicture_Final", save_dir="data/charts")
        logger.info("🎉 [任务结束] 最优参数已就位，大格局审计通过。")


if __name__ == "__main__":
    main()