# coding=utf-8
from __future__ import print_function, absolute_import, unicode_literals
from gm.api import *
import os
import datetime
import pandas as pd

# ===================== 【核心配置】 =====================
SIGNAL_FILE = 'trade_signals.csv'
MAX_POSITION_COUNT = 2          # 最大持仓数
MAX_SINGLE_WEIGHT = 1          # 单只股票最大仓位
STOP_LOSS_RATIO = 0.07           # 固定止损 7%
TRAILING_STOP_RATIO = 0.15       # 移动止盈回撤 5%
ACTIVATION_RATIO = 1          # 移动止盈激活阈值 15%
COOL_DOWN_DAYS = 7              # 风控冷静期（天）
# ===================== 初始化 =====================
def init(context):
    # 新增：移动止盈所需变量
    context.highest_prices = {}    # 记录持仓最高价
    context.last_sell_date = {}     # 记录每个标的最后卖出日期

    if not os.path.exists(SIGNAL_FILE):
        print(f"❌ 找不到信号文件 {SIGNAL_FILE}")
        return
    
    df = pd.read_csv(SIGNAL_FILE)
    
    def format_symbol(sym):
        sym = str(sym).zfill(6)
        return f"SHSE.{sym}" if sym.startswith(('6','5')) else f"SZSE.{sym}"
    
    df['symbol'] = df['symbol'].apply(format_symbol)
    context.signal_dict = {}
    for date, group in df.groupby('date'):
        context.signal_dict[date] = group.set_index('symbol')['signal'].to_dict()
    
    print(f"✅ 信号加载完成：{len(context.signal_dict)} 个交易日")
    print(f"✅ 已启用：移动止盈 + {COOL_DOWN_DAYS}天冷静期风控")
    # 每天 09:31 运行核心逻辑
    schedule(schedule_func=algo, date_rule='1d', time_rule='09:31:00')

# ===================== 【核心：每日交易 + 风控】 =====================
def algo(context):
    today_dt = context.now
    today = today_dt.strftime('%Y-%m-%d')
    today_signals = context.signal_dict.get(today, {})
    
    # 1. 获取当前真实持仓
    positions = context.account().positions()
    current_syms = [p.symbol for p in positions if p.volume > 0]
    just_sold_today = []  # 今日已卖出标的，防止重复操作

    # === 2. 移动止盈 + 固定止损 ===
    for pos in positions:
        if pos.volume == 0:
            continue
        sym = pos.symbol
        cost_price = pos.vwap
        
        try:
            df = history_n(
                symbol=sym, 
                frequency='1d', 
                count=1, 
                end_time=context.now,
                fields='close,high', 
                adjust=ADJUST_PREV,
                df=True
            )
            
            if df is not None and not df.empty:
                curr_close = df['close'].iloc[-1]
                curr_high = df['high'].iloc[-1]

                # 更新持仓最高价（移动止盈核心）
                context.highest_prices[sym] = max(context.highest_prices.get(sym, 0), curr_high)
                highest = context.highest_prices[sym]
                
                pnl_ratio = (curr_close - cost_price) / cost_price
                drawdown = (highest - curr_close) / highest 

                reason = ""
                # 固定止损
                if pnl_ratio <= -STOP_LOSS_RATIO:
                    reason = f"固定止损({pnl_ratio:.1%})"
                # 移动止盈：盈利达标后回撤触发
                elif pnl_ratio >= ACTIVATION_RATIO and drawdown >= TRAILING_STOP_RATIO:
                    reason = f"移动止盈(回撤{drawdown:.1%})"

                if reason:
                    print(f"🚨 {reason} 触发卖出: {sym}")
                    order_target_percent(
                        symbol=sym, percent=0,
                        order_type=OrderType_Market, position_side=PositionSide_Long
                    )
                    just_sold_today.append(sym)
                    context.last_sell_date[sym] = today_dt  # 记录卖出时间，开启冷静期

        except Exception as e:
            print(f"⚠️ 止盈止损计算异常 {sym}: {e}")

    # === 3. 信号卖出（-1） ===
    if today_signals:
        signal_sells = [s for s, sig in today_signals.items() if sig == -1]
        for sym in signal_sells:
            if sym in current_syms and sym not in just_sold_today:
                order_target_percent(
                    symbol=sym, percent=0,
                    order_type=OrderType_Market, position_side=PositionSide_Long
                )
                print(f"策略退出交易指令📤 {today} 信号卖出 {sym}")
                just_sold_today.append(sym)
                # 卖出记录冷静期
                context.last_sell_date[sym] = today_dt

    # 剩余有效持仓
    remaining_syms = [s for s in current_syms if s not in just_sold_today]

    # === 4. 买入逻辑 + 冷静期校验 ===
    if today_signals:
        buy_candidates = []
        for sym, sig in today_signals.items():
            if sig != 1:
                continue
            # 已持仓 / 今日刚卖 → 不买
            if sym in remaining_syms or sym in just_sold_today:
                continue
            
            # ✅ 冷静期判断：卖出后必须满 N 天才能再次买入
            if sym in context.last_sell_date:
                days_passed = (today_dt - context.last_sell_date[sym]).days
                if days_passed < COOL_DOWN_DAYS:
                    continue  # 冷静期内，跳过
            
            buy_candidates.append(sym)

        # 仓位控制
        available_positions = MAX_POSITION_COUNT - len(remaining_syms)
        if available_positions > 0 and buy_candidates:
            buy_list = buy_candidates[:available_positions]
            
            for sym in buy_list:
                order_target_percent(
                    symbol=sym, percent=MAX_SINGLE_WEIGHT,
                    order_type=OrderType_Market, position_side=PositionSide_Long
                )
                print(f"策略介入交易指令📥 {today} 买入 {sym} | 冷静期已通过")
                # 买入重置最高价追踪
                context.highest_prices[sym] = 0

# ===================== 订单回调 =====================
def on_order_status(context, order):
    symbol = order['symbol']
    price = order['price']
    volume = order['volume']
    status = order['status']
    side = order['side']
    effect = order['position_effect']
    order_type = order['order_type']
    
    if status == 3:
        if effect == 1:
            side_effect = '开多仓' if side == 1 else '开空仓'
        else:
            side_effect = '平空仓' if side == 1 else '平多仓'
        order_type_word = '限价' if order_type == 1 else '市价'
        print('成交信息{}:标的：{}，操作：以{}{}，委托价格：{}，委托数量：{}'
              .format(context.now, symbol, order_type_word, side_effect, price, volume))
       
# ===================== 回测完成 =====================
def on_backtest_finished(context, indicator):
    print('='*60)
    print('🎯 回测完成 - AI因子多因子策略（已加移动止盈+冷静期）')
    print(f"收益率: {indicator['pnl_ratio']:.2%}")
    print(f"最大回撤: {indicator['max_drawdown']:.2%}")
    print(f"夏普比率: {indicator['sharp_ratio']:.2f}")
    print('='*60)

# ===================== 【掘金标准回测入口】 =====================
if __name__ == '__main__':
    set_serv_addr("192.168.3.12:7001")
    run(
        strategy_id='b8cc65ec-2e42-11f1-bc2a-90658413e684',
        filename='main.py',
        mode=MODE_BACKTEST,
        token='aa08f4cebff6539a76396d3f1f4123e5f7d5f108',
        backtest_start_time='2024-01-01 08:00:00',
        backtest_end_time=f'{datetime.date.today()} 16:00:00',
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1,
        backtest_adjust=ADJUST_PREV
    )