"""
风险管理模块
============
负责在下单前进行风控拦截
"""
from typing import List


class RiskManager:
    """风险管理器：负责在下单前进行拦截"""

    def __init__(self, max_positions: int = 3, max_single_position_pct: float = 0.4):
        self.max_positions = max_positions
        self.max_single_position_pct = max_single_position_pct

    def allow_new_position(self, current_position_count: int, 
                           symbol: str, current_symbols: List[str]) -> bool:
        """
        检查是否允许开新仓位
        
        Args:
            current_position_count: 当前持仓数量
            symbol: 待交易的股票代码
            current_symbols: 当前已持仓的股票列表
        
        Returns:
            bool: 是否允许
        """
        if symbol in current_symbols:
            return True  # 允许已有股票加仓
        return current_position_count < self.max_positions

    def check_position_limit(self, proposed_cost: float, 
                              total_capital: float) -> bool:
        """
        检查单票仓位是否超限
        
        Args:
            proposed_cost: 建仓后的总成本
            total_capital: 总资金
        
        Returns:
            bool: 是否在限额内
        """
        if total_capital <= 0:
            return False
        return proposed_cost <= total_capital * self.max_single_position_pct
