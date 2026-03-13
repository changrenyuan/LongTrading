"""
回测数据路由
===========
"""
import os
import json
import subprocess
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/backtest", tags=["回测"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKTEST_DATA_DIR = os.path.join(BASE_DIR, "data", "backtest")
LIVE_SCRIPT = os.path.join(BASE_DIR, "live.py")


def load_backtest_json(filename: str):
    """通用JSON读取器"""
    path = os.path.join(BACKTEST_DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_json_by_strategy(strategy_id: str, filename: str):
    """支持动态路径的JSON读取器"""
    sid = strategy_id if strategy_id else "strategy_trend"
    path = os.path.join(BACKTEST_DATA_DIR, sid, filename)

    if not os.path.exists(path):
        fallback = os.path.join(BACKTEST_DATA_DIR, filename)
        if not os.path.exists(fallback):
            return []
        path = fallback

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/equity_curve")
def get_equity_curve(strategy_id: str = None):
    """获取权益曲线"""
    return load_json_by_strategy(strategy_id, "equity_curve.json")


@router.get("/drawdown")
def get_drawdown(strategy_id: str = None):
    """获取回撤曲线"""
    return load_json_by_strategy(strategy_id, "drawdown.json")


@router.get("/backtest_stocks")
def get_backtest_stocks():
    """获取回测股票列表"""
    return load_backtest_json("backtest_stocks.json")


@router.get("/kline_signals")
def get_kline_signals(symbol: str):
    """获取K线和信号"""
    data = load_backtest_json(f"kline_{symbol}.json")
    if not data:
        return {"symbol": symbol, "kline": [], "signals": []}
    return data


@router.get("/trades")
def get_backtest_trades():
    """获取交易记录"""
    return load_backtest_json("trades.json")


@router.get("/summary")
def get_backtest_summary():
    """获取回测汇总"""
    path = os.path.join(BASE_DIR, "data", "backtest", "summary.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# 引擎控制
@router.post("/engine/run_once")
def run_live_engine():
    """运行实盘引擎一次"""
    result = subprocess.run(["python", LIVE_SCRIPT], cwd=BASE_DIR,
                            capture_output=True, text=True, timeout=180)
    if result.returncode == 0:
        return {"status": "success"}
    from fastapi import HTTPException
    raise HTTPException(status_code=500, detail=f"引擎报错: {result.stderr}")
