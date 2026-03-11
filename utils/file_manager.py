"""
数据文件路径管理器
统一管理所有数据文件的路径，支持新旧路径兼容
"""
import os
from typing import Dict, Optional

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ==================== 新目录结构定义 ====================
DIR_STRUCTURE = {
    "config": os.path.join(BASE_DIR, "data", "config"),
    "market": os.path.join(BASE_DIR, "data", "market"),
    "ledger": os.path.join(BASE_DIR, "data", "ledger"),
    "trade": os.path.join(BASE_DIR, "data", "trade"),
    "backtest": os.path.join(BASE_DIR, "data", "backtest"),
    "system": os.path.join(BASE_DIR, "data", "system"),
    "archive": os.path.join(BASE_DIR, "data", "archive"),
}

# ==================== 文件路径定义（新结构） ====================
FILE_PATHS = {
    # 配置模块
    "strategy_params": os.path.join(DIR_STRUCTURE["config"], "strategy_params.json"),
    "universe_pool": os.path.join(DIR_STRUCTURE["config"], "universe_pool.json"),
    "risk_config": os.path.join(DIR_STRUCTURE["config"], "risk_config.json"),

    # 行情快照模块
    "market_snapshot": os.path.join(DIR_STRUCTURE["market"], "snapshot.json"),
    "realtime_quotes": os.path.join(DIR_STRUCTURE["market"], "realtime_quotes.json"),

    # 账户与账本模块
    "broker_account": os.path.join(DIR_STRUCTURE["ledger"], "broker_account.json"),
    "system_account": os.path.join(DIR_STRUCTURE["ledger"], "system_account.json"),
    "portfolio": os.path.join(DIR_STRUCTURE["ledger"], "portfolio.json"),
    "nav_history": os.path.join(DIR_STRUCTURE["ledger"], "nav_history.json"),
    "reconciliation": os.path.join(DIR_STRUCTURE["ledger"], "reconciliation.json"),

    # 交易信号模块
    "signals_today": os.path.join(DIR_STRUCTURE["trade"], "signals_today.json"),
    "orders_pending": os.path.join(DIR_STRUCTURE["trade"], "orders_pending.json"),
    "orders_history": os.path.join(DIR_STRUCTURE["trade"], "orders_history.json"),
    "trade_ledger": os.path.join(DIR_STRUCTURE["trade"], "ledger.csv"),

    # 回测模块
    "backtest_result": os.path.join(DIR_STRUCTURE["backtest"], "latest_result.json"),
    "backtest_summary": os.path.join(DIR_STRUCTURE["backtest"], "summary.json"),
    "equity_curve": os.path.join(DIR_STRUCTURE["backtest"], "equity_curve.json"),
    "drawdown": os.path.join(DIR_STRUCTURE["backtest"], "drawdown.json"),
    "backtest_trades": os.path.join(DIR_STRUCTURE["backtest"], "trades.json"),
    "backtest_stocks": os.path.join(DIR_STRUCTURE["backtest"], "stocks_overview.json"),

    # 系统状态模块
    "engine_state": os.path.join(DIR_STRUCTURE["system"], "engine_state.json"),
    "runtime_metrics": os.path.join(DIR_STRUCTURE["system"], "runtime_metrics.json"),
}

# ==================== 旧路径到新路径的映射（向后兼容） ====================
LEGACY_PATH_MAPPING = {
    # 旧路径 → 新路径
    os.path.join(BASE_DIR, "data", "best_params_win50p.json"): FILE_PATHS["strategy_params"],
    os.path.join(BASE_DIR, "data", "universe_pool.json"): FILE_PATHS["universe_pool"],
    os.path.join(BASE_DIR, "data", "live_broker_account.json"): FILE_PATHS["broker_account"],
    os.path.join(BASE_DIR, "data", "system_account.json"): FILE_PATHS["system_account"],
    os.path.join(BASE_DIR, "data", "portfolio_assets.json"): FILE_PATHS["portfolio"],
    os.path.join(BASE_DIR, "data", "market_status.json"): FILE_PATHS["market_snapshot"],
    os.path.join(BASE_DIR, "data", "live_trade_ledger.csv"): FILE_PATHS["trade_ledger"],
}


class PathManager:
    """路径管理器：统一管理所有数据文件路径"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.base_dir = BASE_DIR
        self.dirs = DIR_STRUCTURE
        self.files = FILE_PATHS
        self.legacy_mapping = LEGACY_PATH_MAPPING

        # 确保目录存在
        self._ensure_directories()

    def _ensure_directories(self):
        """确保所有目录都存在"""
        for dir_path in self.dirs.values():
            os.makedirs(dir_path, exist_ok=True)

        # 创建子目录
        os.makedirs(os.path.join(self.dirs["market"], "kline_cache"), exist_ok=True)
        os.makedirs(os.path.join(self.dirs["backtest"], "kline"), exist_ok=True)
        os.makedirs(os.path.join(self.dirs["backtest"], "optimization"), exist_ok=True)
        os.makedirs(os.path.join(self.dirs["system"], "logs"), exist_ok=True)
        os.makedirs(os.path.join(self.dirs["system"], "debug"), exist_ok=True)

    def get_path(self, file_key: str) -> str:
        """
        获取文件路径（支持向后兼容）

        Args:
            file_key: 文件键名（如 "strategy_params", "portfolio" 等）

        Returns:
            文件的完整路径
        """
        if file_key in self.files:
            new_path = self.files[file_key]
            # 如果新路径存在，直接返回
            if os.path.exists(new_path):
                return new_path

            # 否则检查旧路径是否存在
            for old_path, mapped_new_path in self.legacy_mapping.items():
                if mapped_new_path == new_path and os.path.exists(old_path):
                    return old_path

            # 都不存在，返回新路径（用于创建新文件）
            return new_path

        raise ValueError(f"未知的文件键: {file_key}")

    def get_kline_cache_path(self, symbol: str) -> str:
        """获取K线缓存文件路径"""
        return os.path.join(self.dirs["market"], "kline_cache", f"{symbol}.json")

    def get_backtest_kline_path(self, symbol: str) -> str:
        """获取回测K线文件路径"""
        return os.path.join(self.dirs["backtest"], "kline", f"{symbol}.json")

    def get_log_path(self, date_str: str, log_type: str = "trade") -> str:
        """获取日志文件路径"""
        return os.path.join(self.dirs["system"], "logs", f"{date_str}_{log_type}.log")

    def get_archive_path(self, date_str: str) -> str:
        """获取归档目录路径"""
        archive_dir = os.path.join(self.dirs["archive"], date_str)
        os.makedirs(archive_dir, exist_ok=True)
        return archive_dir

    def migrate_to_new_structure(self):
        """
        迁移旧文件到新目录结构
        执行一次即可，迁移后旧路径会创建软链接
        """
        print("=" * 80)
        print("📦 开始迁移数据文件到新目录结构...")
        print("=" * 80)

        migrated_count = 0

        for old_path, new_path in self.legacy_mapping.items():
            if not os.path.exists(old_path):
                print(f"⏭️  跳过: {os.path.basename(old_path)} (不存在)")
                continue

            if os.path.exists(new_path):
                print(f"✅ 已存在: {os.path.basename(new_path)}")
                continue

            # 创建目标目录
            os.makedirs(os.path.dirname(new_path), exist_ok=True)

            # 移动文件
            import shutil
            shutil.move(old_path, new_path)
            print(f"✅ 迁移: {os.path.basename(old_path)} → {os.path.basename(new_path)}")

            # 创建软链接保持向后兼容
            os.symlink(os.path.abspath(new_path), old_path)
            print(f"🔗 创建软链接: {os.path.basename(old_path)}")

            migrated_count += 1

        print("=" * 80)
        print(f"🎉 迁移完成！共迁移 {migrated_count} 个文件。")
        print("=" * 80)

        return migrated_count

    def list_all_files(self) -> Dict[str, Dict[str, str]]:
        """列出所有文件及其状态"""
        result = {}

        for key, path in self.files.items():
            exists = os.path.exists(path)
            size = os.path.getsize(path) if exists else 0
            mtime = os.path.getmtime(path) if exists else None

            result[key] = {
                "path": path,
                "exists": exists,
                "size_bytes": size,
                "modified_time": mtime
            }

        return result


# ==================== 全局单例 ====================
path_manager = PathManager()


# ==================== 便捷函数 ====================
def get_data_path(file_key: str) -> str:
    """获取数据文件路径（快捷函数）"""
    return path_manager.get_path(file_key)


def ensure_data_dirs():
    """确保数据目录存在（快捷函数）"""
    path_manager._ensure_directories()


if __name__ == "__main__":
    # 测试路径管理器
    pm = PathManager()

    print("\n📂 目录结构:")
    for name, path in pm.dirs.items():
        print(f"  {name}: {path}")

    print("\n📄 文件路径:")
    for name, path in list(pm.files.items())[:5]:  # 只显示前5个
        print(f"  {name}: {path}")

    print("\n🔄 迁移映射:")
    for old, new in list(pm.legacy_mapping.items())[:3]:  # 只显示前3个
        print(f"  {os.path.basename(old)} → {os.path.basename(new)}")

    # 执行迁移
    # pm.migrate_to_new_structure()
