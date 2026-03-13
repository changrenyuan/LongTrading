"""
仓位管理模块
============
包含 PositionSizer（仓位计算器）和 Position（持仓对象）
"""
from typing import Optional
from datetime import datetime


class PositionSizer:
    """仓位计算器：负责计算合规的交易数量"""

    def __init__(self, max_positions: int = 3, position_pct: float = 0.33):
        self.max_positions = max_positions
        self.position_pct = position_pct

    def calculate_shares(self, cash: float, price: float, 
                         available_slots: Optional[int] = None) -> int:
        """
        计算可买入股数（A股规则：必须是 100 的整数倍）
        """
        if price <= 0 or cash <= 0:
            return 0

        if available_slots is None:
            allocation = cash * self.position_pct
        elif available_slots <= 0:
            return 0
        else:
            allocation = cash / available_slots

        # 扣除预估买入手续费(万三)，防止满仓买入时资金不足
        estimated_cash = allocation * (1 - 0.0003)
        # A股合规：向下取整到 100 的倍数
        shares = int(estimated_cash // (price * 100)) * 100
        return max(shares, 0)


class Position:
    """单一股票持仓管理（采用加权平均成本法 + 持仓时间追踪）"""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.shares: int = 0
        self.avg_price: float = 0.0
        self.first_buy_time: Optional[datetime] = None

    @property
    def cost(self) -> float:
        """持仓成本"""
        return self.shares * self.avg_price

    def add_shares(self, shares: int, price: float, current_time: str):
        """买入加仓逻辑"""
        if self.shares == 0:
            # 截取字符串前10位(YYYY-MM-DD)，安全转换为 datetime 对象
            try:
                self.first_buy_time = datetime.strptime(current_time[:10], "%Y-%m-%d")
            except ValueError:
                self.first_buy_time = datetime.now()

        total_value = (self.shares * self.avg_price) + (shares * price)
        self.shares += shares
        self.avg_price = total_value / self.shares

    def reduce_shares(self, shares: int):
        """卖出减仓逻辑"""
        if shares >= self.shares:
            self.shares = 0
            self.avg_price = 0.0
            self.first_buy_time = None
        else:
            self.shares -= shares
