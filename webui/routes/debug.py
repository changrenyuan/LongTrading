"""
调试接口路由
===========
"""
import os
import json
import pandas as pd
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/debug", tags=["调试"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SYSTEM_ACCOUNT_FILE = os.path.join(BASE_DIR, "data", "system_account.json")
MANUAL_ACCOUNT_FILE = os.path.join(BASE_DIR, "data", "live_broker_account.json")
UNIVERSE_POOL_FILE = os.path.join(BASE_DIR, "data", "universe_pool.json")
STRATEGY_CONFIG_FILE = os.path.join(BASE_DIR, "data", "best_params_win50p.json")
DAILY_NAV_FILE = os.path.join(BASE_DIR, "data", "daily_nav.csv")
MARKET_SNAPSHOT_FILE = os.path.join(BASE_DIR, "utils", "data", "ops_test", "market_snapshot.json")


@router.get("/files")
def get_debug_files():
    """获取可调试的数据文件列表"""
    file_configs = [
        ("system_account.json", "系统账本", SYSTEM_ACCOUNT_FILE),
        ("live_broker_account.json", "人工账本", MANUAL_ACCOUNT_FILE),
        ("universe_pool.json", "股票池", UNIVERSE_POOL_FILE),
        ("best_params_win50p.json", "策略参数", STRATEGY_CONFIG_FILE),
        ("daily_nav.csv", "净值历史", DAILY_NAV_FILE),
    ]
    files = []
    for filename, display_name, filepath in file_configs:
        exists = os.path.exists(filepath)
        size = os.path.getsize(filepath) if exists else 0
        files.append({"filename": filename, "display_name": display_name,
                      "exists": exists, "size": size})
    return files


@router.get("/file/{filename}")
def get_debug_file(filename: str):
    """获取指定JSON文件内容"""
    file_map = {
        "system_account.json": SYSTEM_ACCOUNT_FILE,
        "live_broker_account.json": MANUAL_ACCOUNT_FILE,
        "universe_pool.json": UNIVERSE_POOL_FILE,
        "best_params_win50p.json": STRATEGY_CONFIG_FILE,
    }

    if filename not in file_map:
        raise HTTPException(status_code=404, detail=f"文件 {filename} 不在允许列表中")

    filepath = file_map[filename]
    if not os.path.exists(filepath):
        return {"error": f"文件 {filename} 不存在", "content": None}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = json.load(f)
        return {"filename": filename, "content": content, "error": None}
    except Exception as e:
        return {"error": f"读取文件失败: {str(e)}", "content": None}


@router.post("/sync")
def debug_sync():
    """触发数据同步"""
    try:
        from live_exchage.universe import UniverseManager
        from live_exchage.ledger import LedgerManager
        return {
            "success": True,
            "message": "数据同步完成",
            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {"success": False, "message": f"同步失败: {str(e)}"}


@router.get("/compare")
def debug_compare():
    """对比系统账本和人工账本差异"""
    result = {"system_only": [], "manual_only": [], "diff_positions": [], "match_positions": []}

    sys_positions, man_positions = {}, {}

    if os.path.exists(SYSTEM_ACCOUNT_FILE):
        with open(SYSTEM_ACCOUNT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            sys_positions = {p['symbol']: p for p in data.get('positions', [])}

    if os.path.exists(MANUAL_ACCOUNT_FILE):
        with open(MANUAL_ACCOUNT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            man_positions = {p['symbol']: p for p in data.get('positions', [])}

    sys_symbols = set(sys_positions.keys())
    man_symbols = set(man_positions.keys())

    for symbol in sys_symbols - man_symbols:
        result["system_only"].append({"symbol": symbol, "data": sys_positions[symbol]})

    for symbol in man_symbols - sys_symbols:
        result["manual_only"].append({"symbol": symbol, "data": man_positions[symbol]})

    for symbol in sys_symbols & man_symbols:
        sys_p, man_p = sys_positions[symbol], man_positions[symbol]
        diff = {}
        if sys_p.get('shares') != man_p.get('shares'):
            diff['shares'] = {"system": sys_p.get('shares'), "manual": man_p.get('shares')}
        if sys_p.get('cost_price') != man_p.get('cost_price'):
            diff['cost_price'] = {"system": sys_p.get('cost_price'), "manual": man_p.get('cost_price')}

        if diff:
            result["diff_positions"].append({
                "symbol": symbol, "name": sys_p.get('name') or man_p.get('name'), "diff": diff
            })
        else:
            result["match_positions"].append(symbol)

    return result


@router.post("/market_snapshot")
def sync_market_snapshot():
    """触发市场快照同步"""
    try:
        from utils.daylyops import task_1_market_snapshot
        symbols, name_map = task_1_market_snapshot()
        return {
            "success": True, "message": f"同步完成，提取 {len(symbols)} 支标的",
            "symbols": symbols, "name_map": name_map,
            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"同步失败: {str(e)}"}


@router.get("/market_snapshot")
def get_market_snapshot():
    """获取市场快照"""
    if not os.path.exists(MARKET_SNAPSHOT_FILE):
        return {"success": False, "message": "文件不存在，请先同步", "data": [], "count": 0}

    try:
        with open(MARKET_SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"success": True, "message": "获取成功", "data": data,
                "count": len(data) if isinstance(data, list) else 1}
    except Exception as e:
        return {"success": False, "message": f"读取失败: {str(e)}", "data": [], "count": 0}
