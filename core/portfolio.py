"""
组合管理模块
============
管理现金、所有持仓及交易流水的核心类
"""
import csv
import logging
import os
from typing import Dict, List, Optional

from .position import Position
from .risk_manager import RiskManager
from .trading_mixin import TradingMixin

logger = logging.getLogger("MT_Alpha")


class Portfolio(TradingMixin):
    """大管家：管理现金、所有持仓及交易流水"""

    def __init__(self, initial_cash: float, symbols: List[str],
                 ledger_path: str = "data/trade_ledger.csv"):
        self.initial_cash = initial_cash
        self.central_vault = 0.0
        self.sub_budgets: Dict[str, float] = {}
        self.positions: Dict[str, Position] = {}

        max_pos = len(symbols) if symbols else 3
        self.risk_manager = RiskManager(max_positions=max_pos)

        self.total_commission = 0.0
        self.total_tax = 0.0
        self.trade_history: List[dict] = []

        self.ledger_path = ledger_path
        self.position_path = ledger_path.replace("ledger", "positions")
        self.position_id = 0

        self._init_ledger_file()
        self._record_deposit()

        per_stock_cash = initial_cash / len(symbols) if symbols else 0
        for sym in symbols:
            self.sub_budgets[sym] = per_stock_cash
        self.last_audit_equity: Dict[str, float] = {sym: per_stock_cash for sym in symbols}

    # ==================== 初始化方法 ====================

    def _init_ledger_file(self):
        """确保账本文件存在并写入表头"""
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)

        if not os.path.exists(self.ledger_path) or os.path.getsize(self.ledger_path) == 0:
            with open(self.ledger_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'symbol', 'action', 'shares', 'price',
                                 'trade_value', 'fee', 'realized_pnl', 'trade_roi',
                                 'hold_days', 'annualized_roi', 'cash_balance'])

        if not os.path.exists(self.position_path) or os.path.getsize(self.position_path) == 0:
            with open(self.position_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['position_id', 'timestamp', 'item_type', 'symbol',
                                 'shares', 'avg_price', 'cost_basis', 'ratio'])

    def _record_deposit(self):
        """记录初始本金"""
        with open(self.ledger_path, 'r', encoding='utf-8-sig') as f:
            if len(f.readlines()) <= 1:
                with open(self.ledger_path, mode='a', newline='', encoding='utf-8-sig') as out_f:
                    writer = csv.writer(out_f)
                    writer.writerow(['MoneyInit', 'ACCOUNT', 'DEPOSIT', '--', '--',
                                     self.initial_cash, 0.0, '--', '--', '--', '--',
                                     self.initial_cash])

    # ==================== 查询接口 ====================

    @property
    def total_cash(self) -> float:
        """所有剩余现金总和"""
        return self.central_vault + sum(self.sub_budgets.values())

    def get_available_slots(self) -> int:
        """获取可用仓位槽位"""
        return max(0, self.risk_manager.max_positions - len(self.positions))

    def has_position(self, symbol: str) -> bool:
        return symbol in self.positions

    def get_position(self, symbol: str) -> Optional[Position]:
        return self.positions.get(symbol)

    def get_shares(self, symbol: str) -> int:
        pos = self.positions.get(symbol)
        return pos.shares if pos else 0

    def get_avg_price(self, symbol: str) -> float:
        pos = self.positions.get(symbol)
        return pos.avg_price if pos else 0.0

    def get_position_cost(self, symbol: str) -> float:
        pos = self.positions.get(symbol)
        return pos.cost if pos else 0.0

    def get_book_value(self) -> float:
        """获取账户总账面价值"""
        total_cost = sum(pos.cost for pos in self.positions.values())
        return self.total_cash + total_cost

    def get_position_count(self) -> int:
        return len(self.positions)

    def get_allocated_cash(self, symbol: str) -> float:
        return self.sub_budgets.get(symbol, 0.0)

    def get_symbol_book_value(self, symbol: str) -> float:
        return self.get_allocated_cash(symbol) + self.get_position_cost(symbol)

    # ==================== T+20 审计逻辑 ====================

    def audit_and_rebalance(self, current_prices: Dict[str, float], date_str: str):
        """每20天执行奖惩机制"""
        logger.info(f"[{date_str}] 🏦 审计部启动 T+20 绩效清算...")

        for symbol in self.sub_budgets.keys():
            shares = self.get_shares(symbol)
            current_equity = self.sub_budgets[symbol] + (shares * current_prices.get(symbol, 0))
            last_equity = self.last_audit_equity[symbol]

            if current_equity < last_equity:
                penalty = self.sub_budgets[symbol] * 0.20
                if penalty > 0:
                    self.sub_budgets[symbol] -= penalty
                    self.central_vault += penalty
                    logger.warning(f"  🔻 [{symbol}]: 削减预算 {penalty:.2f} 元")
            elif current_equity > last_equity:
                reward = min(self.sub_budgets[symbol] * 0.10, self.central_vault)
                if reward > 0:
                    self.central_vault -= reward
                    self.sub_budgets[symbol] += reward
                    logger.info(f"  🌟 [{symbol}]: 增拨预算 {reward:.2f} 元")

            new_equity = self.sub_budgets[symbol] + (shares * current_prices.get(symbol, 0))
            self.last_audit_equity[symbol] = new_equity
