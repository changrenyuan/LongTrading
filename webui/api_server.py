import os
import json
import subprocess
import pandas as pd
from fastapi import FastAPI, HTTPException

app = FastAPI(title="MT_Alpha 核心数据总线", version="1.0.0")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM_ACCOUNT_FILE = os.path.join(BASE_DIR, "data", "system_account.json")
MANUAL_ACCOUNT_FILE = os.path.join(BASE_DIR, "data", "live_broker_account.json")
LIVE_LEDGER_FILE = os.path.join(BASE_DIR, "data", "live_trade_ledger.csv")
UNIVERSE_POOL_FILE = os.path.join(BASE_DIR, "data", "universe_pool.json")
DAILY_NAV_FILE = os.path.join(BASE_DIR, "data", "daily_nav.csv")
LIVE_SCRIPT = os.path.join(BASE_DIR, "live_main.py")
from utils.metrics import MetricsCalculator # 💡 引入专业的精算师

@app.get("/")
def ping(): return {"status": "ok"}


@app.get("/api/v1/ledger/status")
def get_ledger_status():
    sys_pos, man_pos = {}, {}
    if os.path.exists(SYSTEM_ACCOUNT_FILE):
        with open(SYSTEM_ACCOUNT_FILE, "r", encoding="utf-8") as f: sys_pos = {p['symbol']: p['shares'] for p in
                                                                               json.load(f).get('positions', [])}
    if os.path.exists(MANUAL_ACCOUNT_FILE):
        with open(MANUAL_ACCOUNT_FILE, "r", encoding="utf-8") as f: man_pos = {p['symbol']: p['shares'] for p in
                                                                               json.load(f).get('positions', [])}
    is_match = (sys_pos == man_pos)
    return {"is_match": is_match,
            "message": "🟢 账本对账一致" if is_match else "🔴 对账异常：系统预估持仓与人工真实账本不符！"}


@app.get("/api/v1/ledger/assets")
def get_portfolio_status():
    data = {"available_cash": 0.0, "positions": []}
    if os.path.exists(SYSTEM_ACCOUNT_FILE):
        with open(SYSTEM_ACCOUNT_FILE, "r", encoding="utf-8") as f: data = json.load(f)

    metrics_data = {"total_pnl": 0.0, "annualized_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0,
                    "calmar_ratio": 0.0}

    # 💡 核心重构：名正言顺地调用 MetricsCalculator
    if os.path.exists(DAILY_NAV_FILE):
        try:
            df_nav = pd.read_csv(DAILY_NAV_FILE)
            if len(df_nav) > 0:
                init_eq = df_nav.iloc[0]['Equity']
                curr_eq = df_nav.iloc[-1]['Equity']
                metrics_data['total_pnl'] = curr_eq - init_eq

                # 为了喂给 metrics.py，把数据整形成它喜欢的样子 (Date作为索引，包含equity列)
                df_nav['Date'] = pd.to_datetime(df_nav['Date'])
                df_nav.set_index('Date', inplace=True)
                df_nav.rename(columns={'Equity': 'equity'}, inplace=True)

                # 只有大于 1 天的数据，计算夏普和年化才有意义，否则原样返回 0
                if len(df_nav) > 1:
                    # 💡 专业的事交给专业的模块
                    calc_result = MetricsCalculator.calculate(df_nav, initial_capital=init_eq)
                    metrics_data['annualized_return'] = float(calc_result["年化收益率"].strip('%'))
                    metrics_data['sharpe_ratio'] = float(calc_result["夏普比率"])
                    metrics_data['max_drawdown'] = float(calc_result["最大回撤"].strip('%'))
                    metrics_data['calmar_ratio'] = float(calc_result["卡玛比率"])
        except Exception as e:
            print(f"API 获取高级指标失败: {e}")

    data['metrics'] = metrics_data
    return data
@app.get("/api/v1/universe/pool")
def get_universe_pool():
    if not os.path.exists(UNIVERSE_POOL_FILE): return []
    with open(UNIVERSE_POOL_FILE, "r", encoding="utf-8") as f: return json.load(f)


@app.post("/api/v1/ledger/manual_sync")
def sync_ledger():
    if not os.path.exists(MANUAL_ACCOUNT_FILE):
        raise HTTPException(status_code=404, detail="人工账本不存在")

    with open(MANUAL_ACCOUNT_FILE, "r", encoding="utf-8") as f:
        manual_data = json.load(f)

    # 💡 核心修复：温柔地合并数据，而不是粗暴覆盖
    system_data = {"available_cash": manual_data.get("available_cash", 0.0), "positions": []}

    if os.path.exists(SYSTEM_ACCOUNT_FILE):
        with open(SYSTEM_ACCOUNT_FILE, "r", encoding="utf-8") as f:
            old_sys = json.load(f)

        # 建立旧系统的富文本记忆库
        rich_lookup = {p["symbol"]: p for p in old_sys.get("positions", [])}

        for m_pos in manual_data.get("positions", []):
            sym = m_pos.get("symbol")
            if sym in rich_lookup:
                # 只更新股数和成本，保留名称、盈亏、买入原因等所有富文本
                merged_pos = rich_lookup[sym].copy()
                merged_pos["shares"] = m_pos.get("shares", 0)
                if "cost_price" in m_pos: merged_pos["cost_price"] = m_pos["cost_price"]
                system_data["positions"].append(merged_pos)
            else:
                system_data["positions"].append(m_pos)
    else:
        system_data = manual_data

    with open(SYSTEM_ACCOUNT_FILE, "w", encoding="utf-8") as f:
        json.dump(system_data, f, indent=4, ensure_ascii=False)

    return {"status": "success", "message": "已强制同步为人工账本状态，且完好保留了富文本记忆"}

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