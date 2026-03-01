"""
趋势策略 v6.2 (架构适配版)
特点：完全解耦财务计算，依赖底层 Account 提供精准均价与持仓，极速向量化预计算。
"""
import math
import pandas as pd
from .base import MultiStockStrategy
from utils.logger import global_logger as logger


class InstitutionalTrendStrategy(MultiStockStrategy):

    def __init__(self, cfg=None, symbols=None):
        super().__init__(symbols=symbols)
        self.cfg = cfg or {}

        # 风险参数
        self.stop_loss_pct = self.cfg.get('stop_loss_pct', 0.10)
        self.trailing_stop_pct = self.cfg.get('trailing_stop_pct', 0.20)
        self.max_units = self.cfg.get('max_units', 4)

        # 分档止盈参数 (利润越高，回撤容忍度越低)
        self.profit_tier1 = self.cfg.get('profit_tier1', 0.30)
        self.trailing_tier1 = self.cfg.get('trailing_tier1', 0.15)
        self.profit_tier2 = self.cfg.get('profit_tier2', 0.50)
        self.trailing_tier2 = self.cfg.get('trailing_tier2', 0.10)

        # 分批出场参数
        self.partial_exit_pct = self.cfg.get('partial_exit_pct', 0.5)
        self.enable_partial_exit = self.cfg.get('enable_partial_exit', True)

        # 策略专有状态追踪（峰值价格、加仓次数）
        self.pos_state = {}

    def _init_symbol_state(self, symbol):
        """初始化个股专有状态"""
        self.pos_state[symbol] = {
            'units_held': 0,
            'peak_price': 0.0,
            'partial_exited': False
        }

    def prepare(self, data: dict) -> dict:
        """向量化预计算全市场所有技术指标"""
        self.init_data_state(data)  # 初始化基类指针

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

    def on_bar(self, bar, account, symbol: str):
        """逐日推进，生成交易信号"""
        row = self.get_current_row(symbol)
        if row is None: return None, 0

        price = row['close']
        high = row['high']
        current_shares = account.get_shares(symbol)
        state = self.pos_state[symbol]

        # 💡 状态清理：如果管家显示空仓，彻底重置策略状态
        if current_shares == 0 and state['units_held'] > 0:
            self._init_symbol_state(symbol)

        # 💡 更新峰值价格 (用于移动止盈)
        if current_shares > 0:
            state['peak_price'] = max(state['peak_price'], high)

        avg_price = account.get_avg_price(symbol)  # 绝对精准的账面均价

        # ==========================================
        # A. 离场防守逻辑 (优先判定)
        # ==========================================
        if current_shares > 0 and avg_price > 0:
            current_profit = (price / avg_price) - 1
            peak_price = state['peak_price']

            # 1. 判定动态止盈档位
            dynamic_trailing = self.trailing_stop_pct
            if current_profit > self.profit_tier2:
                dynamic_trailing = self.trailing_tier2
            elif current_profit > self.profit_tier1:
                dynamic_trailing = self.trailing_tier1

            # 2. 触发移动止盈
            if peak_price > 0 and price < peak_price * (1 - dynamic_trailing):
                # 检查是否满足分批止盈条件
                if self.enable_partial_exit and not state['partial_exited'] and current_profit > 0.10:
                    partial_shares = math.floor(current_shares * self.partial_exit_pct / 100) * 100
                    if partial_shares > 0:
                        state['partial_exited'] = True
                        state['peak_price'] = price  # 重置最高价锚点
                        logger.info(f"[{symbol}] 💡 利润回撤达 {dynamic_trailing * 100:.0f}%, 触发半仓止盈")
                        return "SELL", partial_shares

                logger.info(f"[{symbol}] 💡 触发最终移动止盈，全仓撤退")
                return "SELL", current_shares

            # 3. 触发技术面破位
            if row['Trend_Broken']:
                logger.info(f"[{symbol}] 💡 跌破关键均线且放量，技术面破位清仓")
                return "SELL", current_shares

            # 4. 触及硬止损
            if price < avg_price * (1 - self.stop_loss_pct):
                logger.info(f"[{symbol}] 💡 触及 {self.stop_loss_pct * 100:.0f}% 硬止损警戒线，断臂求生")
                return "SELL", current_shares

        # ==========================================
        # B. 进攻开仓逻辑
        # ==========================================
        if row['Strong_Trend']:
            # 1. 首次建仓
            if current_shares == 0:
                bias_ok = row['Bias'] < 1.08
                if (row['MA10_Cross_Up'] or (row['MA10'] > row['MA20'] and row['MACD_Bullish'])) and bias_ok:
                    avail_slots = account.get_available_slots()
                    shares = account.position_sizer.calculate_shares(account.cash, price,
                                                                     avail_slots) if avail_slots > 0 else 0
                    if shares > 0:
                        state['units_held'] = 1
                        state['peak_price'] = price
                        logger.info(f"[{symbol}] 💡 顺势金叉确认，首次建仓")
                        return "BUY", shares

            # 2. 缩量回踩加仓
            elif state['units_held'] < self.max_units and row['Pullback_Support']:
                # 加仓无需判断槽位，按单份风险配置计算
                shares = account.position_sizer.calculate_shares(account.cash, price, available_slots=None)
                if shares > 0:
                    state['units_held'] += 1
                    logger.info(f"[{symbol}] 💡 均线强支撑确认，执行第 {state['units_held']} 次加仓")
                    return "BUY", shares

        return None, 0