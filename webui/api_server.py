import os
import json
import subprocess
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from live_exchage.universe import UniverseManager
from live_exchage.ledger import LedgerManager
from fastapi import BackgroundTasks
app = FastAPI(title="MT_Alpha 核心数据总线", version="1.0.0")
origins = [
    "http://localhost:3000",  # Next.js 默认开发端口
    "http://127.0.0.1:3000",
    "https://your-domain.com",  # 生产环境域名
    "https://www.your-domain.com",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 允许的源
    allow_credentials=True,  # 允许携带 Cookie
    allow_methods=["*"],  # 允许所有 HTTP 方法 (GET, POST, PUT, DELETE 等)
    allow_headers=["*"],  # 允许所有请求头
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM_ACCOUNT_FILE = os.path.join(BASE_DIR, "data", "system_account.json")
MANUAL_ACCOUNT_FILE = os.path.join(BASE_DIR, "data", "live_broker_account.json")
LIVE_LEDGER_FILE = os.path.join(BASE_DIR, "data", "live_trade_ledger.csv")
UNIVERSE_POOL_FILE = os.path.join(BASE_DIR, "data", "universe_pool.json")
STRATEGY_CONFIG_FILE = os.path.join(BASE_DIR, "data", "best_params_win50p.json")
DAILY_NAV_FILE = os.path.join(BASE_DIR, "data", "daily_nav.csv")
BACKTEST_DATA_DIR = os.path.join(BASE_DIR, "data", "backtest")
CHARTS_DIR = os.path.join(BASE_DIR, "data", "charts")
LIVE_SCRIPT = os.path.join(BASE_DIR, "live_main.py")
from utils.metrics import MetricsCalculator # 💡 引入专业的精算师

@app.get("/")
def ping(): return {"status": "ok"}


@app.get("/api/v1/ledger/status")
def get_ledger_status():
    sys_pos, man_pos = {}, {}
    if os.path.exists(SYSTEM_ACCOUNT_FILE):
        with open(SYSTEM_ACCOUNT_FILE, "r", encoding="utf-8") as f:
            # 使用 (shares, cost_price) 元组作为值
            sys_pos = {
                p['symbol']: (p['shares'], round(float(p.get('cost_price', 0)), 3))
                for p in json.load(f).get('positions', [])
            }

    # 2. 提取人工账本：包含股数和成本价
    if os.path.exists(MANUAL_ACCOUNT_FILE):
        with open(MANUAL_ACCOUNT_FILE, "r", encoding="utf-8") as f:
            # 确保人工账本 JSON 中也包含 cost_price 字段
            man_pos = {
                p['symbol']: (p['shares'], round(float(p.get('cost_price', 0)), 3))
                for p in json.load(f).get('positions', [])
            }
    is_match = (sys_pos == man_pos)
    return {"is_match": is_match,
            "message": "🟢 账本对账一致" if is_match else "🔴 对账异常：系统预估持仓与人工真实账本不符！"}


# @app.get("/api/v1/ledger/assets")
@app.get("/api/v1/ledger/assets")
def get_portfolio_status():
    """
    💡 核心数据总线：适配 page.tsx 的前端结构
    包含：可用现金、完整持仓、量化指标 (metrics)、盈亏概览 (pnl_summary)
    """
    # 初始默认结构
    data = {
        "available_cash": 0.0,
        "positions": [],
        "metrics": {
            "total_pnl": 0.0,
            "annualized_return": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "calmar_ratio": 0.0
        },
        "pnl_summary": {
            "position_pnl": 0.0,  # 对应 Card 1: 持仓盈亏
            "daily_pnl": 0.0,  # 对应 Card 2: 当日盈亏
            "daily_pnl_pct": 0.0  # 对应 Card 2: 当日涨跌幅
        }
    }

    # 1. 加载系统账本
    if os.path.exists(SYSTEM_ACCOUNT_FILE):
        try:
            with open(SYSTEM_ACCOUNT_FILE, "r", encoding="utf-8") as f:
                raw_account = json.load(f)
                data["available_cash"] = raw_account.get("available_cash", 0.0)
                data["positions"] = raw_account.get("positions", [])
        except Exception as e:
            print(f"读取账本失败: {e}")

    # 2. 💡 数据补全与持仓盈亏 (position_pnl) 计算
    current_pos_pnl = 0.0
    for p in data["positions"]:
        # 针对前端 Number(pnl_pct) 的适配：如果 pnl_pct 是字符串 "+5.2%"，转换为 float
        if isinstance(p.get("pnl_pct"), str):
            try:
                p["pnl_pct"] = float(p["pnl_pct"].replace('%', '').replace('+', ''))
            except:
                p["pnl_pct"] = 0.0

        # 盈亏计算防御
        if p.get('pnl') is None:
            shares = float(p.get('shares', 0))
            curr = float(p.get('current_price', 0))
            cost = float(p.get('cost_price', 0))
            p['pnl'] = round((curr - cost) * shares, 2)

        current_pos_pnl += float(p.get('pnl', 0.0))

    data["pnl_summary"]["position_pnl"] = round(current_pos_pnl, 2)

    # 3. 💡 历史净值分析：当日盈亏 (daily_pnl) 与 量化指标 (metrics)
    if os.path.exists(DAILY_NAV_FILE):
        try:
            df_nav = pd.read_csv(DAILY_NAV_FILE)
            if len(df_nav) > 0:
                # 基础总盈亏
                init_eq = df_nav.iloc[0]['Equity']
                curr_eq = df_nav.iloc[-1]['Equity']
                data["metrics"]["total_pnl"] = round(curr_eq - init_eq, 2)

                # 当日盈亏与百分比计算
                if len(df_nav) >= 2:
                    yesterday_eq = df_nav.iloc[-2]['Equity']
                    daily_diff = curr_eq - yesterday_eq
                    data["pnl_summary"]["daily_pnl"] = round(daily_diff, 2)
                    data["pnl_summary"]["daily_pnl_pct"] = round((daily_diff / yesterday_eq) * 100, 2)

                # 专业精算 (夏普/卡玛/年化)
                if len(df_nav) > 1:
                    df_nav['Date'] = pd.to_datetime(df_nav['Date'])
                    df_nav.set_index('Date', inplace=True)
                    df_nav.rename(columns={'Equity': 'equity'}, inplace=True)

                    calc_res = MetricsCalculator.calculate(df_nav, initial_capital=init_eq)
                    # 映射 MetricsCalculator 的中文 Key 到前端期待的英文 Key
                    data["metrics"]["annualized_return"] = float(calc_res.get("年化收益率", "0").strip('%'))
                    data["metrics"]["sharpe_ratio"] = float(calc_res.get("夏普比率", 0))
                    data["metrics"]["max_drawdown"] = float(calc_res.get("最大回撤", "0").strip('%'))
                    data["metrics"]["calmar_ratio"] = float(calc_res.get("卡玛比率", 0))
        except Exception as e:
            print(f"精算分析失败: {e}")

    return data


@app.get("/api/v1/ledger/nav_history")
def get_nav_history():
    """
    📈 获取历史净值曲线数据，直接对接前端图表
    """
    if not os.path.exists(DAILY_NAV_FILE):
        return []

    try:
        # 读取 CSV 数据
        df = pd.read_csv(DAILY_NAV_FILE)
        if df.empty:
            return []

        # 1. 数据清洗：去除空值
        df = df.dropna(subset=['Date', 'Equity'])

        # 2. 转换日期格式，确保前端能够识别
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')

        # 3. 按日期排序并去重（保留最后一次记录）
        df = df.sort_values('Date').drop_duplicates('Date', keep='last')

        # 4. 转换为前端标准格式：[{date: '...', equity: ...}]
        chart_data = df.rename(columns={'Date': 'date', 'Equity': 'equity'}).to_dict(orient='records')

        return chart_data
    except Exception as e:
        print(f"提取净值历史失败: {e}")
        return []
@app.get("/api/v1/universe/pool")
def get_universe_pool():
    if not os.path.exists(UNIVERSE_POOL_FILE): return []
    with open(UNIVERSE_POOL_FILE, "r", encoding="utf-8") as f: return json.load(f)


@app.post("/api/v1/ledger/manual_sync")
def sync_ledger():
    """💡 API 层：现在只负责调用模块，不写逻辑"""
    try:
        # 初始化需要的工具
        # 这里建议将 universe_manager 设为全局或在启动时初始化
        um = UniverseManager()
        lm = LedgerManager()

        success = lm.sync_manual_to_system(um)

        if success:
            return {"status": "success", "message": "对账完成，数据已全量补全"}
        else:
            raise HTTPException(status_code=500, detail="对账模块执行失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/orders/today")
def get_recent_trades(limit: int = 50):
    if not os.path.exists(LIVE_LEDGER_FILE): return []
    try:
        df = pd.read_csv(LIVE_LEDGER_FILE, dtype=str).fillna("")
        return df.tail(limit).iloc[::-1].to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/engine/run_once")
def run_live_engine():
    result = subprocess.run(["python", LIVE_SCRIPT], cwd=BASE_DIR, capture_output=True, text=True, timeout=180)
    if result.returncode == 0: return {"status": "success"}
    raise HTTPException(status_code=500, detail=f"引擎报错: {result.stderr}")

#策略
@app.get("/api/v1/strategy/params")
def get_params():
    if not os.path.exists(STRATEGY_CONFIG_FILE): return {}
    with open(STRATEGY_CONFIG_FILE, "r", encoding="utf-8") as f: return json.load(f)

@app.post("/api/v1/strategy/params")
def update_params(new_params: dict):
    try:
        with open(STRATEGY_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(new_params, f, indent=4, ensure_ascii=False)
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# 通用 JSON 读取器
def load_backtest_json(filename: str):
    path = os.path.join(BACKTEST_DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# 💡 通用读取器：支持动态路径
def load_json_by_strategy(strategy_id: str, filename: str):
    # 默认值处理
    sid = strategy_id if strategy_id else "strategy_trend"
    path = os.path.join(BACKTEST_DATA_DIR, sid, filename)

    if not os.path.exists(path):
        # 如果子文件夹不存在，尝试读取根目录作为兜底
        fallback_path = os.path.join(BACKTEST_DATA_DIR, filename)
        if not os.path.exists(fallback_path):
            return []
        path = fallback_path

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
@app.get("/api/v1/backtest/equity_curve")
def get_backtest_equity(strategy_id: str = None):
    """📈 对接 EquityCurveChart.tsx -> equity_curve.json"""
    return load_json_by_strategy(strategy_id, "equity_curve.json")

@app.get("/api/v1/backtest/drawdown")
def get_backtest_drawdown(strategy_id: str = None):
    """📉 对接 DrawdownChart.tsx -> drawdown.json"""
    return load_json_by_strategy(strategy_id, "drawdown.json")

@app.get("/api/v1/backtest/backtest_stocks")
def get_backtest_stocks():
    """🎯 对接 KlineSignalChart.tsx 下拉框 -> backtest_stocks.json"""
    return load_backtest_json("backtest_stocks.json")

@app.get("/api/v1/backtest/kline_signals")
def get_kline_signals(symbol: str):
    """🕯️ 对接 KlineSignalChart.tsx 主图 -> kline_{symbol}.json"""
    # 优先读取 PushJSON 预处理好的个股详情包
    filename = f"kline_{symbol}.json"
    data = load_backtest_json(filename)
    if not data:
        return {"symbol": symbol, "kline": [], "signals": []}
    return data

@app.get("/api/v1/backtest/trades")
def get_backtest_trades():
    """📊 对接 WinRatePieChart / PnlImpactCard -> trades.json"""
    return load_backtest_json("trades.json")
@app.get("/api/v1/backtest/summary")
def get_backtest_summary():
    path = os.path.join(BASE_DIR, "data", "backtest", "summary.json")
    if not os.path.exists(path): return {}
    with open(path, "r", encoding="utf-8") as f: return json.load(f)