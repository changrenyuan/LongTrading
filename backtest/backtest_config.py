"""
回测配置管理
===========
"""
import os
import json
from datetime import datetime
from typing import Dict, Any

from utils.logger import global_logger as logger


def load_optimized_params(params_path: str = "data/config/trend_strategy_params.json") -> Dict[str, Any]:
    """加载策略最优参数"""
    if not os.path.exists(params_path):
        logger.warning(f"最优参数文件不存在: {params_path}")
        return {}

    with open(params_path, 'r', encoding='utf-8') as f:
        params = json.load(f)

    logger.info(f"✅ 已加载最优参数: {params_path}")
    logger.info(f"   - MA周期: {params.get('ma_short')}/{params.get('ma_mid')}/{params.get('ma_long')}")
    logger.info(f"   - 止损: {params.get('stop_loss_pct') * 100:.1f}%")
    return params


def load_backtest_config(config_path: str = "data/config/backtest_config.json") -> Dict[str, Any]:
    """加载回测配置"""
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
            "symbol_names": {"300502": "新易盛", "300308": "中际旭创", "601606": "长城军工"}
        },
        "capital": {"initial_capital": 1000000.0},
        "backtest_period": {"use_custom_period": False},
        "strategy": {"strategy_name": "InstitutionalTrendStrategy", "use_optimized_params": True},
        "execution": {"pricing_mode": "conservative", "commission_rate": 0.0003}
    }


def create_task_id() -> str:
    """创建任务ID"""
    return f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def update_task_status(task_id: str, status: str, progress: Dict[str, Any],
                       output_base_dir: str = "data/backtest"):
    """更新任务状态文件"""
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
            "completed": False, "success": False,
            "error_message": None, "output_dir": None
        })
    }

    os.makedirs(os.path.dirname(status_file), exist_ok=True)
    with open(status_file, 'w', encoding='utf-8') as f:
        json.dump(task_status, f, ensure_ascii=False, indent=2)


def save_config_snapshot(output_dir: str, task_id: str, config: Dict, params: Dict):
    """保存配置快照"""
    snapshot = {
        "task_id": task_id,
        "created_at": datetime.now().isoformat(),
        "backtest_config": config,
        "strategy_params": params if config.get("strategy", {}).get("use_optimized_params", True)
                          else config.get("strategy", {}).get("custom_params", {})
    }

    path = os.path.join(output_dir, "config_snapshot.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    logger.info(f"📄 配置快照已保存: {path}")
