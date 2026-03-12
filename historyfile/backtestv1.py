import os
import pandas as pd
from data_provider.akshare_pd import AkShareProvider
from core.account import Portfolio
from core.engineBacktest import BacktestEngine
from utils.plotter import Plotter
from strategies.trend import InstitutionalTrendStrategy
from utils.metrics import MetricsCalculator
from utils.pushjson import PushJSON

def run_backtest():
    # 1. 准备交易备忘录
    ledger_path = "../data/main_ledger.csv"
    if os.path.exists(ledger_path): os.remove(ledger_path)
    if os.path.exists(ledger_path.replace("ledger", "positions")): os.remove(ledger_path.replace("ledger", "positions"))

    # 2. 定义股票池与大资金 ( 100 万)
    symbols = ["300502", "300308","601606"]
    symbol_names = {"300502": "新易盛", "300308": "中际旭创","601606": "长城军工"}


    initial_capital = 1000000.0  # 100万初始资金

    provider = AkShareProvider()
    data_dict = {sym: provider.get_data(sym) for sym in symbols if not provider.get_data(sym).empty}

    # 4. 初始化三剑客
    account = Portfolio(initial_cash=initial_capital, symbols=symbols, ledger_path=ledger_path)
    # 💡 注入高敏参数
    strategy = InstitutionalTrendStrategy(symbols=symbols)
    engine = BacktestEngine(data_dict=data_dict, strategy=strategy, account=account)

    # 5. 一键起飞！
    df_results = engine.run()

    # ==========================================
    # 📊 6. 机构级绩效评估 (接入 metrics.py)
    # ==========================================
    if not df_results.empty:
        # metrics.py 需要 pnl 列
        df_results['pnl'] = df_results['equity'] - initial_capital

        # 为了适配 metrics.py 的胜率统计，这里做个小 hack (因为目前多股信号是分开存的)
        # 我们用 account 的真实底稿来计算更精准的胜率
        real_trades = account.trade_history
        win_trades = sum(1 for t in real_trades if t['action'] == 'SELL' and t['realized_pnl'] > 0)
        loss_trades = sum(1 for t in real_trades if t['action'] == 'SELL' and t['realized_pnl'] <= 0)
        total_exits = win_trades + loss_trades
        real_win_rate = (win_trades / total_exits * 100) if total_exits > 0 else 0

        print("\n" + "=" * 50)
        print("🏆 策略核心绩效评估报告 (Tear Sheet)")
        print("=" * 50)

        # 调用 MetricsCalculator
        eval_metrics = MetricsCalculator.calculate(df_results, initial_capital)

        print(f"💰 初始本金:   {initial_capital:,.2f}")
        print(f"💵 最终权益:   {df_results['equity'].iloc[-1]:,.2f}")
        print(f"📈 累计收益率: {eval_metrics.get('累计收益率')}")
        print(f"🚀 年化收益率: {eval_metrics.get('年化收益率')}")
        print(f"📉 最大回撤:   {eval_metrics.get('最大回撤')}  <-- (老板最看重这个)")
        print(f"⚖️ 夏普比率:   {eval_metrics.get('夏普比率')}  <-- (大于 1.5 就算优秀)")
        print(f"🛡️ 卡玛比率:   {eval_metrics.get('卡玛比率')}  <-- (收益回撤比)")
        print(f"🎯 真实胜率:   {real_win_rate:.1f}% (共 {total_exits} 次平仓)")
        print("=" * 50 + "\n")

    # 7. 渲染 2x2 机构级专业图表
    Plotter.plot_portfolio(
        df_res=df_results,
        symbols=symbols,
        symbol_names=symbol_names,
        strategy_name="Trend",
        save_dir="../data/charts"
    )

# ==========================================
    # 📡 8. 导出前端 JSON 数据总线
    # ==========================================

    PushJSON.export_all(
        df_res=df_results,
        account=account,
        symbols=symbols,
        symbol_names=symbol_names,
        data_dict=data_dict,
        strategy_id = "strategy_trend",
        base_save_dir ="../data/backtest"
    )
if __name__ == "__main__":
    run_backtest()