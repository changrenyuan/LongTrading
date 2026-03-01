import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
import os
from utils.logger import global_logger as logger


class Plotter:
    @staticmethod
    def plot_portfolio(df_res: pd.DataFrame, symbols: list,
                       symbol_names: dict = None,
                       strategy_name: str = "未知策略",
                       save_dir: str = "data/charts"):
        """绘制账户全局总览 与 个股 2x2 深度分析视图"""
        """绘制账户总资产与个股买卖点"""
        os.makedirs(save_dir, exist_ok=True)

        # 设置中文字体 (Windows通常为SimHei, Mac为Arial Unicode MS)
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False

        # ==========================================
        # 1. 绘制总账户资金曲线与回撤 (全局视角)
        # ==========================================
        fig1, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)

        # 权益曲线
        ax1.plot(df_res.index, df_res['equity'], color='#2980b9', linewidth=2, label='账户动态总资产 (Equity)')
        ax1.axhline(y=df_res['equity'].iloc[0], color='gray', linestyle='--', label='初始本金')
        ax1.fill_between(df_res.index, df_res['equity'], df_res['equity'].iloc[0],
                         where=(df_res['equity'] >= df_res['equity'].iloc[0]), color='#2ecc71', alpha=0.2)
        ax1.set_title("量化回测：账户总动态资产曲线", fontsize=14, fontweight='bold')
        ax1.set_ylabel("总金额 (元)")
        ax1.legend(loc='upper left')
        ax1.grid(True, linestyle=':', alpha=0.6)

        # 回撤曲线
        max_equity = df_res['equity'].cummax()
        drawdown = (df_res['equity'] - max_equity) / max_equity
        ax2.fill_between(df_res.index, drawdown, 0, color='#e74c3c', alpha=0.4)
        ax2.plot(df_res.index, drawdown, color='#c0392b', linewidth=1)
        ax2.set_title("动态回撤曲线 (Drawdown)", fontsize=12)
        ax2.set_ylabel("回撤比例")
        ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y * 100:.0f}%'))
        ax2.grid(True, linestyle=':', alpha=0.6)

        filepath_eq = os.path.join(save_dir, "portfolio_equity.png")
        fig1.savefig(filepath_eq, dpi=150, bbox_inches='tight')
        plt.close(fig1)
        logger.info(f"📈 账户总资产曲线图已保存至: {filepath_eq}")

        # ==========================================
        # 2. 个股 2x2 深度分析视图 (核心升级)
        # ==========================================
        for symbol in symbols:
            stock_name = symbol_names.get(symbol, "未知名称")

            # 创建 2x2 布局
            fig, axes = plt.subplots(2, 2, figsize=(18, 12))
            fig.suptitle(f"策略标的分析 | 标的: {symbol} {stock_name} | 策略: {strategy_name}",
                         fontsize=18, fontweight='bold', y=0.98)

            ax_price = axes[0, 0]  # 左上：价格、成本与买卖点
            ax_alloc = axes[0, 1]  # 右上：资金占用占比
            ax_pnl = axes[1, 0]  # 左下：盈亏对总资产影响
            ax_pie = axes[1, 1]  # 右下：胜率饼图

            # 提取该股票所需列
            price_col = f"{symbol}_price"
            buy_col = f"{symbol}_buy_signal"
            sell_col = f"{symbol}_sell_signal"
            avg_price_col = f"{symbol}_avg_price"
            cost_col = f"{symbol}_cost"
            mv_col = f"{symbol}_market_value"

            # 如果缺少数据，跳过绘制
            if price_col not in df_res.columns: continue

            # ---------- 图 1: 价格、成本与买卖点 (左上) ----------
            ax_price.plot(df_res.index, df_res[price_col], color='#34495e', alpha=0.8, label='收盘价')

            # 绘制持仓成本线 (只有持仓时才显示，将 0 替换为 NaN)
            if avg_price_col in df_res.columns:
                avg_price_series = df_res[avg_price_col].replace(0, np.nan)
                ax_price.plot(df_res.index, avg_price_series, color='#f39c12', linestyle='--', linewidth=2,
                              label='持仓成本均价')

            # 标记买卖点
            if buy_col in df_res.columns and df_res[buy_col].notna().any():
                buys = df_res[df_res[buy_col].notna()]
                ax_price.scatter(buys.index, buys[buy_col], color='#e74c3c', marker='^', s=120, label='买入', zorder=5)
            if sell_col in df_res.columns and df_res[sell_col].notna().any():
                sells = df_res[df_res[sell_col].notna()]
                ax_price.scatter(sells.index, sells[sell_col], color='#2ecc71', marker='v', s=120, label='卖出',
                                 zorder=5)

            ax_price.set_title("1. 价格走势与交易动作", fontsize=12)
            ax_price.legend(loc='upper left')
            ax_price.grid(True, linestyle=':', alpha=0.6)

            # ---------- 图 2: 资金分配占比 (右上) ----------
            if mv_col in df_res.columns:
                # 资金占比 = 该股持仓市值 / 账户总动态权益
                alloc_ratio = (df_res[mv_col] / df_res['equity']) * 100
                ax_alloc.fill_between(df_res.index, alloc_ratio, 0, color='#9b59b6', alpha=0.3)
                ax_alloc.plot(df_res.index, alloc_ratio, color='#8e44ad', linewidth=1.5)
                ax_alloc.axhline(y=33.3, color='gray', linestyle=':', label='风控参考线 (1/3)')

                ax_alloc.set_title("2. 仓位资金占比 (资金分配风险)", fontsize=12)
                ax_alloc.set_ylabel("占总资产比例 (%)")
                ax_alloc.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.1f}%'))
                ax_alloc.legend(loc='upper left')
                ax_alloc.grid(True, linestyle=':', alpha=0.6)

            # ---------- 图 3: 盈亏对总资产的比例 (左下) ----------
            if mv_col in df_res.columns and cost_col in df_res.columns:
                # 浮动盈亏 = 市值 - 成本
                floating_pnl = df_res[mv_col] - df_res[cost_col]
                # 对总资产的影响占比
                pnl_impact_ratio = (floating_pnl / df_res['equity']) * 100

                ax_pnl.fill_between(df_res.index, pnl_impact_ratio, 0, where=(pnl_impact_ratio >= 0), color='#e74c3c',
                                    alpha=0.4, label='浮盈贡献')
                ax_pnl.fill_between(df_res.index, pnl_impact_ratio, 0, where=(pnl_impact_ratio < 0), color='#2ecc71',
                                    alpha=0.4, label='浮亏拖累')
                ax_pnl.plot(df_res.index, pnl_impact_ratio, color='#7f8c8d', linewidth=1)
                ax_pnl.axhline(0, color='black', linewidth=0.8)

                ax_pnl.set_title("3. 盈亏对总资产影响占比 (止盈止损监测)", fontsize=12)
                ax_pnl.set_ylabel("影响比例 (%)")
                ax_pnl.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.1f}%'))
                ax_pnl.legend(loc='upper left')
                ax_pnl.grid(True, linestyle=':', alpha=0.6)

            # ---------- 图 4: 胜率统计饼图 (右下) ----------
            wins, losses = 0, 0
            buy_price_cache = 0

            # 简单的 FIFO 匹配胜率统计 (适合全仓买卖的策略)
            for idx, row in df_res.iterrows():
                if buy_col in df_res.columns and pd.notna(row[buy_col]):
                    buy_price_cache = row[buy_col]
                elif sell_col in df_res.columns and pd.notna(row[sell_col]):
                    sell_price = row[sell_col]
                    if buy_price_cache > 0:
                        if sell_price > buy_price_cache:
                            wins += 1
                        else:
                            losses += 1
                        buy_price_cache = 0  # 匹配完重置

            total_trades = wins + losses
            if total_trades > 0:
                ax_pie.pie([wins, losses], labels=['盈利交易 (Win)', '亏损交易 (Loss)'],
                           autopct='%1.1f%%', colors=['#e74c3c', '#2ecc71'],
                           startangle=90, explode=(0.05, 0), shadow=True)
                ax_pie.set_title(f"4. 策略胜率分布 (共 {total_trades} 次开平仓)", fontsize=12)
            else:
                ax_pie.text(0.5, 0.5, "回测期间无完整交易记录", ha='center', va='center', fontsize=12)
                ax_pie.set_title("4. 策略胜率分布", fontsize=12)

            # 调整时间轴格式 (前三个图)
            for ax in [ax_price, ax_alloc, ax_pnl]:
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha='right')

            plt.tight_layout(rect=[0, 0, 1, 0.96])  # 留出总标题空间

            filepath_stock = os.path.join(save_dir, f"{symbol}_2x2_analysis.png")
            fig.savefig(filepath_stock, dpi=150, bbox_inches='tight')
            plt.close(fig)
            logger.info(f"📈 {symbol} 专业 2x2 深度分析图已保存至: {filepath_stock}")