import os
import json
import pandas as pd
import numpy as np


class PushJSON:
    """
    🚀 对照 plotter.py 逻辑，将回测内存数据序列化为前端 JSON 数据包
    补全个股动态盈亏占比、资金占用占比等深度分析维度
    """

    @classmethod
    def export_all(cls, df_res: pd.DataFrame,
                   account,
                   symbols: list,
                   symbol_names: dict,
                   data_dict: dict,
                   strategy_id: str = "strategy_trend",
                   base_save_dir: str = "data/backtest"):
        """
        核心导出入口：同步生成全局曲线与个股深度分析 JSON
        """
        save_dir = os.path.join(base_save_dir, strategy_id)
        os.makedirs(save_dir, exist_ok=True)

        # 0. 基础时间轴与权益对齐 (用于计算比例的分母)
        if not isinstance(df_res.index, pd.DatetimeIndex):
            df_res.index = pd.to_datetime(df_res.index)
        df_res['date_str'] = df_res.index.strftime('%Y-%m-%d')
        initial_capital = df_res['equity'].iloc[0]

        # 1. 导出全局净值与回撤 (对接 EquityCurveChart & DrawdownChart)
        df_res['running_max'] = df_res['equity'].cummax()
        df_res['drawdown'] = (df_res['equity'] / df_res['running_max'] - 1) * 100

        equity_curve = []
        drawdown_curve = []
        for date_str, row in df_res.iterrows():
            d_str = row['date_str']
            equity_curve.append({
                "date": d_str,
                "equity": round(float(row['equity']), 2),
                "benchmark": round(float(initial_capital), 2)
            })
            drawdown_curve.append({
                "date": d_str,
                "drawdown": round(float(row['drawdown']), 2)
            })

        cls._save_json(os.path.join(save_dir, "equity_curve.json"), equity_curve)
        cls._save_json(os.path.join(save_dir, "drawdown.json"), drawdown_curve)

        # 2. 导出基础交易流水
        trades_list = []
        for t in account.trade_history:
            trades_list.append({
                "date": str(t['timestamp']),
                "symbol": t['symbol'],
                "name": symbol_names.get(t['symbol'], t['symbol']),
                "action": t['action'],
                "shares": int(t['shares']),
                "price": round(float(t['price']), 2),
                "pnl": round(float(t.get('realized_pnl', 0)), 2),
                "reason": t.get('reason', '技术指标触发'),
                "status": "回测中已执行"  # 💡 补全接口期待的 status
            })
        cls._save_json(os.path.join(base_save_dir, "trades.json"), trades_list)

        # 3. 🚀 对标 plotter.py：计算每只股票的每日深度维度
        # 我们需要从账户底稿中重建每日持仓状态
        ledger_df = pd.DataFrame(account.trade_history) if account.trade_history else pd.DataFrame()

        for sym in symbols:
            if sym not in data_dict: continue
            df_stock = data_dict[sym].copy()
            df_stock['ma5'] = df_stock['close'].rolling(5).mean()
            df_stock['ma20'] = df_stock['close'].rolling(20).mean()
            df_stock = df_stock.fillna(0)  # 💡 建议在计算 MA 后统一填充
            # --- 精算个股每日占比逻辑 ---
            pnl_ratio_data = []
            capital_usage_data = []

            curr_shares = 0
            curr_cum_pnl = 0

            # 遍历回测全周期时间点，确保与总权益曲线对齐
            for date_ts in df_res.index:
                date_str = date_ts.strftime('%Y-%m-%d')
                total_equity = df_res.loc[date_ts, 'equity']

                # 提取截止到该日期的该股交易
                if not ledger_df.empty:
                    day_trades = ledger_df[(ledger_df['symbol'] == sym) & (ledger_df['timestamp'] == date_str)]
                    for _, t in day_trades.iterrows():
                        if t['action'] == 'BUY':
                            curr_shares += t['shares']
                        elif t['action'] == 'SELL':
                            curr_shares -= t['shares']
                            curr_cum_pnl += t['realized_pnl']

                # 获取该股当日收盘价
                price = df_stock.loc[date_ts, 'close'] if date_ts in df_stock.index else 0

                # A. 盈亏占比 (对应 plotter 第3图)
                pnl_ratio_data.append({
                    "date": date_str,
                    "pnlRatio": round((curr_cum_pnl / total_equity) * 100, 4),
                    "totalPnl": round(float(curr_cum_pnl), 2)
                })

                # B. 资金占用占比 (对应 plotter 第2图)
                market_value = curr_shares * price
                capital_usage_data.append({
                    "date": date_str,
                    "capitalUsage": round((market_value / total_equity) * 100, 4),
                    "position": int(curr_shares)
                })

            # --- 拼装 K线 详情包 ---
            kline_data = []
            for date, row in df_stock.iterrows():
                kline_data.append({
                    "date": date.strftime('%Y-%m-%d'),
                    "open": round(float(row['open']), 2),
                    "high": round(float(row['high']), 2),
                    "low": round(float(row['low']), 2),
                    "close": round(float(row['close']), 2),
                    "ma5": round(float(row['ma5'] or 0), 2),
                    "ma20": round(float(row['ma20'] or 0), 2)
                })

            # 过滤信号
            stock_signals = [t for t in trades_list if t['symbol'] == sym]

            cls._save_json(os.path.join(base_save_dir, f"kline_{sym}.json"), {
                "symbol": sym,
                "name": symbol_names.get(sym, sym),
                "kline": kline_data,
                "signals": stock_signals,
                "pnlRatioData": pnl_ratio_data,  # 💡 补全副图1数据
                "capitalUsageData": capital_usage_data  # 💡 补全副图2数据
            })

        # 4. 导出股票概览列表
        stocks_info = []
        for sym in symbols:
            s_trades = [t for t in trades_list if t['symbol'] == sym and t['action'] == 'SELL']
            total_pnl = sum(t['pnl'] for t in s_trades)
            stocks_info.append({
                "symbol": sym,
                "name": symbol_names.get(sym, sym),
                "return_pct": round((total_pnl / initial_capital) * 100, 2),
                "trades": len(s_trades)
            })
        cls._save_json(os.path.join(base_save_dir, "backtest_stocks.json"), stocks_info)
        # --- ADD: 导出宏观绩效指标 summary.json ---
        from utils.metrics import MetricsCalculator
        summary_metrics = MetricsCalculator.calculate(df_res, initial_capital)
        cls._save_json(os.path.join(base_save_dir, "summary.json"), {
            "total_pnl": round(float(df_res['equity'].iloc[-1] - initial_capital), 2),
            "sharpe_ratio": float(summary_metrics.get("夏普比率", 0)),
            "max_drawdown": float(summary_metrics.get("最大回撤", "0").strip('%')),
            "calmar_ratio": float(summary_metrics.get("卡玛比率", 0)),
            "annualized_return": float(summary_metrics.get("年化收益率", "0").strip('%')),
            "win_rate": float(summary_metrics.get("胜率", "0").strip('%'))
        })
        print(f"📡 [PushJSON] 策略 {strategy_id} 深度分析包(包含占比曲线)已导出。")

    @staticmethod
    def _save_json(path, data):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)