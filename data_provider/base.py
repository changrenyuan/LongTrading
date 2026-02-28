from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional


class BaseDataProvider(ABC):
    """
    【数据源基类】
    定义了系统获取行情数据的标准接口（Blueprint）。
    所有具体的数据源实现（如 AkShare, CCXT, 本地CSV）都必须继承此类并实现以下方法。
    """

    @abstractmethod
    def get_data(self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取指定标的的历史 K 线数据。

        参数:
            symbol (str): 标的代码 (如 '000001', 'BTC/USDT')
            start_date (str, optional): 起始日期 (YYYY-MM-DD)
            end_date (str, optional): 结束日期 (YYYY-MM-DD)

        返回:
            pd.DataFrame: 必须包含 ['open', 'high', 'low', 'close', 'volume'] 列，且 index 为 datetime。
        """
        pass
