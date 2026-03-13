"""
回测主程序
=========
支持UI配置驱动和最优参数读取
"""
import os
import json
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any

from data_provider.akshare_pd import AkShareProvider
from core.account import Portfolio
from core.engineBacktest import BacktestEngine
from strategies.trend import InstitutionalTrendStrategy
from utils.metrics import MetricsCalculator
from utils.pushjson import PushJSON
from utils.logger import global_logger as logger

from backtest_config import (
    load_optimized_params, load_backtest_config, create_task_id,
    update_task_status, save_config_snapshot
)


def run_backtest(config_path: str = "data/config/backtest_config.json",
                 params_path: str = "data/config/trend_strategy_params.json") -> Optional[str]:
    """
    运行回测

    Args:
        config_path: 回测配置文件路径
        params_path: 策略最优参数文件路径

    Returns:
        任务ID（成功）或 None（失败）
    """
    # 1. 加载配置
    config = load_backtest_config(config_path)
    optimized_params = load_optimized_params(params_path)

    # 2. 创建任务ID和输出目录
    task_id = create_task_id()
    start_time = datetime.now()
    output_dir = os.path.join("data", "backtest", task_id)
    os.makedirs(output_dir, exist_ok=True)

    # 3. 初始化任务状态
    update_task_status(task_id, "running", {
        "step": "初始化回测引擎", "progress": 0, "start_time": start_time.isoformat()
    })

    try:
        # 4. 提取配置参数
        symbols = config["stock_pool"]["symbols"]
        symbol_names = config["stock_pool"]["symbol_names"]
        initial_capital = config["capital"]["initial_capital"]
        pricing_mode = config["execution"].get("pricing_mode", "conservative")

        # 5. 决定使用哪个参数
        use_optimized = config.get("strategy", {}).get("use_optimized_params", True)
        strategy_params = optimized_params if use_optimized and optimized_params \
                         else config.get("strategy", {}).get("custom_params", {})

        logger.info(f"📊 {'使用最优参数' if use_optimized else '使用自定义参数'}进行回测")

        # 6. 保存配置快照
        save_config_snapshot(output_dir, task_id, config, strategy_params)

        # 7. 准备交易备忘录
        ledger_path = os.path.join(output_dir, "ledger.csv")
        positions_path = os.path.join(output_dir, "positions.csv")
        for p in [ledger_path, positions_path]:
            if os.path.exists(p):
                os.remove(p)

        # 8. 获取历史数据
        update_task_status(task_id, "running", {
            "step": "获取历史数据", "progress": 10,
            "start_time": start_time.isoformat(),
            "elapsed_seconds": (datetime.now() - start_time).seconds
        })

        provider = AkShareProvider()
        data_dict = {}
        for sym in symbols:
            df = provider.get_data(sym)
            if not df.empty:
                data_dict[sym] = df
                logger.info(f"✅ [{sym}] 获取数据成功: {len(df)} 条记录")
            else:
                logger.warning(f"⚠️ [{sym}] 获取数据失败，跳过")

        if not data_dict:
            raise ValueError("所有股票数据获取失败")

        # 9. 初始化引擎
        update_task_status(task_id, "running", {
            "step": "初始化回测引擎", "progress": 20,
            "start_time": start_time.isoformat(),
            "elapsed_seconds": (datetime.now() - start_time).seconds
        })

        account = Portfolio(initial_cash=initial_capital, symbols=list(data_dict.keys()),
                           ledger_path=ledger_path)
        strategy = InstitutionalTrendStrategy(symbols=list(data_dict.keys()), cfg=strategy_params if strategy_params else None)
        engine = BacktestEngine(data_dict=data_dict, strategy=strategy, account=account, pricing_mode=pricing_mode)

        # 10. 运行回测
        update_task_status(task_id, "running", {
            "step": "运行回测计算", "progress": 30,
            "start_time": start_time.isoformat(),
            "elapsed_seconds": (datetime.now() - start_time).seconds
        })

        logger.info(f"🚀 开始回测，任务ID: {task_id}")
        df_results = engine.run()

        if df_results.empty:
            raise ValueError("回测结果为空")

        # 11. 计算绩效指标
        update_task_status(task_id, "running", {
            "step": "计算绩效指标", "progress": 70,
            "start_time": start_time.isoformat(),
            "elapsed_seconds": (datetime.now() - start_time).seconds
        })

        df_results['pnl'] = df_results['equity'] - initial_capital
        eval_metrics = MetricsCalculator.calculate(df_results, initial_capital, account.trade_history)

        # 计算真实胜率
        win_trades = sum(1 for t in account.trade_history if t['action'] == 'SELL' and t['realized_pnl'] > 0)
        loss_trades = sum(1 for t in account.trade_history if t['action'] == 'SELL' and t['realized_pnl'] <= 0)
        total_exits = win_trades + loss_trades
        real_win_rate = (win_trades / total_exits * 100) if total_exits > 0 else 0

        # 打印绩效报告
        _print_report(task_id, initial_capital, df_results, eval_metrics, real_win_rate, total_exits)

        # 12. 导出JSON数据
        update_task_status(task_id, "running", {
            "step": "导出结果数据", "progress": 90,
            "start_time": start_time.isoformat(),
            "elapsed_seconds": (datetime.now() - start_time).seconds
        })

        PushJSON.export_all(df_res=df_results, account=account, symbols=list(data_dict.keys()),
                            symbol_names=symbol_names, data_dict=data_dict,
                            strategy_id=task_id, base_save_dir="data/backtest")

        # 13. 保存绩效汇总
        _save_summary(output_dir, task_id, symbols, initial_capital, use_optimized,
                     strategy_params, df_results, eval_metrics, real_win_rate, account.trade_history, total_exits)

        # 14. 完成
        elapsed = (datetime.now() - start_time).seconds
        update_task_status(task_id, "completed", {
            "step": "回测完成", "progress": 100,
            "start_time": start_time.isoformat(),
            "elapsed_seconds": elapsed,
            "result": {"completed": True, "success": True, "error_message": None, "output_dir": output_dir}
        })

        logger.info(f"🎉 回测完成！任务ID: {task_id}")
        logger.info(f"📁 结果保存在: {output_dir}")
        return task_id

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ 回测失败: {error_msg}")
        update_task_status(task_id, "failed", {
            "step": "回测失败", "progress": 0,
            "start_time": start_time.isoformat(),
            "elapsed_seconds": (datetime.now() - start_time).seconds,
            "result": {"completed": False, "success": False, "error_message": error_msg, "output_dir": output_dir}
        })
        raise


def _print_report(task_id: str, initial_capital: float, df_results: pd.DataFrame,
                  eval_metrics: Dict, win_rate: float, total_exits: int):
    """打印绩效报告"""
    print("\n" + "=" * 60)
    print("🏆 策略核心绩效评估报告 (Tear Sheet)")
    print("=" * 60)
    print(f"📋 任务ID:     {task_id}")
    print(f"💰 初始本金:   {initial_capital:,.2f}")
    print(f"💵 最终权益:   {df_results['equity'].iloc[-1]:,.2f}")
    print(f"📈 累计收益率: {eval_metrics.get('累计收益率')}")
    print(f"🚀 年化收益率: {eval_metrics.get('年化收益率')}")
    print(f"📉 最大回撤:   {eval_metrics.get('最大回撤')}")
    print(f"⚖️ 夏普比率:   {eval_metrics.get('夏普比率')}")
    print(f"🛡️ 卡玛比率:   {eval_metrics.get('卡玛比率')}")
    print(f"🎯 真实胜率:   {win_rate:.1f}% (共 {total_exits} 次平仓)")
    print("=" * 60 + "\n")


def _save_summary(output_dir: str, task_id: str, symbols: list, initial_capital: float,
                  use_optimized: bool, strategy_params: Dict, df_results: pd.DataFrame,
                  eval_metrics: Dict, win_rate: float, trades: list, total_exits: int):
    """保存绩效汇总"""
    summary = {
        "version": "1.0",
        "task_id": task_id,
        "completed_at": datetime.now().isoformat(),
        "config": {"symbols": symbols, "initial_capital": initial_capital, "use_optimized_params": use_optimized},
        "params_used": strategy_params,
        "performance": {
            "initial_capital": initial_capital,
            "final_equity": float(df_results['equity'].iloc[-1]),
            "total_return": eval_metrics.get("累计收益率"),
            "annualized_return": eval_metrics.get("年化收益率"),
            "max_drawdown": eval_metrics.get("最大回撤"),
            "sharpe_ratio": eval_metrics.get("夏普比率"),
            "calmar_ratio": eval_metrics.get("卡玛比率"),
            "win_rate": f"{win_rate:.1f}%",
            "total_trades": len(trades),
            "total_exits": total_exits
        }
    }

    with open(os.path.join(output_dir, "summary.json"), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


# ==================== 命令行入口 ====================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MT_Alpha 回测引擎")
    parser.add_argument("--config", default="data/config/backtest_config.json", help="回测配置文件路径")
    parser.add_argument("--params", default="data/config/trend_strategy_params.json", help="策略最优参数文件路径")
    args = parser.parse_args()

    task_id = run_backtest(args.config, args.params)

    if task_id:
        print(f"\n✅ 回测成功完成！任务ID: {task_id}")
        print(f"📊 查看结果: data/backtest/{task_id}/summary.json")
    else:
        print("\n❌ 回测失败！请检查日志。")
