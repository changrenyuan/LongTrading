"""
回测主程序 - 支持UI配置驱动和最优参数读取
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


# ==================== 配置管理 ====================

def load_optimized_params(params_path: str = "data/config/trend_strategy_params.json") -> Dict[str, Any]:
    """
    加载策略最优参数（从调优结果文件读取）

    Args:
        params_path: 最优参数文件路径

    Returns:
        参数字典
    """
    if not os.path.exists(params_path):
        logger.warning(f"最优参数文件不存在: {params_path}")
        return {}

    with open(params_path, 'r', encoding='utf-8') as f:
        params = json.load(f)

    logger.info(f"✅ 已加载最优参数: {params_path}")
    logger.info(f"   - MA周期: {params.get('ma_short')}/{params.get('ma_mid')}/{params.get('ma_long')}")
    logger.info(f"   - 止损: {params.get('stop_loss_pct') * 100:.1f}%")
    logger.info(f"   - 移动止盈: {params.get('trailing_stop_pct') * 100:.1f}%")

    return params


def load_backtest_config(config_path: str = "data/config/backtest_config.json") -> Dict[str, Any]:
    """
    加载回测配置（股票池、资金等）

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    if not os.path.exists(config_path):
        logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
        return get_default_config()

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    logger.info(f"✅ 已加载回测配置: {config_path}")
    return config


def get_default_config() -> Dict[str, Any]:
    """获取默认配置"""
    return {
        "version": "1.0",
        "stock_pool": {
            "symbols": ["300502", "300308", "601606"],
            "symbol_names": {
                "300502": "新易盛",
                "300308": "中际旭创",
                "601606": "长城军工"
            }
        },
        "capital": {
            "initial_capital": 1000000.0
        },
        "backtest_period": {
            "use_custom_period": False
        },
        "strategy": {
            "strategy_name": "InstitutionalTrendStrategy",
            "use_optimized_params": True
        },
        "execution": {
            "pricing_mode": "conservative",
            "commission_rate": 0.0003
        }
    }


# ==================== 任务状态管理 ====================

def create_task_id() -> str:
    """创建任务ID"""
    return f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def update_task_status(task_id: str, status: str, progress: Dict[str, Any],
                       output_base_dir: str = "data/backtest"):
    """
    更新任务状态文件

    Args:
        task_id: 任务ID
        status: 任务状态 (idle, running, completed, failed)
        progress: 进度信息
        output_base_dir: 输出基础目录
    """
    status_file = os.path.join(output_base_dir, "task_status.json")

    task_status = {
        "version": "1.0",
        "task_id": task_id,
        "status": status,
        "last_update": datetime.now().isoformat(),
        "progress": {
            "current_step": progress.get("step", ""),
            "progress_pct": progress.get("progress", 0),
            "start_time": progress.get("start_time"),
            "elapsed_seconds": progress.get("elapsed_seconds", 0)
        },
        "result": progress.get("result", {
            "completed": False,
            "success": False,
            "error_message": None,
            "output_dir": None
        })
    }

    os.makedirs(os.path.dirname(status_file), exist_ok=True)
    with open(status_file, 'w', encoding='utf-8') as f:
        json.dump(task_status, f, ensure_ascii=False, indent=2)


# ==================== 主函数 ====================

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

    # 2. 创建任务ID
    task_id = create_task_id()
    start_time = datetime.now()

    # 创建输出目录
    output_dir = os.path.join("data", "backtest", task_id)
    os.makedirs(output_dir, exist_ok=True)

    # 3. 初始化任务状态
    update_task_status(task_id, "running", {
        "step": "初始化回测引擎",
        "progress": 0,
        "start_time": start_time.isoformat()
    })

    try:
        # 4. 保存配置快照（包含使用的参数）
        config_snapshot = {
            "task_id": task_id,
            "created_at": datetime.now().isoformat(),
            "backtest_config": config,
            "strategy_params": optimized_params if config.get("strategy", {}).get("use_optimized_params",
                                                                                  True) else config.get("strategy",
                                                                                                        {}).get(
                "custom_params", {})
        }

        config_snapshot_path = os.path.join(output_dir, "config_snapshot.json")
        with open(config_snapshot_path, 'w', encoding='utf-8') as f:
            json.dump(config_snapshot, f, ensure_ascii=False, indent=2)
        logger.info(f"📄 配置快照已保存: {config_snapshot_path}")

        # 5. 提取配置参数
        symbols = config["stock_pool"]["symbols"]
        symbol_names = config["stock_pool"]["symbol_names"]
        initial_capital = config["capital"]["initial_capital"]
        pricing_mode = config["execution"].get("pricing_mode", "conservative")

        # 6. 决定使用哪个参数
        use_optimized = config.get("strategy", {}).get("use_optimized_params", True)
        if use_optimized and optimized_params:
            strategy_params = optimized_params
            logger.info("📊 使用最优参数进行回测")
        else:
            strategy_params = config.get("strategy", {}).get("custom_params", {})
            logger.info("📊 使用自定义参数进行回测")

        # 7. 准备交易备忘录
        ledger_path = os.path.join(output_dir, "ledger.csv")
        positions_path = os.path.join(output_dir, "positions.csv")

        # 清理旧文件
        if os.path.exists(ledger_path):
            os.remove(ledger_path)
        if os.path.exists(positions_path):
            os.remove(positions_path)

        # 8. 更新状态：获取数据
        update_task_status(task_id, "running", {
            "step": "获取历史数据",
            "progress": 10,
            "start_time": start_time.isoformat(),
            "elapsed_seconds": (datetime.now() - start_time).seconds
        })

        # 9. 获取历史数据
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

        # 10. 更新状态：初始化引擎
        update_task_status(task_id, "running", {
            "step": "初始化回测引擎",
            "progress": 20,
            "start_time": start_time.isoformat(),
            "elapsed_seconds": (datetime.now() - start_time).seconds
        })

        # 11. 初始化账户
        account = Portfolio(
            initial_cash=initial_capital,
            symbols=list(data_dict.keys()),
            ledger_path=ledger_path
        )

        # 12. 初始化策略（使用参数）
        strategy = InstitutionalTrendStrategy(
            symbols=list(data_dict.keys()),
            cfg=strategy_params if strategy_params else None
        )

        # 13. 初始化引擎
        engine = BacktestEngine(
            data_dict=data_dict,
            strategy=strategy,
            account=account,
            pricing_mode=pricing_mode
        )

        # 14. 更新状态：运行回测
        update_task_status(task_id, "running", {
            "step": "运行回测计算",
            "progress": 30,
            "start_time": start_time.isoformat(),
            "elapsed_seconds": (datetime.now() - start_time).seconds
        })

        # 15. 运行回测
        logger.info(f"🚀 开始回测，任务ID: {task_id}")
        df_results = engine.run()

        if df_results.empty:
            raise ValueError("回测结果为空")

        # 16. 更新状态：计算绩效
        update_task_status(task_id, "running", {
            "step": "计算绩效指标",
            "progress": 70,
            "start_time": start_time.isoformat(),
            "elapsed_seconds": (datetime.now() - start_time).seconds
        })

        # 17. 计算绩效指标
        df_results['pnl'] = df_results['equity'] - initial_capital
        eval_metrics = MetricsCalculator.calculate(df_results, initial_capital, account.trade_history)

        # 计算真实胜率
        real_trades = account.trade_history
        win_trades = sum(1 for t in real_trades if t['action'] == 'SELL' and t['realized_pnl'] > 0)
        loss_trades = sum(1 for t in real_trades if t['action'] == 'SELL' and t['realized_pnl'] <= 0)
        total_exits = win_trades + loss_trades
        real_win_rate = (win_trades / total_exits * 100) if total_exits > 0 else 0

        # 打印绩效报告
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
        print(f"🎯 真实胜率:   {real_win_rate:.1f}% (共 {total_exits} 次平仓)")
        print("=" * 60 + "\n")

        # 18. 更新状态：导出JSON
        update_task_status(task_id, "running", {
            "step": "导出结果数据",
            "progress": 90,
            "start_time": start_time.isoformat(),
            "elapsed_seconds": (datetime.now() - start_time).seconds
        })

        # 19. 导出JSON数据
        PushJSON.export_all(
            df_res=df_results,
            account=account,
            symbols=list(data_dict.keys()),
            symbol_names=symbol_names,
            data_dict=data_dict,
            strategy_id=task_id,
            base_save_dir="data/backtest"
        )

        # 20. 保存绩效汇总
        summary = {
            "version": "1.0",
            "task_id": task_id,
            "completed_at": datetime.now().isoformat(),
            "config": {
                "symbols": symbols,
                "initial_capital": initial_capital,
                "use_optimized_params": use_optimized
            },
            "params_used": strategy_params,
            "performance": {
                "initial_capital": initial_capital,
                "final_equity": float(df_results['equity'].iloc[-1]),
                "total_return": eval_metrics.get("累计收益率"),
                "annualized_return": eval_metrics.get("年化收益率"),
                "max_drawdown": eval_metrics.get("最大回撤"),
                "sharpe_ratio": eval_metrics.get("夏普比率"),
                "calmar_ratio": eval_metrics.get("卡玛比率"),
                "win_rate": f"{real_win_rate:.1f}%",
                "total_trades": len(real_trades),
                "total_exits": total_exits
            }
        }

        summary_path = os.path.join(output_dir, "summary.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        # 21. 更新状态：完成
        elapsed = (datetime.now() - start_time).seconds
        update_task_status(task_id, "completed", {
            "step": "回测完成",
            "progress": 100,
            "start_time": start_time.isoformat(),
            "elapsed_seconds": elapsed,
            "result": {
                "completed": True,
                "success": True,
                "error_message": None,
                "output_dir": output_dir
            }
        })

        logger.info(f"🎉 回测完成！任务ID: {task_id}")
        logger.info(f"📁 结果保存在: {output_dir}")

        return task_id

    except Exception as e:
        # 错误处理
        error_msg = str(e)
        logger.error(f"❌ 回测失败: {error_msg}")

        update_task_status(task_id, "failed", {
            "step": "回测失败",
            "progress": 0,
            "start_time": start_time.isoformat(),
            "elapsed_seconds": (datetime.now() - start_time).seconds,
            "result": {
                "completed": False,
                "success": False,
                "error_message": error_msg,
                "output_dir": output_dir
            }
        })

        raise


# ==================== 命令行入口 ====================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MT_Alpha 回测引擎")
    parser.add_argument(
        "--config",
        default="data/config/backtest_config.json",
        help="回测配置文件路径"
    )
    parser.add_argument(
        "--params",
        default="data/config/trend_strategy_params.json",
        help="策略最优参数文件路径"
    )

    args = parser.parse_args()

    # 运行回测
    task_id = run_backtest(args.config, args.params)

    if task_id:
        print(f"\n✅ 回测成功完成！任务ID: {task_id}")
        print(f"📊 查看结果: data/backtest/{task_id}/summary.json")
    else:
        print("\n❌ 回测失败！请检查日志。")
