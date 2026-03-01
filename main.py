import os
from data_provider.akshare_pd import AkShareProvider
from core.account import Portfolio
from core.engineBacktest import BacktestEngine
from strategies.sma520 import SMA520Strategy
from utils.plotter import Plotter
from strategies.trendv3 import InstitutionalTrendStrategy

def run_backtest():
    # 1. 准备底稿清理
    ledger_path = "data/main_ledger.csv"
    if os.path.exists(ledger_path): os.remove(ledger_path)
    if os.path.exists(ledger_path.replace("ledger", "positions")): os.remove(ledger_path.replace("ledger", "positions"))

    # 2. 定义股票池并拉取数据
    symbols = ["300502", "300308"]
    symbol_names = {"300502": "新易盛", "300308": "中际旭创"}
    provider = AkShareProvider()
    data_dict = {sym: provider.get_data(sym) for sym in symbols if not provider.get_data(sym).empty}

    # 3. 初始化三剑客 (管家、策略、引擎)
    account = Portfolio(initial_cash=1000000.0,symbols=symbols, ledger_path=ledger_path)
    strategy = InstitutionalTrendStrategy(cfg={},symbols=symbols)
    engine = BacktestEngine(data_dict=data_dict, strategy=strategy, account=account)

    # 4. 一键起飞！
    df_results = engine.run()

    # 5. 渲染 2x2 机构级专业图表
    Plotter.plot_portfolio(
        df_res=df_results, 
        symbols=symbols, 
        symbol_names=symbol_names,
        strategy_name="trendv2",
        save_dir="data/charts"
    )

if __name__ == "__main__":
    run_backtest()