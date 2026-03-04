import os
import json
import subprocess
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="MT_Alpha 核心数据总线", version="2.0.0")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM_ACCOUNT_FILE = os.path.join(BASE_DIR, "data", "system_account.json")
MANUAL_ACCOUNT_FILE = os.path.join(BASE_DIR, "data", "live_broker_account.json")
LIVE_LEDGER_FILE = os.path.join(BASE_DIR, "data", "live_trade_ledger.csv")
LIVE_SCRIPT = os.path.join(BASE_DIR, "live_trading.py")

@app.get("/")
def ping():
    return {"status": "ok", "message": "MT_Alpha API Engine V2 is running."}
# ==========================================
# 1. 资产与对账中心 (Ledger APIs)
# ==========================================
@app.get("/api/v1/ledger/status")
def get_ledger_status():
    """获取双账本对账状态"""
    sys_pos, man_pos = {}, {}
    if os.path.exists(SYSTEM_ACCOUNT_FILE):
        with open(SYSTEM_ACCOUNT_FILE, "r", encoding="utf-8") as f:
            sys_pos = {p['symbol']: p['shares'] for p in json.load(f).get('positions', [])}
    if os.path.exists(MANUAL_ACCOUNT_FILE):
        with open(MANUAL_ACCOUNT_FILE, "r", encoding="utf-8") as f:
            man_pos = {p['symbol']: p['shares'] for p in json.load(f).get('positions', [])}

    is_match = (sys_pos == man_pos)
    return {
        "is_match": is_match,
        "system_positions": sys_pos,
        "manual_positions": man_pos,
        "message": "🟢 对账一致" if is_match else "🔴 对账异常：系统与人工账本不符！"
    }


@app.get("/api/v1/ledger/assets")
def get_portfolio_status():
    """获取宏观资产看板 (暂时返回系统账本状态)"""
    if not os.path.exists(SYSTEM_ACCOUNT_FILE):
        return {"available_cash": 0.0, "positions": []}
    with open(SYSTEM_ACCOUNT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/v1/ledger/manual_sync")
def sync_ledger():
    """以人工账本为准强制同步"""
    if not os.path.exists(MANUAL_ACCOUNT_FILE):
        raise HTTPException(status_code=404, detail="人工账本不存在")
    with open(MANUAL_ACCOUNT_FILE, "r", encoding="utf-8") as f:
        manual_data = json.load(f)
    with open(SYSTEM_ACCOUNT_FILE, "w", encoding="utf-8") as f:
        json.dump(manual_data, f, indent=4, ensure_ascii=False)
    return {"status": "success", "message": "已强制同步为人工账本状态"}


# ==========================================
# 2. 持仓与指令监控 (Positions & Orders APIs)
# ==========================================
@app.get("/api/v1/orders/today")
def get_recent_trades(limit: int = 50):
    if not os.path.exists(LIVE_LEDGER_FILE): return []
    try:
        df = pd.read_csv(LIVE_LEDGER_FILE)
        return df.tail(limit).iloc[::-1].fillna("").to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 3. 引擎启停控制 (Engine Control)
# ==========================================
@app.post("/api/v1/engine/run_once")
def run_live_engine():
    """一键触发实盘推演"""
    try:
        # 使用 subprocess 调用外部 python 脚本运行策略
        result = subprocess.run(
            ["python", LIVE_SCRIPT],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            return {"status": "success", "message": "引擎推演完成", "log_tail": result.stdout[-500:]}
        else:
            raise HTTPException(status_code=500, detail=f"引擎报错: {result.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))