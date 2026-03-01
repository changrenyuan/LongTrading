"""
绩效指标计算模块 (V6 架构适配版)

支持计算的指标：
- 收益率指标：累计收益率、年化收益率
- 风险指标：最大回撤、年化波动率、下行波动率
- 风险调整收益：夏普比率、索提诺比率、卡玛比率
- 交易统计：精确胜率、盈亏比、交易次数 (基于 Account 真实流水底稿)
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, List


class MetricsCalculator:
    """绩效指标计算器"""

    @staticmethod
    def calculate(df: pd.DataFrame, initial_capital: float, trade_history: List[dict] = None) -> Dict[str, Any]:
        """
        计算完整绩效指标

        Args:
            df: 回测结果DataFrame，需包含 equity 列，索引必须是日期类型
            initial_capital: 初始资金
            trade_history: 来自 account.trade_history 的真实流水账底稿

        Returns:
            包含所有绩效指标的字典
        """
        if len(df) == 0 or initial_capital <= 0:
            return MetricsCalculator._empty_metrics()

        # 确保索引是 Datetime 类型，否则后面的重采样会报错
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        equity = df['equity']

        # === 收益率指标 ===
        total_return = MetricsCalculator._calc_total_return(equity, initial_capital)
        annual_return = MetricsCalculator._calc_annual_return(equity, initial_capital)

        # === 风险指标 ===
        max_drawdown = MetricsCalculator._calc_max_drawdown(equity)
        annual_volatility = MetricsCalculator._calc_annual_volatility(equity)
        downside_volatility = MetricsCalculator._calc_downside_volatility(equity)

        # === 风险调整收益 ===
        sharpe_ratio = MetricsCalculator._calc_sharpe_ratio(equity)
        sortino_ratio = MetricsCalculator._calc_sortino_ratio(equity, downside_volatility)
        calmar_ratio = MetricsCalculator._calc_calmar_ratio(annual_return, max_drawdown)

        # === 交易统计 (💡 改为解析真实流水账) ===
        trade_stats = MetricsCalculator._calc_trade_stats_from_ledger(trade_history or [])

        return {
            # 收益率指标
            "累计收益率": f"{total_return * 100:.2f}%",
            "年化收益率": f"{annual_return * 100:.2f}%",

            # 风险指标
            "最大回撤": f"{max_drawdown * 100:.2f}%",
            "年化波动率": f"{annual_volatility * 100:.2f}%",
            "下行波动率": f"{downside_volatility * 100:.2f}%",

            # 风险调整收益
            "夏普比率": f"{sharpe_ratio:.2f}",
            "索提诺比率": f"{sortino_ratio:.2f}",
            "卡玛比率": f"{calmar_ratio:.2f}",

            # 交易统计
            "交易天数": len(df),
            "平仓次数": trade_stats['total_exits'],
            "盈利次数": trade_stats['win_trades'],
            "亏损次数": trade_stats['loss_trades'],
            "胜率": f"{trade_stats['win_rate'] * 100:.1f}%",
            "盈亏比": f"{trade_stats['profit_loss_ratio']:.2f}",

            # 原始数值 (用于进一步分析)
            "_raw": {
                "total_return": total_return,
                "annual_return": annual_return,
                "max_drawdown": max_drawdown,
                "annual_volatility": annual_volatility,
                "sharpe_ratio": sharpe_ratio,
                "sortino_ratio": sortino_ratio,
                "calmar_ratio": calmar_ratio,
                **trade_stats
            }
        }

    @staticmethod
    def _empty_metrics() -> Dict[str, Any]:
        return {
            "累计收益率": "0.00%", "年化收益率": "0.00%", "最大回撤": "0.00%",
            "年化波动率": "0.00%", "下行波动率": "0.00%",
            "夏普比率": "0.00", "索提诺比率": "0.00", "卡玛比率": "0.00",
            "交易天数": 0, "平仓次数": 0, "盈利次数": 0, "亏损次数": 0,
            "胜率": "0.0%", "盈亏比": "0.00", "_raw": {}
        }

    @staticmethod
    def _calc_total_return(equity: pd.Series, initial_capital: float) -> float:
        return (equity.iloc[-1] / initial_capital) - 1

    @staticmethod
    def _calc_annual_return(equity: pd.Series, initial_capital: float) -> float:
        days = len(equity)
        if days <= 0: return 0.0
        total_return = MetricsCalculator._calc_total_return(equity, initial_capital)
        return (1 + total_return) ** (252 / days) - 1

    @staticmethod
    def _calc_max_drawdown(equity: pd.Series) -> float:
        max_equity = equity.cummax()
        max_equity_safe = max_equity.replace(0, np.nan)
        drawdowns = (equity - max_equity) / max_equity_safe
        return abs(drawdowns.fillna(0).min())

    @staticmethod
    def _calc_annual_volatility(equity: pd.Series) -> float:
        returns = equity.pct_change().dropna()
        if len(returns) <= 1: return 0.0
        return returns.std() * np.sqrt(252)

    @staticmethod
    def _calc_downside_volatility(equity: pd.Series, risk_free_rate: float = 0.03) -> float:
        returns = equity.pct_change().dropna()
        if len(returns) <= 1: return 0.0
        daily_rf = risk_free_rate / 252
        downside_returns = returns[returns < daily_rf] - daily_rf
        if len(downside_returns) == 0: return 0.0
        return np.sqrt((downside_returns ** 2).mean()) * np.sqrt(252)

    @staticmethod
    def _calc_sharpe_ratio(equity: pd.Series, risk_free_rate: float = 0.03) -> float:
        returns = equity.pct_change().dropna()
        if len(returns) <= 1: return 0.0
        std = returns.std()
        if std <= 0 or np.isnan(std): return 0.0
        excess_return = returns.mean() * 252 - risk_free_rate
        return excess_return / (std * np.sqrt(252))

    @staticmethod
    def _calc_sortino_ratio(equity: pd.Series, downside_vol: float, risk_free_rate: float = 0.03) -> float:
        if downside_vol <= 0: return 0.0
        returns = equity.pct_change().dropna()
        if len(returns) <= 1: return 0.0
        excess_return = returns.mean() * 252 - risk_free_rate
        return excess_return / downside_vol

    @staticmethod
    def _calc_calmar_ratio(annual_return: float, max_drawdown: float) -> float:
        if max_drawdown <= 0: return 0.0
        return annual_return / max_drawdown

    @staticmethod
    def _calc_trade_stats_from_ledger(trade_history: List[dict]) -> Dict[str, Any]:
        """
        💡 新版核心：直接解析大管家的真实流水账底稿，完美支持多股并发、分批加减仓！
        """
        # 仅统计卖出（平仓/落袋为安）的动作来计算胜率和盈亏
        sells = [t for t in trade_history if t.get('action') == 'SELL']

        total_exits = len(sells)
        if total_exits == 0:
            return {'total_exits': 0, 'win_trades': 0, 'loss_trades': 0, 'win_rate': 0.0, 'profit_loss_ratio': 0.0}

        profits = []
        losses = []

        for trade in sells:
            pnl = trade.get('realized_pnl', 0.0)
            if pnl > 0:
                profits.append(pnl)
            else:
                losses.append(abs(pnl))

        win_trades = len(profits)
        loss_trades = len(losses)
        win_rate = win_trades / total_exits

        avg_profit = np.mean(profits) if profits else 0.0
        avg_loss = np