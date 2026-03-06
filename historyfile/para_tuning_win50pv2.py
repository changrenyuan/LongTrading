import os
import json
import logging
import pandas as pd
import optuna
from datetime import datetime

# 引入核心组件
from data_provider.cloudakpd import DataCenter
from data_provider.akshare_pd import AkShareProvider
from core.account import Portfolio
from core.engineBacktest import BacktestEngine
from strategies.trend import InstitutionalTrendStrategy
from utils.metrics import MetricsCalculator
from utils.logger import global_logger as logger
from utils.plotter import Plotter

# 💡 强制 Optuna 静默，只看我们的专业审计日志
optuna.logging.set_verbosity(optuna.logging.WARNING)


def load_boss_portfolio_json(file_path="data/live_broker_account.json"):
    """📂 步骤 1: 解析老板的 JSON 持仓"""
    logger.info(f"🔍 正在解析持仓文件: {file_path}")
    if not os.path.exists(file_path):
        logger.warning(f"⚠️ 未找到持仓文件: {file_path}，将仅使用市场活跃票。")
        return [], 10000000.0

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        cash = data.get("available_cash", 10000000.0)
        positions = data.get("positions", [])

        # 提取代码并规范化为 6 位字符串
        symbols = [str(p['symbol']).zfill(6) for p in positions if 'symbol' in p]

        logger.info(f"✅ JSON 解析成功: 现金储备 {cash:,.2f} | 持仓代码: {symbols}")
        return list(set(symbols)), cash
    except Exception as e:
        logger.error(f"❌ JSON 解析崩溃: {e}")
        return [], 10000000.0


def run_portfolio_ai_optimization(data_dict, symbols, initial_capital, n_trials=500):
    """🧠 步骤 4: AI 贝叶斯寻优 (高胜率压榨模式)"""
    logger.info(f"🧠 寻优引擎启动: 样本总数 {len(symbols)} 只 | 预设试验 {n_trials} 次")
    logger.info(f"🎯 核心目标: 强行压榨胜率至 50% 以上，不达标则评分呈指数级塌陷。")

    original_level = logger.level
    # 调优期间静默回测细节，只输出关键突破
    logger.setLevel(logging.ERROR)

    best_metrics = None
    best_df_results = None

    def objective(trial):
        nonlocal best_metrics, best_df_results

        # --- 参数建议空间 ---
        ma_short = trial.suggest_int('ma_short', 3, 10)
        ma_mid = trial.suggest_int('ma_mid', 10, 30)
        ma_long = trial.suggest_int('ma_long', 60, 150, step=10)
        if ma_short >= ma_mid or ma_mid >= ma_long: raise optuna.TrialPruned()

        current_cfg = {
            'ma_short': ma_short, 'ma_mid': ma_mid, 'ma_long': ma_long,
            'bias_entry_limit': trial.suggest_float('bias_entry_limit', 1.05, 1.20, step=0.01),
            'stop_loss_pct': trial.suggest_float('stop_loss_pct', 0.03, 0.08, step=0.01),
            'trailing_stop_pct': trial.suggest_float('trailing_stop_pct', 0.10, 0.25, step=0.01),
            'profit_tier1': trial.suggest_float('profit_tier1', 0.15, 0.40, step=0.05),
            'unit_size': trial.suggest_categorical('unit_size', [0.20, 0.25, 0.33]),
            'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9, 'vol_ma_window': 20,
            'lot_size': 100, 'est_commission': 0.0003, 'max_units': int(1.0 // 0.25)
        }

        # --- 回测流程 ---
        account = Portfolio(initial_cash=initial_capital, symbols=symbols)
        strategy = InstitutionalTrendStrategy(cfg=current_cfg, symbols=symbols)
        engine = BacktestEngine(data_dict=data_dict, strategy=strategy, account=account)
        df_results = engine.run()

        if df_results.empty: return -999.0

        # --- 评分计算 (高胜率惩罚逻辑) ---
        metrics = MetricsCalculator.calculate(df_results, initial_capital, account.trade_history)
        raw = metrics["_raw"]

        win_rate = raw.get("win_rate", 0.0)
        total_return = raw.get("total_return", 0.0)
        max_dd = raw.get("max_drawdown", 1.0)

        # 💡 核心数学评分模型 (LaTeX 表达)
        # Score = TotalReturn * (WinRate / 0.5)^2 / MaxDrawdown
        win_rate_factor = (win_rate / 0.5) ** 2
        score = total_return * win_rate_factor / max(max_dd, 0.05)

        # 强力红线: 胜率低于 45% 直接给予惩罚性负分
        if win_rate < 0.45: score = -10.0 + win_rate

        if score > trial.study.user_attrs.get("best_score", -999.0):
            trial.study.set_user_attr("best_score", score)
            best_metrics = metrics
            best_df_results = df_results
            # 💡 突破时使用 print 确保在控制台高亮
            print(
                f"🔥 [局号:{trial.number}] 寻优突破! 胜率:{win_rate * 100:.1f}% | 夏普:{metrics.get('夏普比率')} | 回撤:{metrics.get('最大回撤')} | Score:{score:.2f}")

        return score

    study = optuna.create_study(direction="maximize")
    study.set_user_attr("best_score", -999.0)
    study.optimize(objective, n_trials=n_trials)

    logger.setLevel(original_level)
    return study.best_params, best_metrics, best_df_results


def main():
    logger.info("🚀 " + "=" * 50)
    logger.info("🚀 [MT_ALPHA] 高胜率 AI 寻优引擎 (JSON持仓对齐版)")
    logger.info("🚀 " + "=" * 50)

    # 1. 📂 加载老板持仓 (JSON)
    boss_symbols, initial_cash = load_boss_portfolio_json("../data/live_broker_account.json")

    # 2. 📡 获取云端选股快照
    dc = DataCenter()
    logger.info("📡 正在从云端读取最新全市场快照以锁定活跃标的...")
    snapshot_df = dc.get_snapshot_from_cloud()
    if snapshot_df.empty:
        logger.error("❌ 云端快照为空，无法选股。请先执行数据同步脚本！")
        return

    # 筛选成交额前 15 的非 ST 主板个股 (活跃“活水”)
    active_df = snapshot_df[~snapshot_df['name'].str.contains('ST')]
    active_df = active_df[active_df['symbol'].str.startswith(('60', '00', '30'))]
    active_df = active_df.sort_values(by='amount', ascending=False).head(15)
    active_symbols = active_df['symbol'].tolist()

    # 3. 🤝 股票池混合、去重
    full_symbols = list(set(active_symbols + boss_symbols))
    name_map = dict(zip(snapshot_df['symbol'], snapshot_df['name']))

    # 格式化展示池
    display_pool = [f"{s}({name_map.get(s, '持仓股')})" for s in full_symbols]
    logger.info(f"🎯 最终寻优池锁定 ({len(full_symbols)}只): {' | '.join(display_pool)}")

    # 4. 🚀 搬运 K 线历史数据 (修正进度打印 Bug)
    logger.info("🚚 正在启动数据搬运机 (AkShareProvider)...")
    provider = AkShareProvider()
    data_dict = {}

    for i, sym in enumerate(full_symbols):
        try:
            df = provider.get_data(sym)
            if not df.empty:
                data_dict[sym] = df
            # 💡 修正点：使用 i 进行取余判断进度
            if (i + 1) % 5 == 0:
                logger.info(f"   ▫️ 进度: 已加载 {i + 1}/{len(full_symbols)} 只标的数据...")
        except Exception as e:
            logger.warning(f"   ⚠️ 标的 {sym} 加载异常: {e}")

    if len(data_dict) < len(full_symbols) * 0.5:
        logger.error("❌ 可用标的数据不足 50%，寻优环境不可信，终止。")
        return

    logger.info(f"✅ 数据搬运完成，共加载 {len(data_dict)} 只标的 K 线。")

    # 5. 🧠 执行 AI 寻优
    best_params, best_metrics, best_df_res = run_portfolio_ai_optimization(
        data_dict, list(data_dict.keys()), initial_cash, n_trials=500
    )

    # 6. 🏆 结果审计与打印
    if best_params and best_metrics:
        logger.info("=" * 50)
        logger.info("🏆 [寻优结果] 找到一组符合胜率预期的最优参数:")
        for k, v in best_params.items():
            logger.info(f"   👉 {k:<20}: {v}")
        logger.info("-" * 50)
        logger.info(f"🎯 战果统计: 胜率 {best_metrics.get('胜率')} | 夏普 {best_metrics.get('夏普比率')}")
        logger.info(f"📈 绩效追踪: 累计收益 {best_metrics.get('累计收益率')} | 最大回撤 {best_metrics.get('最大回撤')}")
        logger.info("=" * 50)

        # 出图存档
        Plotter.plot_portfolio(
            df_res=best_df_res, symbols=full_symbols,
            symbol_names={s: name_map.get(s, '未知') for s in full_symbols},
            strategy_name="AI_WinRate_Final", save_dir="../data/charts"
        )
    else:
        logger.error("❌ 寻优未能找到有效参数组。")


if __name__ == "__main__":
    main()