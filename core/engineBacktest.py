"""
多股并发回测引擎 (Backtest Engine)
架构流派: 时间驱动 (Time-Driven)
功能: 构建全局时间轴，按日同步推进多只股票的行情，统筹资金调度与每日快照。
"""
import pandas as pd
from typing import Dict, List
from utils.logger import global_logger as logger


class BacktestEngine:
    def __init__(self, data_dict: Dict[str, pd.DataFrame], strategy, account):
        """
        :param data_dict: 格式为 {'300502': df1, '300308': df2} 的历史 K 线字典
        :param strategy: 继承自 BaseStrategy 的策略实例
        :param account: Portfolio 资金大管家实例
        """
        self.data_dict = data_dict
        self.strategy = strategy
        self.account = account
        self.daily_history: List[dict] = []  # 存放每天的快照

    def run(self) -> pd.DataFrame:
        """
        启动时间机器，运行回测
        :return: 包含每日详细资金与信号快照的 DataFrame
        """
        if not self.data_dict:
            logger.error("回测引擎启动失败：传入的数据字典为空！")
            return pd.DataFrame()

        # 1. 策略预热 (调用 Pandas 向量化极速计算所有指标)
        logger.info("⏳ 引擎启动：正在通知策略大脑进行全量指标预计算...")
        self.strategy.prepare(self.data_dict)

        # 2. 构建全局统一时间轴 (取所有股票交易日的并集并排序)
        all_dates = set()
        for df in self.data_dict.values():
            all_dates.update(df.index)
        sorted_dates = sorted(list(all_dates))

        logger.info(f"📅 统一时间轴构建完毕，总计 {len(sorted_dates)} 个交易日。")
        logger.info("🚀 时光机正式启动，开始逐日撮合...")

        trade_count = 0
        day_counter = 0  # 💡 新增交易日计数器
        # 3. 外层时间循环：历史车轮滚滚向前
        for current_date in sorted_dates:
            date_str = current_date.strftime("%Y-%m-%d")
            day_counter += 1
            daily_prices = {}
            # 初始化当天的快照卡片
            daily_record = {'date': current_date}
            total_market_value = 0.0  # 当日持仓总市值

            # 4. 内层资产循环：检阅每一只股票
            for symbol, df in self.data_dict.items():
                # 检查该股票今天是否交易 (防停牌报错)
                if current_date in df.index:
                    bar = df.loc[current_date]
                    price = bar['close']
                    daily_prices[symbol] = bar['close']
                    # 记录该股今日收盘价
                    daily_record[f"{symbol}_price"] = price

                    # 💡 核心交互：问策略大脑要操作指令
                    action, shares = self.strategy.on_bar(bar, self.account, symbol)

                    # 💡 核心交互：如果有指令，交给财务管家执行
                    if action in ["BUY", "SELL"]:
                        res = self.account.execute_trade(
                            symbol=symbol,
                            action=action,
                            shares=shares,
                            price=price,
                            current_time=date_str
                        )

                        # 如果管家说执行成功了，才在快照上打上买卖标记
                        if res['success']:
                            trade_count += 1
                            signal_key = f"{symbol}_buy_signal" if action == "BUY" else f"{symbol}_sell_signal"
                            daily_record[signal_key] = price
                            logger.info(
                                f"[{date_str}] ⚡ {action} {symbol} {res['filled_shares']}股 @ {price:.2f} | 剩余现金: {self.account.total_cash:.2f}")
                            # 👇 新增这个 else 分支：专门记录因为资金不足或风控被废掉的单子
                        else:
                            logger.warning(f"[{date_str}] 🚫 订单失效 [{symbol}]: {res.get('message')}")

                    # 💡 核心记账：收集 2x2 图表需要的该股深度财务数据
                    held_shares = self.account.get_shares(symbol)
                    stock_market_value = held_shares * price
                    total_market_value += stock_market_value

                    daily_record[f"{symbol}_shares"] = held_shares
                    daily_record[f"{symbol}_avg_price"] = self.account.get_avg_price(symbol)
                    daily_record[f"{symbol}_cost"] = self.account.get_position_cost(symbol)
                    daily_record[f"{symbol}_market_value"] = stock_market_value

            # 5. 每日收盘结算：记录账户总资产
            daily_record['cash'] = self.account.total_cash
            daily_record['equity'] = self.account.total_cash + total_market_value
            if day_counter % 20 == 0:
                self.account.audit_and_rebalance(daily_prices, date_str)
            self.daily_history.append(daily_record)
        self._reconcile_orders()
        logger.info(f"🎉 回测完美收官！共触发有效交易 {trade_count} 笔。")
        logger.info(f"📊 最终账户动态总资产: {self.daily_history[-1]['equity']:.2f} 元")

        # 将历史快照转换为 DataFrame，方便后续画图和计算指标
        df_results = pd.DataFrame(self.daily_history).set_index('date')
        return df_results

    def _reconcile_orders(self):
        """审计部期末对账：对比策略日记本与真实成交流水"""
        logger.info("==========================================")
        logger.info("🕵️ 审计部期末对账报告 (Signal Reconciliation)")
        logger.info("==========================================")

        intended = self.strategy.intended_signals
        executed = self.account.trade_history

        if not intended:
            logger.info("策略未产生任何意向信号。")
            return

        mismatch_count = 0
        for intent in intended:
            # 去真实流水里找有没有这笔交易
            match = next((t for t in executed if
                          t['timestamp'] == intent['date'] and t['symbol'] == intent['symbol'] and t['action'] ==
                          intent['action']), None)

            if match:
                logger.info(
                    f"✅ 对账成功 | {intent['date']} {intent['symbol']} {intent['action']} 因[{intent['reason']}] 意向 {intent['shares']}股，实盘执行 {match['shares']}股")
            else:
                mismatch_count += 1
                logger.warning(
                    f"❌ 对账异常 (废单) | {intent['date']} {intent['symbol']} {intent['action']} 因[{intent['reason']}] 意向 {intent['shares']}股，【但被财务部拦截或未成交】")

        logger.info(f"对账完成。意向信号: {len(intended)}笔，实际成交: {len(executed)}笔，废单/异常: {mismatch_count}笔。")
        logger.info("==========================================")
