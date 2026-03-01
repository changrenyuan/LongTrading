"""
趋势策略 v6.3 (全参数化/子基金隔离版)
1. 全参数化：消除所有魔法数字，为机器网格调参(Grid Search)做好完美铺垫。
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
    # ---------------- 资金与基础风控 ----------------
    'stop_loss_pct': 0.10,             # 硬止损警戒线 (亏损 10% 无条件走人)
    'trailing_stop_pct': 0.25,         # 基础移动止盈 (最高点回撤 25%)
    'unit_size': 0.25,                 # 每次加仓消耗【该股总预算】的占比
    'max_units': 4,                    # 最大建仓次数
    'lot_size': 100,                   # 交易手数乘数 (A股为100)
    'est_commission': 0.0003,          # 预估交易摩擦成本 (防止满仓算错钱)

    # ---------------- 分档动态止盈 ----------------
    'profit_tier1': 0.30,              # 利润达到 30% 时...
    'trailing_tier1': 0.15,            # ...回撤容忍度收紧至 15%
    'profit_tier2': 0.50,              # 利润达到 50% 时...
    'trailing_tier2': 0.10,            # ...回撤容忍度收紧至 10%
    'enable_partial_exit': True,       # 是否开启分批止盈
    'partial_exit_pct': 0.50,          # 触发止盈时先抛掉的仓位比例 (50%)
    'partial_exit_min_profit': 0.10,   # 触发分批止盈的最低浮盈要求 (10%)

    # ---------------- 技术指标周期 ----------------
    'ma_short': 5,                    # 短期均线周期
    'ma_mid': 20,                      # 中期均线周期 (核心生命线)
    'ma_long': 60,                     # 长期均线周期 (牛熊分界线)
    'vol_ma_window': 20,               # 成交量均线周期
    'macd_fast': 12,                   # MACD 快线周期
    'macd_slow': 26,                   # MACD 慢线周期
    'macd_signal': 9,                  # MACD 信号线周期

    # ---------------- 信号过滤与确认条件 ----------------
    'trend_ma_diff': 5,                # 判断长期均线向上的计算周期跨度
    'trend_strength_buffer': 1.05,     # 多头排列强度缓冲 (中期均线需 > 长期均线 * 1.02)
    'bias_entry_limit': 1.08,          # 首次建仓防追高限制 (收盘价 / 中期均线 < 1.08)
    'pullback_bias_limit': 1.05,       # 回踩加仓的最高偏离限制 (Bias < 1.05)
    'pullback_support_upper': 1.02,    # 回踩支撑区上限 (最低价 < 中期均线 * 1.02)
    'pullback_support_lower': 0.98,    # 回踩支撑区下限 (最低价 > 中期均线 * 0.98)
    'trend_broken_lower': 0.98,        # 破位止损确认线 (收盘价 < 中期均线 * 0.98)
    'trend_broken_vol': 1.2,           # 破位放量确认线 (成交量 > 均量 * 1.2)
    'add_pos_min_profit': 0.08,        # 💡 铁律：底仓必须浮盈 8% 以上才允许加仓！防逆势加仓。
    'breakout_window': 10,             # 💡 突破加仓：看过去10天的高点
    'breakout_vol_limit': 1.15,         # 💡 突破加仓：成交量必须是近期的 1.1 倍以上
}
# ==========================================

class InstitutionalTrendStrategy(MultiStockStrategy):
    def __init__(self, cfg=None, symbols=None):
        super().__init__(symbols=symbols)
        # 用传入的参数覆盖默认参数，便于外部调参
        self.cfg = {**STRATEGY_PARAMS, **(cfg or {})}
        self.pos_state = {}
        self.intended_signals = []

    def _record_intent(self, date_str, symbol, action, shares, reason):
        self.intended_signals.append({
            'date': date_str, 'symbol': symbol, 'action': action,
            'shares': shares, 'reason': reason
        })

    def _init_symbol_state(self, symbol):
        self.pos_state[symbol] = {'units_held': 0, 'peak_price': 0.0, 'partial_exited': False}

    def prepare(self, data: dict) -> dict:
        self.init_data_state(data)

        # 提取经常用到的参数，让代码更简洁
        cfg = self.cfg

        for symbol, df in self.indicators.items():
            self._init_symbol_state(symbol)
            df = df.copy()

            # 1. 均线系统
            df['MA_Short'] = df['close'].rolling(cfg['ma_short']).mean()
            df['MA_Mid'] = df['close'].rolling(cfg['ma_mid']).mean()
            df['MA_Long'] = df['close'].rolling(cfg['ma_long']).mean()

            # 2. MACD
            df['DIF'] = df['close'].ewm(span=cfg['macd_fast'], adjust=False).mean() - df['close'].ewm(span=cfg['macd_slow'], adjust=False).mean()
            df['DEA'] = df['DIF'].ewm(span=cfg['macd_signal'], adjust=False).mean()
            df['MACD'] = (df['DIF'] - df['DEA']) * 2

            # 3. 乖离率与趋势
            df['MA_Vol'] = df['volume'].rolling(cfg['vol_ma_window']).mean()
            df['Bias'] = df['close'] / df['MA_Mid']
            df['Strong_Trend'] = (df['MA_Mid'] > df['MA_Long'] * cfg['trend_strength_buffer']) & \
                                 (df['MA_Long'].diff(cfg['trend_ma_diff']) >= 0)

            # 4. 信号矩阵
            df['MA_Cross_Up'] = (df['MA_Short'] > df['MA_Mid']) & (df['MA_Short'].shift(1) <= df['MA_Mid'].shift(1))
            df['MACD_Bullish'] = (df['DIF'] > df['DEA']) & (df['DIF'] > 0)

            # 💡 1. 缩量回踩确认 (增加成交量萎缩的判断，防止放量暴跌时接飞刀)
            df['Pullback_Support'] = (df['low'] < df['MA_Mid'] * cfg['pullback_support_upper']) & \
                                     (df['low'] > df['MA_Mid'] * cfg['pullback_support_lower']) & \
                                     (df['close'] > df['open']) & \
                                     (df['close'] > df['MA_Mid']) & \
                                     (df['Bias'] < cfg['pullback_bias_limit']) & \
                                     (df['volume'] < df['MA_Vol'] * 1.2)  # 成交量不能爆天量
            # 💡 2. 强势突破确认 (空中加油：突破近 N 天最高价，且放量)
            df['Recent_High'] = df['high'].shift(1).rolling(cfg['breakout_window']).max()
            df['Breakout_Add'] = (df['close'] > df['Recent_High']) & \
                                 (df['volume'] > df['MA_Vol'] * cfg['breakout_vol_limit']) & \
                                 (df['Strong_Trend'])  # 必须在多头趋势下
            # 破位确认
            df['Trend_Broken'] = (df['close'] < df['MA_Mid'] * cfg['trend_broken_lower']) & \
                                 (df['volume'] > df['MA_Vol'] * cfg['trend_broken_vol'])
            # 填充缺失值
            df = df.ffill().bfill()
            bool_cols = ['Strong_Trend', 'MA_Cross_Up', 'MACD_Bullish', 'Pullback_Support', 'Trend_Broken', 'Breakout_Add']
            df[bool_cols] = df[bool_cols].fillna(False)
            self.indicators[symbol] = df

        return self.indicators

    def _calculate_shares_by_budget(self, account, symbol: str, price: float) -> int:
        if price <= 0: return 0
        cfg = self.cfg

        available_budget = account.get_allocated_cash(symbol)
        symbol_book_value = account.get_symbol_book_value(symbol)

        # 计划消费 = 账户总额 * 仓位配置比 * 扣除摩擦成本
        target_cash = symbol_book_value * cfg['unit_size'] * (1 - cfg['est_commission'])

        lot_value = price * cfg['lot_size']
        # 防饿死：如果配置的钱不够买一手，直接提额到一手
        if target_cash < lot_value:
            target_cash = lot_value

        # 确保消费不超过可用预算
        actual_spend = min(target_cash, available_budget * (1 - cfg['est_commission']))
        shares = int(actual_spend // lot_value) * cfg['lot_size']

        return max(shares, 0)

    def on_bar(self, bar, account, symbol: str):
        row = self.get_current_row(symbol)
        if row is None: return None, 0

        cfg = self.cfg
        price = row['close']
        date_str = bar.name.strftime("%Y-%m-%d") if hasattr(bar, 'name') else "UNKNOWN"
        current_shares = account.get_shares(symbol)
        state = self.pos_state[symbol]

        if current_shares == 0 and state['units_held'] > 0:
            self._init_symbol_state(symbol)
            state = self.pos_state[symbol]

        if current_shares > 0:
            state['peak_price'] = max(state['peak_price'], row['high'])

        avg_price = account.get_avg_price(symbol)

        # ================== A. 离场防守逻辑 ==================
        if current_shares > 0 and avg_price > 0:
            current_profit = (price / avg_price) - 1
            peak_price = state['peak_price']

            dynamic_trailing = cfg['trailing_stop_pct']
            if current_profit > cfg['profit_tier2']: dynamic_trailing = cfg['trailing_tier2']
            elif current_profit > cfg['profit_tier1']: dynamic_trailing = cfg['trailing_tier1']

            if peak_price > 0 and price < peak_price * (1 - dynamic_trailing):
                # 触发分批止盈
                if cfg['enable_partial_exit'] and not state['partial_exited'] and current_profit > cfg['partial_exit_min_profit']:
                    partial_shares = math.floor(current_shares * cfg['partial_exit_pct'] / cfg['lot_size']) * cfg['lot_size']
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

            if price < avg_price * (1 - cfg['stop_loss_pct']):
                reason = f"触及 {cfg['stop_loss_pct']*100:.0f}% 硬止损"
                self._record_intent(date_str, symbol, "SELL", current_shares, reason)
                return "SELL", current_shares

        # ================== B. 开仓与加仓逻辑 ==================
        if row['Strong_Trend']:
            if current_shares == 0:
                if row['Bias'] < cfg['bias_entry_limit'] and (row['MA_Cross_Up'] or (row['MA_Short'] > row['MA_Mid'] and row['MACD_Bullish'])):
                    shares = self._calculate_shares_by_budget(account, symbol, price)
                    if shares > 0:
                        state['units_held'] = 1
                        state['peak_price'] = price
                        reason = "顺势金叉确认，首次建仓"
                        self._record_intent(date_str, symbol, "BUY", shares, reason)
                        return "BUY", shares


            # 【立体加仓体系】：乘胜追击

            elif state['units_held'] < cfg['max_units']:
                # 💡 铁律一：盈利验证！只有现价高于成本价 2% 以上，才允许加仓！绝不逆势加死仓！
                if price > avg_price * (1 + cfg['add_pos_min_profit']):
                    # 进攻路线 A：缩量回踩生命线
                    if row['Pullback_Support']:
                        shares = self._calculate_shares_by_budget(account, symbol, price)
                        if shares > 0:
                            state['units_held'] += 1
                            reason = f"均线缩量回踩，执行第 {state['units_held']} 次加仓"
                            self._record_intent(date_str, symbol, "BUY", shares, reason)
                            return "BUY", shares
                    # 进攻路线 B：高位横盘后放量突破 (空中加油)
                    elif row['Breakout_Add']:
                        shares = self._calculate_shares_by_budget(account, symbol, price)
                        if shares > 0:
                            state['units_held'] += 1
                            reason = f"平台放量突破(空中加油)，执行第 {state['units_held']} 次追击加仓"
                            self._record_intent(date_str, symbol, "BUY", shares, reason)
                            return "BUY", shares
        return None, 0