"""
经典双均线交叉策略 (SMA5 & SMA20)
逻辑：
- 5日均线上穿20日均线 (金叉) -> 买入
- 5日均线下穿20日均线 (死叉) -> 卖出（清仓）
"""
import pandas as pd
from .base import MultiStockStrategy


class SMA520Strategy(MultiStockStrategy):

    def __init__(self, cfg=None, symbols=None):
        super().__init__(symbols)
        # 策略参数
        self.fast_window = 5
        self.slow_window = 20

    def prepare(self, data: dict) -> dict:
        """
        [性能核心]：在回测引擎启动前，利用 Pandas 向量化计算所有股票的指标。
        绝对不要在每天的 on_bar 里去算均线！
        """
        self.init_data_state(data)  # 初始化基类指针

        for symbol, df in self.indicators.items():
            # 1. 计算均线
            df['SMA_Fast'] = df['close'].rolling(window=self.fast_window).mean()
            df['SMA_Slow'] = df['close'].rolling(window=self.slow_window).mean()

            # 2. 计算交叉信号 (金叉与死叉)
            # 昨天的 Fast <= Slow，且今天的 Fast > Slow，即为上穿
            df['is_golden_cross'] = (df['SMA_Fast'] > df['SMA_Slow']) & (
                        df['SMA_Fast'].shift(1) <= df['SMA_Slow'].shift(1))
            # 昨天的 Fast >= Slow，且今天的 Fast < Slow，即为下穿
            df['is_death_cross'] = (df['SMA_Fast'] < df['SMA_Slow']) & (
                        df['SMA_Fast'].shift(1) >= df['SMA_Slow'].shift(1))

            # 将 NaN 填充为 False
            df['is_golden_cross'] = df['is_golden_cross'].fillna(False)
            df['is_death_cross'] = df['is_death_cross'].fillna(False)

            self.indicators[symbol] = df

        return self.indicators

    def on_bar(self, bar: pd.Series, account, symbol: str):
        """
        引擎每一天都会调用一次这个方法
        :param bar: 引擎传过来的今天的原始 K 线（实际上我们不用它，用我们算好的 row）
        :param account: Portfolio 实例 (我们刚刚写好的会计管家)
        """
        # 极速获取包含了均线信号的这一天的数据
        row = self.get_current_row(symbol)
        if row is None:
            return None, 0

        action = None
        shares = 0
        price = row['close']

        # 获取当前持仓情况
        current_shares = account.get_shares(symbol)

        # === 核心逻辑 ===
        # 1. 卖出逻辑 (死叉且有持仓)
        if row['is_death_cross'] and current_shares > 0:
            action = "SELL"
            shares = current_shares  # 全仓卖出

        # 2. 买入逻辑 (金叉且当前未持有)
        elif row['is_golden_cross'] and current_shares == 0:
            # 召唤 Account 的风控计算器，看看手里的钱能买多少股
            available_slots = account.get_available_slots()
            if available_slots > 0:
                shares_to_buy = account.position_sizer.calculate_shares(account.cash, price, available_slots)
                if shares_to_buy > 0:
                    action = "BUY"
                    shares = shares_to_buy

        return action, shares