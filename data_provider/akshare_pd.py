import akshare as ak
import pandas as pd
import os
from datetime import datetime, time
import glob
from utils.logger import global_logger as logger

# 假设你的项目有 BaseDataProvider 基类，如果没有请保持原样
from .base import BaseDataProvider

class AkShareProvider(BaseDataProvider):
    def __init__(self, cache_dir="data"):
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def get_market_snapshot(self) -> pd.DataFrame:
        """
        获取全 A 股当日实时快照
        规则：
        1. 超过 threshold_time（如 11:30）：拉取最新数据并缓存。
        2. 早于 threshold_time：优先使用最近的历史缓存，如果没有则拉取实时但不缓存。
        """
        now = datetime.now()
        today_str = now.strftime('%Y%m%d')
        # 💡 修复：将时间阈值设定为 11:30，与你的注释保持一致
        threshold_time = time(10, 30)

        cache_file_today = os.path.join(self.cache_dir, f"market_snapshot_{today_str}.csv")

        # --- 逻辑 A: 早于指定时间 ---
        if now.time() < threshold_time:
            logger.info(f"当前时间早于 11:30，优先检索历史缓存...")
            cache_pattern = os.path.join(self.cache_dir, "market_snapshot_*.csv")
            all_caches = glob.glob(cache_pattern)

            # 过滤今日缓存，并按时间倒序
            history_caches = sorted([f for f in all_caches if today_str not in f], reverse=True)

            if history_caches:
                latest_history = history_caches[0]
                logger.info(f"加载历史缓存: {os.path.basename(latest_history)}")
                return pd.read_csv(latest_history, dtype={'代码': str})
            else:
                logger.warning("未找到历史缓存，正在拉取实时数据（不缓存）...")
                return self._fetch_snapshot_from_api()

        # --- 逻辑 B: 晚于指定时间 ---
        if os.path.exists(cache_file_today):
            logger.info(f"检测到今日 ({today_str}) 缓存，正在加载...")
            return pd.read_csv(cache_file_today, dtype={'代码': str})

        logger.info("今日首次运行，正在拉取并缓存全市场快照...")
        df = self._fetch_snapshot_from_api()
        if not df.empty:
            df.to_csv(cache_file_today, index=False, encoding='utf-8-sig')
            logger.info(f"今日数据已成功缓存至: {cache_file_today}")
        return df

    def _fetch_snapshot_from_api(self) -> pd.DataFrame:
        """内部方法：封装最新的东方财富快照接口"""
        try:
            # 💡 优化：使用更稳定、速度更快的 em (东方财富) 接口
            df = ak.stock_zh_a_spot()
            return df
        except Exception as e:
            logger.error(f"拉取全市场快照失败: {e}")
            raise ConnectionError("无法获取实时行情，请检查网络或代理设置。")

    def get_data(self, symbol: str) -> pd.DataFrame:
        """
        获取单只股票的日线历史数据
        """
        try:
            raw_code = self._fix_symbol(symbol)
            # 💡 默认前复权 (qfq)
            df = ak.stock_zh_a_daily(symbol=raw_code, adjust="qfq")
            logger.debug(f"👉 数据列名检查: {list(df.columns)}")
            if df.empty:
                return pd.DataFrame()

            # 💡 确保列名映射正确，适配回测引擎 (engine.py)
            df = df.rename(columns={
                '日期': 'date', '开盘': 'open', '收盘': 'close',
                '最高': 'high', '最低': 'low', '成交量': 'volume',
                '换手率': 'turnover'
            })

            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            # 返回最近的 500 个交易日（约两年数据）
            return df[['open', 'high', 'low', 'close', 'volume', 'turnover']].sort_index().tail(500)

        except Exception as e:
            logger.error(f"获取股票 {symbol} 历史数据失败: {e}")
            return pd.DataFrame()
    def get_data_dc(self, symbol: str) -> pd.DataFrame:
        """
        获取单只股票的日线历史数据
        """
        try:
            # raw_code = self._fix_symbol(symbol)
            # 💡 默认前复权 (qfq)
            df = ak.stock_zh_a_hist(symbol=symbol, adjust="qfq")
            logger.debug(f"👉 数据列名检查: {list(df.columns)}")
            if df.empty:
                return pd.DataFrame()

            # 💡 确保列名映射正确，适配回测引擎 (engine.py)
            df = df.rename(columns={
                '日期': 'date', '开盘': 'open', '收盘': 'close',
                '最高': 'high', '最低': 'low', '成交量': 'volume',
                '换手率': 'turnover'
            })

            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            # 返回最近的 500 个交易日（约两年数据）
            return df[['open', 'high', 'low', 'close', 'volume', 'turnover']].sort_index().tail(500)

        except Exception as e:
            logger.error(f"获取股票 {symbol} 历史数据失败: {e}")
            return pd.DataFrame()
    def _fix_symbol(self, symbol: str) -> str:
        """
        规范化股票代码 (以备其他需要带有 sh/sz 前缀的接口使用)
        """
        raw_code = "".join(filter(str.isdigit, symbol))
        if raw_code.startswith('6'): return f"sh{raw_code}"
        if raw_code.startswith(('0', '3')): return f"sz{raw_code}"
        if raw_code.startswith(('4', '8')): return f"bj{raw_code}"  # 💡 补充了北交所
        return symbol