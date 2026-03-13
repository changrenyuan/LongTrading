import csv
import logging
import os
from typing import Dict, List, Optional
import math
from datetime import datetime

logger = logging.getLogger("MT_Alpha")


class PositionSizer:
    """仓位计算器：负责计算合规的交易数量"""

    def __init__(self, max_positions: int = 3, position_pct: float = 0.33):
        self.max_positions = max_positions
        self.position_pct = position_pct

    def calculate_shares(self, cash: float, price: float, available_slots: Optional[int] = None) -> int:
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

        # 💡 优化：扣除预估的买入手续费 (假设万三)，防止满仓买入时资金不足
        estimated_cash = allocation * (1 - 0.0003)

        # 💡 A股合规：向下取整到 100 的倍数
        shares = int(estimated_cash // (price * 100)) * 100
        return max(shares, 0)


class RiskManager:
    """风险管理器：负责在下单前进行拦截"""

    def __init__(self, max_positions: int = 3, max_single_position_pct: float = 0.4):
        self.max_positions = max_positions
        self.max_single_position_pct = max_single_position_pct

    def allow_new_position(self, current_position_count: int, symbol: str, current_symbols: List[str]) -> bool:
        if symbol in current_symbols:
            return True  # 允许已有股票加仓
        return current_position_count < self.max_positions


class Position:
    """单一股票持仓管理（采用加权平均成本法 + 持仓时间追踪）"""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.shares: int = 0
        self.avg_price: float = 0.0
        self.first_buy_time: Optional[datetime] = None  # 💡 记录建仓时间

    @property
    def cost(self) -> float:
        return self.shares * self.avg_price

    def add_shares(self, shares: int, price: float, current_time: str):  # 💡 接收当前时间字符串
        """买入加仓逻辑"""
        if self.shares == 0:
            # 💡 截取字符串前10位(YYYY-MM-DD)，安全转换为 datetime 对象
            try:
                self.first_buy_time = datetime.strptime(current_time[:10], "%Y-%m-%d")
            except ValueError:
                self.first_buy_time = datetime.now() # 极端情况防错保底

        total_value = (self.shares * self.avg_price) + (shares * price)
        self.shares += shares
        self.avg_price = total_value / self.shares

    def reduce_shares(self, shares: int):
        """卖出减仓逻辑"""
        if shares >= self.shares:
            self.shares = 0
            self.avg_price = 0.0
            self.first_buy_time = None  # 清仓后重置时间
        else:
            self.shares -= shares

class Portfolio:
    """大管家：管理现金、所有持仓及交易流水"""

    def __init__(self, initial_cash: float, symbols: List[str], ledger_path: str = "data/trade_ledger.csv"):
        self.initial_cash = initial_cash
        self.central_vault = 0.0  # 中央资金池
        self.sub_budgets: Dict[str, float] = {}  # 各股独立预算
        self.positions: Dict[str, Position] = {}

        # self.position_sizer = PositionSizer(max_positions=max_positions)
        # self.risk_manager = RiskManager(max_positions=max_positions)

        max_pos = len(symbols) if symbols else 3
        self.risk_manager = RiskManager(max_positions=max_pos)

        self.total_commission = 0.0
        self.total_tax = 0.0
        self.trade_history: List[dict] = []

        self.ledger_path = ledger_path
        self.position_path = ledger_path.replace("ledger", "positions")
        self.position_id = 0

        self._init_ledger_file()
        self._record_deposit()  # 💡 新增：系统初始化时记录老板入金
        # 记录上一次审计时的总资产，用于对比盈亏
        per_stock_cash = initial_cash / len(symbols) if symbols else 0
        for sym in symbols:
            self.sub_budgets[sym] = per_stock_cash
        self.last_audit_equity: Dict[str, float] = {sym: per_stock_cash for sym in symbols}

    def _record_deposit(self):
        """💡 新增：在流水账第一行记录初始本金"""
        # timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 检查是否是空文件（只有表头），避免重复启动时重复记录入金
        with open(self.ledger_path, 'r', encoding='utf-8-sig') as f:
            if len(f.readlines()) <= 1:
                with open(self.ledger_path, mode='a', newline='', encoding='utf-8-sig') as out_f:
                    writer = csv.writer(out_f)
                    writer.writerow(
                        ['MoneyInit', 'ACCOUNT', 'DEPOSIT', '--', '--', self.initial_cash, 0.0, '--', '--', '--', '--',
                         self.initial_cash])

    # ==================== 查询接口 ====================

    def _init_ledger_file(self):
        """确保账本文件夹和文件存在，并写入表头"""
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)

        # 1. 流水表头（💡 增加了 hold_days 和 annualized_roi）
        if not os.path.exists(self.ledger_path) or os.path.getsize(self.ledger_path) == 0:
            with open(self.ledger_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'symbol', 'action', 'shares', 'price',
                                 'trade_value', 'fee', 'realized_pnl', 'trade_roi',
                                 'hold_days', 'annualized_roi', 'cash_balance'])

        # 2. 持仓底稿表头
        if not os.path.exists(self.position_path) or os.path.getsize(self.position_path) == 0:
            with open(self.position_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(
                    ['position_id', 'timestamp', 'item_type', 'symbol', 'shares', 'avg_price', 'cost_basis', 'ratio'])



    def get_available_slots(self) -> int:
        return max(0, self.risk_manager.max_positions - len(self.positions))

    # ==================== 查询接口 (静态账面纯净版) ====================

    def has_position(self, symbol: str) -> bool:
        """是否持有某股票"""
        return symbol in self.positions

    def get_position(self, symbol: str):
        """获取持仓对象 (Position)"""
        return self.positions.get(symbol)

    def get_shares(self, symbol: str) -> int:
        """获取持仓股数"""
        pos = self.positions.get(symbol)
        return pos.shares if pos else 0

    def get_avg_price(self, symbol: str) -> float:
        """获取持仓均价 (买入成本均价)"""
        pos = self.positions.get(symbol)
        return pos.avg_price if pos else 0.0

    def get_position_cost(self, symbol: str) -> float:
        """获取单只股票的账面总成本（买入时花掉的钱）"""
        pos = self.positions.get(symbol)
        return pos.cost if pos else 0.0

    def get_book_value(self) -> float:
        """
        💡 替代原来的 get_equity。
        获取账户【总账面价值】(剩余现金 + 所有持仓的买入总成本)。
        绝对不依赖最新市场价！
        """
        total_cost = sum(pos.cost for pos in self.positions.values())
        return self.total_cash + total_cost

    def get_position_count(self) -> int:
        """获取当前持仓股票的数量"""
        return len(self.positions)

    def get_available_slots(self) -> int:
        """获取可用仓位槽位"""
        return max(0, self.risk_manager.max_positions - len(self.positions))

    # ==================== 资金隔离查询接口 ====================
    def get_allocated_cash(self, symbol: str) -> float:
        """获取某只股票当前剩余的可用预算"""
        return self.sub_budgets.get(symbol, 0.0)

    def get_symbol_book_value(self, symbol: str) -> float:
        """获取某只股票目前的总账面资产 (剩余预算 + 买入成本)"""
        return self.get_allocated_cash(symbol) + self.get_position_cost(symbol)

    @property
    def total_cash(self) -> float:
        """所有剩余现金总和 (用于总资产计算)"""
        return self.central_vault + sum(self.sub_budgets.values())

    # ==================== T+20 滚动审计核心逻辑 ====================
    def audit_and_rebalance(self, current_prices: Dict[str, float], date_str: str):
        """每 20 天调用一次，执行奖惩机制"""
        logger.info(f"[{date_str}] 🏦 审计部启动 T+20 绩效清算与预算再分配...")

        for symbol in self.sub_budgets.keys():
            shares = self.get_shares(symbol)
            # 这里的 current_equity 是【奖惩调拨前】的权益
            current_equity = self.sub_budgets[symbol] + (shares * current_prices.get(symbol, 0))
            last_equity = self.last_audit_equity[symbol]

            # 表现不好 (亏损)：削减剩余预算的 20%
            if current_equity < last_equity:
                penalty = self.sub_budgets[symbol] * 0.20
                if penalty > 0:
                    self.sub_budgets[symbol] -= penalty
                    self.central_vault += penalty
                    logger.warning(f"  🔻 审计降级 [{symbol}]: 周期亏损，削减可用预算 {penalty:.2f} 元归入中央池")

            # 表现优异 (盈利)：奖励可用预算的 10%
            elif current_equity > last_equity:
                reward_request = self.sub_budgets[symbol] * 0.10
                # 前提是中央池有钱
                actual_reward = min(reward_request, self.central_vault)
                if actual_reward > 0:
                    self.central_vault -= actual_reward
                    self.sub_budgets[symbol] += actual_reward
                    logger.info(f"  🌟 审计奖励 [{symbol}]: 周期盈利，由中央池增拨预算 {actual_reward:.2f} 元")

            # 💡 致命 BUG 修复：基准线必须是【奖惩调拨后】的新权益！绝对不能用调拨前的！
            new_equity_after_rebalance = self.sub_budgets[symbol] + (shares * current_prices.get(symbol, 0))
            self.last_audit_equity[symbol] = new_equity_after_rebalance
    # ==================== 核心执行接口 ====================

    def execute_trade(self, symbol: str, action: str, shares: int, price: float,
                      commission_rate: float = 0.0003, stamp_tax_rate: float = 0.0005, current_time: str = "2023-06-12") -> dict:
        """
        统一的交易执行入口
        """
        result = {'success': False, 'symbol': symbol, 'action': action, 'message': ''}
        # 防御性编程：拦截非法动作
        if action not in ["BUY", "SELL"]:
            result['message'] = f"未知的交易动作: {action}"
            return result

        if shares <= 0 or price <= 0:
            result['message'] = "报单数量或价格必须大于 0"
            return result

        realized_pnl = 0.0  # 默认盈亏为 0
        trade_value = 0.0
        # 💡 新增三个指标变量
        trade_roi = 0.0
        hold_days = 0
        annualized_roi = 0.0

        if action == "BUY":
            # 1. 风控拦截
            if not self.risk_manager.allow_new_position(len(self.positions), symbol, list(self.positions.keys())):
                result['message'] = "触发风控：已达最大持仓限制"
                return result

            # 2. 规整 A 股报单要求 (强制100的整数倍)
            shares = (shares // 100) * 100
            if shares == 0:
                result['message'] = "资金或意向手数不足 1 手 (100股)"
                return result

            # 3. 算账
            trade_value = shares * price
            commission = max(5.0, trade_value * commission_rate)  # A股规矩：最低收费 5 元
            total_cost = trade_value + commission

            if total_cost > self.sub_budgets[symbol]:
                result['message'] = f"该股专属预算不足：需 {total_cost:.2f}，剩余 {self.sub_budgets[symbol]:.2f}"
                return result

            # 💡 4. 新增风控核心：审计部拦截 (单票仓位占比上限检查)
            current_pos_cost = self.get_position_cost(symbol)
            total_book_value = self.get_book_value()  # 获取总账面本金
            proposed_total_cost = current_pos_cost + total_cost  # 如果买入，这只股的总成本

            # max_single_position_pct 默认是 0.4 (单只股票不能超过总盘子的 40%)
            if proposed_total_cost > total_book_value * self.risk_manager.max_single_position_pct:
                result[
                    'message'] = f"风控拦截：买入后该股占比超限 ({proposed_total_cost / total_book_value * 100:.1f}% > 40%)"
                logger.warning(f"[{current_time}] ❌ 风控拦截 [{symbol}]: {result['message']}")
                return result

            # 4. 执行更新
            self.sub_budgets[symbol] -= total_cost
            self.total_commission += commission

            if symbol not in self.positions:
                self.positions[symbol] = Position(symbol)
            self.positions[symbol].add_shares(shares, price, current_time)

            # 💡 修复：加入了 'trade_value': trade_value
            result.update({'success': True, 'filled_shares': shares, 'trade_value': trade_value, 'fee': commission,
                           'message': "买入成功"})
        elif action == "SELL":
            if symbol not in self.positions or self.positions[symbol].shares == 0:
                result['message'] = "未持有该股票"
                return result

            pos = self.positions[symbol]
            sell_shares = min(shares, pos.shares)  # 防止超卖

            # 算账 (卖出需扣除印花税)
            trade_value = sell_shares * price
            commission = max(5.0, trade_value * commission_rate)
            tax = trade_value * stamp_tax_rate
            total_fee = commission + tax
            net_revenue = trade_value - total_fee

            # 💡 审计核心：计算这笔卖出的真实实现盈亏 (Realized PnL)
            cost_basis_of_sold = sell_shares * pos.avg_price
            realized_pnl = net_revenue - cost_basis_of_sold
            if cost_basis_of_sold > 0:
                trade_roi = realized_pnl / cost_basis_of_sold
                # 💡 计算持仓天数与年化 (安全转换当前时间)
                try:
                    current_dt = datetime.strptime(current_time[:10], "%Y-%m-%d")
                    delta_days = (current_dt - pos.first_buy_time).days
                    hold_days = max(1, delta_days)  # 防止当天买卖 (T+0) 除以零
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

            result.update({'success': True, 'filled_shares': sell_shares, 'trade_value': trade_value, 'fee': total_fee, 'message': "卖出成功"})
        # 💡 记录流水
        if result['success']:
            # 💡 把 hold_days 和 annualized_roi 传给流水记录
            self._record_trade(symbol, action, result['filled_shares'],
                               price, result['trade_value'], result['fee'],
                               realized_pnl, trade_roi, hold_days, annualized_roi, current_time)
            self._record_position(current_time)
            return result

    def _record_trade(self, symbol: str, action: str, shares: int, price: float, trade_value: float, fee: float,
                      realized_pnl: float, trade_roi: float, hold_days: int, annualized_roi: float, current_time: str):
        """记录每一次成功的交易，并直接追加到本地 CSV 文件中"""
        # timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        roi_str = f"{trade_roi * 100:.2f}%" if action == "SELL" else "--"
        days_str = f"{hold_days} 天" if action == "SELL" else "--"
        ann_roi_str = f"{annualized_roi * 100:.2f}%" if action == "SELL" else "--"
        # 1. 记入内存供本次运行快速查询
        trade_record = {
            'timestamp': current_time,
            'symbol': symbol,
            'action': action,
            'shares': shares,
            'price': price,
            'trade_value': trade_value,
            'fee': fee,
            'realized_pnl': realized_pnl,
            'trade_roi':roi_str,
            'hold_days': days_str,  # 💡 新增
            'annualized_roi': ann_roi_str,  # 💡 新增
            'balance': self.total_cash
        }
        self.trade_history.append(trade_record)

        # 2. 💡 立即追加写入本地硬盘，防断电丢失
        try:
            with open(self.ledger_path, mode='a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([current_time, symbol, action, shares, price,
                                 round(trade_value, 2), round(fee, 2), round(realized_pnl, 2),
                                 roi_str, days_str, ann_roi_str, round(self.total_cash, 2)])
        except Exception as e:
            logger.error(f"账本写入失败: {e}")

    def _record_position(self, current_time: str = "2023-06-12"):
        """💡 审计核心：记录当前仓位快照底稿（宏观资金面 + 微观个股）"""
        # timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamp = current_time
        try:
            with open(self.position_path, mode='a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['$+'])
                self.position_id += 1

                # 1. 宏观资金面 (以初始入金 self.initial_cash 为锚点计算所有 ratio)
                writer.writerow(
                    [self.position_id, timestamp, 'SUMMARY', 'INITIAL_FUNDS', '--', '--', self.initial_cash, '100.00%'])

                cash_ratio = (self.total_cash / self.initial_cash) * 100
                writer.writerow(
                    [self.position_id, timestamp, 'SUMMARY', 'CASH_BALANCE', '--', '--', round(self.total_cash, 2),
                     f"{cash_ratio:.2f}%"])

                # 2. 微观个股
                if not self.positions:
                    writer.writerow([self.position_id, timestamp, 'POSITION', 'EMPTY', 0, 0.0, 0.0, '0.00%'])
                else:
                    for symbol, pos in self.positions.items():
                        pos_ratio = (pos.cost / self.initial_cash) * 100
                        writer.writerow(
                            [self.position_id, timestamp, 'POSITION', symbol, pos.shares, round(pos.avg_price, 3),
                             round(pos.cost, 2), f"{pos_ratio:.2f}%"])

                writer.writerow(['=$'])
        except Exception as e:
            logger.error(f"仓位快照写入失败: {e}")