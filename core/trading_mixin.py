"""
交易执行混入模块
================
提供 Portfolio 的交易执行方法
"""
import csv
import logging
from datetime import datetime
from typing import Dict, Tuple

from .position import Position

logger = logging.getLogger("MT_Alpha")


class TradingMixin:
    """
    交易执行混入类
    为 Portfolio 提供交易执行、记录等方法
    """

    # 这些属性由 Portfolio 提供，这里声明类型供类型检查使用
    positions: Dict[str, Position]
    sub_budgets: Dict[str, float]
    risk_manager: any
    total_commission: float
    total_tax: float
    trade_history: list
    ledger_path: str
    position_path: str
    position_id: int
    initial_cash: float

    def get_position_cost(self, symbol: str) -> float:
        """由 Portfolio 提供"""
        pass

    def get_book_value(self) -> float:
        """由 Portfolio 提供"""
        pass

    @property
    def total_cash(self) -> float:
        """由 Portfolio 提供"""
        return 0.0

    # ==================== 交易执行接口 ====================

    def execute_trade(self, symbol: str, action: str, shares: int, price: float,
                      commission_rate: float = 0.0003, stamp_tax_rate: float = 0.0005,
                      current_time: str = "2023-06-12") -> dict:
        """统一的交易执行入口"""
        result = {'success': False, 'symbol': symbol, 'action': action, 'message': ''}

        if action not in ["BUY", "SELL"]:
            result['message'] = f"未知的交易动作: {action}"
            return result

        if shares <= 0 or price <= 0:
            result['message'] = "报单数量或价格必须大于 0"
            return result

        realized_pnl = 0.0
        trade_roi = 0.0
        hold_days = 0
        annualized_roi = 0.0

        if action == "BUY":
            result = self._execute_buy(symbol, shares, price, commission_rate, current_time)
        elif action == "SELL":
            result, realized_pnl, trade_roi, hold_days, annualized_roi = \
                self._execute_sell(symbol, shares, price, commission_rate, stamp_tax_rate, current_time)

        # 记录流水
        if result['success']:
            self._record_trade(symbol, action, result['filled_shares'], price,
                               result['trade_value'], result['fee'],
                               realized_pnl, trade_roi, hold_days, annualized_roi, current_time)
            self._record_position(current_time)

        return result

    def _execute_buy(self, symbol: str, shares: int, price: float,
                     commission_rate: float, current_time: str) -> dict:
        """执行买入"""
        result = {'success': False, 'symbol': symbol, 'action': 'BUY', 'message': ''}

        # 风控拦截
        if not self.risk_manager.allow_new_position(len(self.positions), symbol, list(self.positions.keys())):
            result['message'] = "触发风控：已达最大持仓限制"
            return result

        # 规整A股报单要求(100的整数倍)
        shares = (shares // 100) * 100
        if shares == 0:
            result['message'] = "资金或意向手数不足 1 手 (100股)"
            return result

        # 算账
        trade_value = shares * price
        commission = max(5.0, trade_value * commission_rate)
        total_cost = trade_value + commission

        if total_cost > self.sub_budgets[symbol]:
            result['message'] = f"预算不足：需 {total_cost:.2f}，剩余 {self.sub_budgets[symbol]:.2f}"
            return result

        # 单票仓位上限检查
        current_pos_cost = self.get_position_cost(symbol)
        total_book_value = self.get_book_value()
        proposed_total_cost = current_pos_cost + total_cost

        if not self.risk_manager.check_position_limit(proposed_total_cost, total_book_value):
            result['message'] = f"风控拦截：占比超限 ({proposed_total_cost/total_book_value*100:.1f}% > 40%)"
            logger.warning(f"[{current_time}] ❌ 风控拦截 [{symbol}]: {result['message']}")
            return result

        # 执行更新
        self.sub_budgets[symbol] -= total_cost
        self.total_commission += commission

        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol)
        self.positions[symbol].add_shares(shares, price, current_time)

        result.update({'success': True, 'filled_shares': shares, 'trade_value': trade_value,
                       'fee': commission, 'message': "买入成功"})
        return result

    def _execute_sell(self, symbol: str, shares: int, price: float,
                      commission_rate: float, stamp_tax_rate: float,
                      current_time: str) -> Tuple[dict, float, float, int, float]:
        """执行卖出"""
        result = {'success': False, 'symbol': symbol, 'action': 'SELL', 'message': ''}
        realized_pnl = 0.0
        trade_roi = 0.0
        hold_days = 0
        annualized_roi = 0.0

        if symbol not in self.positions or self.positions[symbol].shares == 0:
            result['message'] = "未持有该股票"
            return result, realized_pnl, trade_roi, hold_days, annualized_roi

        pos = self.positions[symbol]
        sell_shares = min(shares, pos.shares)

        # 算账
        trade_value = sell_shares * price
        commission = max(5.0, trade_value * commission_rate)
        tax = trade_value * stamp_tax_rate
        total_fee = commission + tax
        net_revenue = trade_value - total_fee

        # 计算盈亏
        cost_basis = sell_shares * pos.avg_price
        realized_pnl = net_revenue - cost_basis

        if cost_basis > 0:
            trade_roi = realized_pnl / cost_basis
            try:
                current_dt = datetime.strptime(current_time[:10], "%Y-%m-%d")
                delta_days = (current_dt - pos.first_buy_time).days
                hold_days = max(1, delta_days)
            except:
                hold_days = 1
            annualized_roi = (trade_roi / hold_days) * 365

        # 执行更新
        self.sub_budgets[symbol] += net_revenue
        self.total_commission += commission
        self.total_tax += tax

        pos.reduce_shares(sell_shares)
        if pos.shares == 0:
            del self.positions[symbol]

        result.update({'success': True, 'filled_shares': sell_shares, 'trade_value': trade_value,
                       'fee': total_fee, 'message': "卖出成功"})
        return result, realized_pnl, trade_roi, hold_days, annualized_roi

    # ==================== 记录方法 ====================

    def _record_trade(self, symbol: str, action: str, shares: int, price: float,
                      trade_value: float, fee: float, realized_pnl: float,
                      trade_roi: float, hold_days: int, annualized_roi: float,
                      current_time: str):
        """记录交易到CSV"""
        roi_str = f"{trade_roi * 100:.2f}%" if action == "SELL" else "--"
        days_str = f"{hold_days} 天" if action == "SELL" else "--"
        ann_roi_str = f"{annualized_roi * 100:.2f}%" if action == "SELL" else "--"

        self.trade_history.append({
            'timestamp': current_time, 'symbol': symbol, 'action': action,
            'shares': shares, 'price': price, 'trade_value': trade_value,
            'fee': fee, 'realized_pnl': realized_pnl, 'trade_roi': roi_str,
            'hold_days': days_str, 'annualized_roi': ann_roi_str,
            'balance': self.total_cash
        })

        try:
            with open(self.ledger_path, mode='a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([current_time, symbol, action, shares, price,
                                 round(trade_value, 2), round(fee, 2), round(realized_pnl, 2),
                                 roi_str, days_str, ann_roi_str, round(self.total_cash, 2)])
        except Exception as e:
            logger.error(f"账本写入失败: {e}")

    def _record_position(self, current_time: str = "2023-06-12"):
        """记录仓位快照"""
        try:
            with open(self.position_path, mode='a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['$+'])
                self.position_id += 1

                writer.writerow([self.position_id, current_time, 'SUMMARY', 'INITIAL_FUNDS',
                                 '--', '--', self.initial_cash, '100.00%'])

                cash_ratio = (self.total_cash / self.initial_cash) * 100
                writer.writerow([self.position_id, current_time, 'SUMMARY', 'CASH_BALANCE',
                                 '--', '--', round(self.total_cash, 2), f"{cash_ratio:.2f}%"])

                if not self.positions:
                    writer.writerow([self.position_id, current_time, 'POSITION', 'EMPTY',
                                     0, 0.0, 0.0, '0.00%'])
                else:
                    for sym, pos in self.positions.items():
                        pos_ratio = (pos.cost / self.initial_cash) * 100
                        writer.writerow([self.position_id, current_time, 'POSITION', sym,
                                         pos.shares, round(pos.avg_price, 3),
                                         round(pos.cost, 2), f"{pos_ratio:.2f}%"])

                writer.writerow(['=$'])
        except Exception as e:
            logger.error(f"仓位快照写入失败: {e}")
