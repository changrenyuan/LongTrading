"""
策略基类模块 - 专为多股票快速回测优化
"""
from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Union, Tuple, Optional


class BaseStrategy(ABC):
    """策略绝对基类"""

    @abstractmethod
    def prepare(self, data: Union[pd.DataFrame, Dict[str, pd.DataFrame]]) -> Union[
        pd.DataFrame, Dict[str, pd.DataFrame]]:
        """预处理数据：用于在回测开始前，利用 Pandas 向量化一次性计算好所有技术指标"""
        pass

    @abstractmethod
    def on_bar(self, bar: pd.Series, account, symbol: str) -> Tuple[Optional[str], int]:
        """
        每日K线切片调用
        返回格式: (action, shares) -> 比如 ("BUY", 200) 或者 (None, 0)
        """
        pass


class MultiStockStrategy(BaseStrategy):
    """
    多股票策略基类（性能优化版）
    核心优化：避免在 for 循环中使用极慢的 df.loc 查询，改用内部指针 (self.current_idx)
    """

    def __init__(self, symbols: list = None):
        self.symbols = symbols or []
        self.indicators: Dict[str, pd.DataFrame] = {}  # 存放计算好指标的数据
        self.current_idx: Dict[str, int] = {}  # 存放每只股票遍历到了第几行

    def init_data_state(self, data: Dict[str, pd.DataFrame]):
        """在 prepare 时调用，初始化每只股票的指针"""
        for symbol, df in data.items():
            if symbol not in self.symbols:
                self.symbols.append(symbol)
            self.indicators[symbol] = df.copy()
            self.current_idx[symbol] = 0

    def get_current_row(self, symbol: str) -> Optional[pd.Series]:
        """极速获取当前K线及指标数据，并自动推移指针"""
        if symbol not in self.indicators:
            return None

        idx = self.current_idx[symbol]
        df_len = len(self.indicators[symbol])

        if idx >= df_len:
            return None

        # 使用 .iloc 按位置极速提取，比按日期 .loc 提取快 10 倍以上
        row = self.indicators[symbol].iloc[idx]
        self.current_idx[symbol] += 1
        return row