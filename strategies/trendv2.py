"""
趋势策略 v6.3 (子基金/预算隔离版)
1. 参数集中化：文件头部清晰列出所有超参，方便后续大规模调参。
2. 资金隔离：无法获取总资金，只能获取单票分配预算。
3. 意向日记本：记录所有应发信号，供审计部收盘后对账。
"""
import math
import pandas as pd
from .base import MultiStockStrategy
from utils.logger import global_logger as logger

# ==========================================
# 🎛️ 策略超级参数控制台 (Grid Search Parameters)
# ==========================================
STRATEGY_PARAMS = {
    'stop_loss_pct': 0.10,          # 硬止损警戒线
    'trailing_stop_pct': 0.25,      # 基础移动止盈
    'unit_size': 0.25,              # 每次加仓消耗【该股总预算】的占比
    'max_units': 4,                 # 最大建仓次数
    'profit_tier1': 0.30,           # 利润分档1
    'trailing_tier1': 0.15,         # 止盈回撤1
    'profit_tier2': 0.50,           # 利润分档2
    'trailing_tier2': 0.10,         # 止盈回撤2
    'enable_partial_exit': True,
    'partial_exit_pct': 0.50,
}
# ==========================================

class InstitutionalTrendStrategy(MultiStockStrategy):
    def __init__(self, cfg=None, symbols=None):
        super().__init__(symbols=symbols)
        self.cfg = {**STRATEGY_PARAMS, **(cfg or {})}
        self.pos_state = {}
        # 💡 审计专用：策略的“意向日记本”
        self.intended_signals = []

    def _record_intent(self, date_str, symbol, action, shares, reason):
        """记录策略发出的意向信号，供盘后审计"""
        self.intended_signals.append({
            'date': date_str, 'symbol': symbol, 'action': action,
            'shares': shares, 'reason': reason
        })

    def _init_symbol_state(self, symbol):
        self.pos_state[symbol] = {'units_held': 0, 'peak_price': 0.0, 'partial_exited': False}

    def prepare(self, data: dict) -> dict:
        """💡 修复：完整的指标计算逻辑，绝不能用 pass 替代！"""
        self.init_data_state(data)

        for symbol, df in self.indicators.items():
            self._init_symbol_state(symbol)
            df = df.copy()

            # 1. 均线系统
            df['MA10'] = df['close'].rolling(10).mean()
            df['MA20'] = df['close'].rolling(20).mean()
            df['MA60'] = df['close'].rolling(60).mean()

            # 2. MACD
            df['DIF'] = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
            df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
            df['MACD'] = (df['DIF'] - df['DEA']) * 2

            # 3. 乖离率与趋势
            df['MA_Vol'] = df['volume'].rolling(20).mean()
            df['Bias'] = df['close'] / df['MA20']
            df['Strong_Trend'] = (df['MA20'] > df['MA60'] * 1.02) & (df['MA60'].diff(3) >= 0)

            # 4. 信号矩阵
            df['MA10_Cross_Up'] = (df['MA10'] > df['MA20']) & (df['MA10'].shift(1) <= df['MA20'].shift(1))
            df['MACD_Bullish'] = (df['DIF'] > df['DEA']) & (df['DIF'] > 0)
            df['Pullback_Support'] = (df['low'] < df['MA20'] * 1.02) & (df['low'] > df['MA20'] * 0.98) & \
                                     (df['close'] > df['open']) & (df['close'] > df['MA20']) & (df['Bias'] < 1.05)
            df['Trend_Broken'] = (df['close'] < df['MA20'] * 0.98) & (df['volume'] > df['MA_Vol'] * 1.2)

            # 填充缺失值
            df = df.ffill().bfill()
            bool_cols = ['Strong_Trend', 'MA10_Cross_Up', 'MACD_Bullish', 'Pullback_Support', 'Trend_Broken']
            df[bool_cols] = df[bool_cols].fillna(False)

            self.indicators[symbol] = df

        return self.indicators

    def _calculate_shares_by_budget(self, account, symbol: str, price: float) -> int:
        """💡 核心资金隔离升级：只能向会计请求该股的独立预算"""
        if price <= 0: return 0

        available_budget = account.get_allocated_cash(symbol)
        symbol_book_value = account.get_symbol_book_value(symbol)

        # 每次计划动用该股总资产的 unit_size (25%)
        target_cash = symbol_book_value * self.cfg['unit_size'] * (1 - 0.0003)
        actual_spend = min(target_cash, available_budget * (1 - 0.0003))

        shares = int(actual_spend // (price * 100)) * 100
        return max(shares, 0)

    def on_bar(self, bar, account, symbol: str):
        row = self.get_current_row(symbol)
        if row is None: return None, 0

        price = row['close']
        date_str = bar.name.strftime("%Y-%m-%d") if hasattr(bar, 'name') else "UNKNOWN"
        current_shares = account.get_shares(symbol)
        state = self.pos_state[symbol]

        if current_shares == 0 and state['units_held'] > 0:
            self._init_symbol_state(symbol)

        if current_shares > 0:
            state['peak_price'] = max(state['peak_price'], row['high'])

        avg_price = account.get_avg_price(symbol)

        # ================== A. 离场逻辑 ==================
        if current_shares > 0 and avg_price > 0:
            current_profit = (price / avg_price) - 1
            peak_price = state['peak_price']

            dynamic_trailing = self.cfg['trailing_stop_pct']
            if current_profit > self.cfg['profit_tier2']: dynamic_trailing = self.cfg['trailing_tier2']
            elif current_profit > self.cfg['profit_tier1']: dynamic_trailing = self.cfg['trailing_tier1']

            if peak_price > 0 and price < peak_price * (1 - dynamic_trailing):
                if self.cfg['enable_partial_exit'] and not state['partial_exited'] and current_profit > 0.10:
                    partial_shares = math.floor(current_shares * self.cfg['partial_exit_pct'] / 100) * 100
                    if partial_shares > 0:
                        state['partial_exited'] = True
                        state['peak_price'] = price
                        reason = f"利润回撤达 {dynamic_trailing*100:.0f}%, 半仓止盈"
                        self._record_intent(date_str, symbol, "SELL", partial_shares, reason)
                        return "SELL", partial_shares

                reason = "触发最终移动止盈，全仓撤退"
                self._record_intent(date_str, symbol, "SELL", current_shares, reason)
                return "SELL", current_shares

            if row['Trend_Broken']:
                reason = "技术面破位清仓"
                self._record_intent(date_str, symbol, "SELL", current_shares, reason)
                return "SELL", current_shares

            if price < avg_price * (1 - self.cfg['stop_loss_pct']):
                reason = f"触及 {self.cfg['stop_loss_pct']*100:.0f}% 硬止损"
                self._record_intent(date_str, symbol, "SELL", current_shares, reason)
                return "SELL", current_shares

        # ================== B. 开仓与加仓逻辑 ==================
        if row['Strong_Trend']:
            if current_shares == 0:
                if row['Bias'] < 1.15 and (row['MA10_Cross_Up'] or (row['MA10'] > row['MA20'] and row['MACD_Bullish'])):
                    shares = self._calculate_shares_by_budget(account, symbol, price)
                    if shares > 0:
                        state['units_held'] = 1
                        state['peak_price'] = price
                        reason = "顺势金叉确认，首次建仓"
                        self._record_intent(date_str, symbol, "BUY", shares, reason)
                        return "BUY", shares

            elif state['units_held'] < self.cfg['max_units'] and row['Pullback_Support']:
                shares = self._calculate_shares_by_budget(account, symbol, price)
                if shares > 0:
                    state['units_held'] += 1
                    reason = f"均线强支撑确认，执行第 {state['units_held']} 次加仓"
                    self._record_intent(date_str, symbol, "BUY", shares, reason)
                    return "BUY", shares

        return None, 0