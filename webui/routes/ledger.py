"""
账本路由
=======
"""
import os
import json
import pandas as pd
from fastapi import APIRouter, HTTPException

from live_exchage.universe import UniverseManager
from live_exchage.ledger import LedgerManager

router = APIRouter(prefix="/api/v1/ledger", tags=["账本"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SYSTEM_ACCOUNT_FILE = os.path.join(BASE_DIR, "data", "system_account.json")
MANUAL_ACCOUNT_FILE = os.path.join(BASE_DIR, "data", "live_broker_account.json")
LIVE_LEDGER_FILE = os.path.join(BASE_DIR, "data", "live_trade_ledger.csv")
PORTFOLIO_ASSETS_FILE = os.path.join(BASE_DIR, "data", "portfolio_assets.json")
DAILY_NAV_FILE = os.path.join(BASE_DIR, "data", "daily_nav.csv")


@router.get("/status")
def get_ledger_status():
    """对账接口：对比系统账本和人工账本"""
    sys_data, man_data = {"cash": 0.0, "pos": {}}, {"cash": 0.0, "pos": {}}

    if os.path.exists(SYSTEM_ACCOUNT_FILE):
        with open(SYSTEM_ACCOUNT_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            sys_data["cash"] = round(float(raw.get("available_cash", 0.0)), 2)
            sys_data["pos"] = {
                p['symbol']: (p['shares'], round(float(p.get('cost_price', 0)), 3))
                for p in raw.get('positions', [])
            }

    if os.path.exists(MANUAL_ACCOUNT_FILE):
        with open(MANUAL_ACCOUNT_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            man_data["cash"] = round(float(raw.get("available_cash", 0.0)), 2)
            man_data["pos"] = {
                p['symbol']: (p['shares'], round(float(p.get('cost_price', 0)), 3))
                for p in raw.get('positions', [])
            }

    cash_match = (sys_data["cash"] == man_data["cash"])
    pos_match = (sys_data["pos"] == man_data["pos"])
    is_match = cash_match and pos_match

    if is_match:
        return {"is_match": True, "message": "🟢 现金与持仓对账完全一致"}

    errors = []
    if not cash_match:
        errors.append(f"现金不符(系统:{sys_data['cash']} vs 人工:{man_data['cash']})")
    if not pos_match:
        errors.append("持仓细节不符")

    return {
        "is_match": False,
        "message": f"🔴 对账异常：{', '.join(errors)}",
        "details": {
            "cash_diff": round(sys_data["cash"] - man_data["cash"], 2),
            "sys_pos_count": len(sys_data["pos"]),
            "man_pos_count": len(man_data["pos"])
        }
    }


@router.get("/assets")
def get_portfolio_status():
    """获取资产状态"""
    default = {
        "available_cash": 0.0, "positions": [],
        "metrics": {"total_pnl": 0.0, "annualized_return": 0.0, "sharpe_ratio": 0.0,
                    "max_drawdown": 0.0, "calmar_ratio": 0.0},
        "pnl_summary": {"position_pnl": 0.0, "daily_pnl": 0.0, "daily_pnl_pct": 0.0}
    }
    try:
        if os.path.exists(PORTFOLIO_ASSETS_FILE):
            with open(PORTFOLIO_ASSETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        raise HTTPException(status_code=404, detail="资产审计文件未生成")
    except Exception:
        return default


@router.get("/nav_history")
def get_nav_history():
    """获取历史净值曲线"""
    if not os.path.exists(DAILY_NAV_FILE):
        return []

    try:
        df = pd.read_csv(DAILY_NAV_FILE)
        if df.empty:
            return []

        df = df.dropna(subset=['Date', 'Equity'])
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
        df = df.sort_values('Date').drop_duplicates('Date', keep='last')

        return df.rename(columns={'Date': 'date', 'Equity': 'equity'}).to_dict(orient='records')
    except Exception as e:
        print(f"提取净值历史失败: {e}")
        return []


@router.post("/manual_sync")
def sync_ledger():
    """手动同步账本"""
    try:
        um = UniverseManager()
        lm = LedgerManager()
        success = lm.sync_manual_to_system(um)

        if success:
            return {"status": "success", "message": "对账完成，数据已全量补全"}
        raise HTTPException(status_code=500, detail="对账模块执行失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
