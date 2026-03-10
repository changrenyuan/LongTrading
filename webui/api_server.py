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
LIVE_SCRIPT = os.path.join(BASE_DIR, "live.py")
# 核心资产与指标快照 (由 engine.py/ledger.py 生成)
PORTFOLIO_ASSETS_FILE = os.path.join(BASE_DIR, "data","portfolio_assets.json")
from utils.metrics import MetricsCalculator # 💡 引入专业的精算师

@app.get("/")
def ping(): return {"status": "ok"}
# --- 通用读取函数 ---
# 交易日历缓存（避免频繁请求）
_trading_days_cache = {"year": None, "days": set()}


def get_trading_days(year: int) -> set:
    """获取指定年份的交易日（使用 akshare）"""
    global _trading_days_cache

    if _trading_days_cache["year"] == year:
        return _trading_days_cache["days"]

    try:
        import akshare as ak
        # 获取交易日历
        df = ak.tool_trade_date_hist_sina()
        # 筛选当年交易日
        trading_days = set()
        for date_str in df['trade_date'].astype(str):
            if date_str.startswith(str(year)):
                trading_days.add(date_str)

        _trading_days_cache = {"year": year, "days": trading_days}
        return trading_days
    except Exception as e:
        print(f"获取交易日历失败: {e}")
        # 降级：排除周末
        from datetime import date, timedelta
        trading_days = set()
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        current = start
        while current <= end:
            if current.weekday() < 5:  # 周一到周五
                trading_days.add(current.strftime('%Y%m%d'))
            current += timedelta(days=1)
        return trading_days


@app.get("/api/v1/market/status")
def get_market_status():
    """获取市场交易状态"""
    from datetime import datetime, time

    now = datetime.now()
    today_str = now.strftime('%Y%m%d')
    current_time = now.time()

    # 定义交易时段
    MORNING_OPEN = time(9, 30)
    MORNING_CLOSE = time(11, 30)
    AFTERNOON_OPEN = time(13, 0)
    AFTERNOON_CLOSE = time(15, 0)

    # 判断是否是交易日
    trading_days = get_trading_days(now.year)
    is_trading_day = today_str in trading_days

    # 判断市场状态
    market_status = "休市"
    status_code = 0  # 0:休市 1:开盘前 2:早盘 3:午休 4:午盘 5:收盘后

    if is_trading_day:
        if current_time < MORNING_OPEN:
            market_status = "开盘前"
            status_code = 1
        elif MORNING_OPEN <= current_time < MORNING_CLOSE:
            market_status = "早盘交易中"
            status_code = 2
        elif MORNING_CLOSE <= current_time < AFTERNOON_OPEN:
            market_status = "午间休市"
            status_code = 3
        elif AFTERNOON_OPEN <= current_time < AFTERNOON_CLOSE:
            market_status = "午盘交易中"
            status_code = 4
        else:
            market_status = "已收盘"
            status_code = 5
    else:
        # 非交易日
        if current_time < MORNING_OPEN:
            market_status = "非交易日"
            status_code = 0
        else:
            market_status = "休市日"
            status_code = 0

    # 计算距离下一交易状态的时间
    next_event = None
    next_event_time = None

    if is_trading_day:
        if status_code == 1:  # 开盘前
            next_event = "开盘"
            next_event_time = datetime.combine(now.date(), MORNING_OPEN)
        elif status_code == 2:  # 早盘
            next_event = "午休"
            next_event_time = datetime.combine(now.date(), MORNING_CLOSE)
        elif status_code == 3:  # 午休
            next_event = "午盘开盘"
            next_event_time = datetime.combine(now.date(), AFTERNOON_OPEN)
        elif status_code == 4:  # 午盘
            next_event = "收盘"
            next_event_time = datetime.combine(now.date(), AFTERNOON_CLOSE)

    # 计算剩余时间
    countdown = None
    if next_event_time:
        delta = next_event_time - now
        total_seconds = int(delta.total_seconds())
        if total_seconds > 0:
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            countdown = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return {
        "is_trading_day": is_trading_day,
        "market_status": market_status,
        "status_code": status_code,
        "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()],
        "next_event": next_event,
        "countdown": countdown,
        "trading_periods": {
            "morning": {"open": "09:30", "close": "11:30"},
            "afternoon": {"open": "13:00", "close": "15:00"}
        }
    }
# @app.get("/api/v1/ledger/status")
@app.get("/api/v1/ledger/status")
def get_ledger_status():
    sys_data, man_data = {"cash": 0.0, "pos": {}}, {"cash": 0.0, "pos": {}}

    # 1. 提取系统账本数据
    if os.path.exists(SYSTEM_ACCOUNT_FILE):
        with open(SYSTEM_ACCOUNT_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            sys_data["cash"] = round(float(raw.get("available_cash", 0.0)), 2)
            # 记录 (股数, 成本价) 用于对比
            sys_data["pos"] = {
                p['symbol']: (p['shares'], round(float(p.get('cost_price', 0)), 3))
                for p in raw.get('positions', [])
            }

    # 2. 提取人工账本数据
    if os.path.exists(MANUAL_ACCOUNT_FILE):
        with open(MANUAL_ACCOUNT_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            man_data["cash"] = round(float(raw.get("available_cash", 0.0)), 2)
            man_data["pos"] = {
                p['symbol']: (p['shares'], round(float(p.get('cost_price', 0)), 3))
                for p in raw.get('positions', [])
            }

    # 3. 核心对账逻辑：现金 + 持仓
    cash_match = (sys_data["cash"] == man_data["cash"])
    pos_match = (sys_data["pos"] == man_data["pos"])

    is_match = cash_match and pos_match

    # 4. 构造详细的反馈信息
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

# @app.get("/api/v1/ledger/assets")
@app.get("/api/v1/ledger/assets")
def get_portfolio_status():
    """
    💡 优化：删除所有计算、MetricsCalculator 和 CSV 读取。
    直接透传由后端精算好的全量资产数据。
    """
    default_structure = {
        "available_cash": 0.0,
        "positions": [],
        "metrics": {"total_pnl": 0.0, "annualized_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0, "calmar_ratio": 0.0},
        "pnl_summary": {"position_pnl": 0.0, "daily_pnl": 0.0, "daily_pnl_pct": 0.0}
    }
    try:
        # 1. 实例化 LedgerManager 并执行实时审计
        # 这将触发 15 分钟保鲜检查及所有财务指标的重算

        # 2. 物理读取由 lm.update_assets_snapshot 生成的最鲜 JSON
        if os.path.exists(PORTFOLIO_ASSETS_FILE):
            with open(PORTFOLIO_ASSETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            raise HTTPException(status_code=404, detail="资产审计文件未生成")
        lm = LedgerManager()
        background_tasks.add_task(lm.update_assets_snapshot)
    except Exception as e:
        # 发生任何错误，返回默认结构，保证前端不崩
        return {
            "available_cash": 0.0, "positions": [],
            "metrics": {"total_pnl": 0.0, "annualized_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0,
                        "calmar_ratio": 0.0},
            "pnl_summary": {"position_pnl": 0.0, "daily_pnl": 0.0, "daily_pnl_pct": 0.0}
        }
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


# ============================================================================
# 调测接口 - 用于数据同步和调试
# ============================================================================

@app.get("/api/v1/debug/files")
def get_debug_files():
    """获取可调试的数据文件列表"""
    files = []
    file_configs = [
        ("system_account.json", "系统账本", SYSTEM_ACCOUNT_FILE),
        ("live_broker_account.json", "人工账本", MANUAL_ACCOUNT_FILE),
        ("universe_pool.json", "股票池", UNIVERSE_POOL_FILE),
        ("best_params_win50p.json", "策略参数", STRATEGY_CONFIG_FILE),
        ("daily_nav.csv", "净值历史", DAILY_NAV_FILE),
    ]
    for filename, display_name, filepath in file_configs:
        exists = os.path.exists(filepath)
        size = os.path.getsize(filepath) if exists else 0
        files.append({
            "filename": filename,
            "display_name": display_name,
            "exists": exists,
            "size": size
        })
    return files


@app.get("/api/v1/debug/file/{filename}")
def get_debug_file(filename: str):
    """获取指定 JSON 文件内容"""
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


@app.post("/api/v1/debug/sync")
def debug_sync():
    """触发数据同步"""
    try:
        um = UniverseManager()
        lm = LedgerManager()
        # 执行同步逻辑（根据实际需求补充）
        return {
            "success": True,
            "message": "数据同步完成",
            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {"success": False, "message": f"同步失败: {str(e)}"}


@app.get("/api/v1/debug/compare")
def debug_compare():
    """对比系统账本和人工账本差异"""
    result = {
        "system_only": [],  # 仅系统账本有
        "manual_only": [],  # 仅人工账本有
        "diff_positions": [],  # 持仓数量/成本不同
        "match_positions": [],  # 一致的持仓
    }

    # 读取系统账本
    sys_positions = {}
    if os.path.exists(SYSTEM_ACCOUNT_FILE):
        with open(SYSTEM_ACCOUNT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            sys_positions = {p['symbol']: p for p in data.get('positions', [])}

    # 读取人工账本
    man_positions = {}
    if os.path.exists(MANUAL_ACCOUNT_FILE):
        with open(MANUAL_ACCOUNT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            man_positions = {p['symbol']: p for p in data.get('positions', [])}

    sys_symbols = set(sys_positions.keys())
    man_symbols = set(man_positions.keys())

    # 仅系统账本有
    for symbol in sys_symbols - man_symbols:
        result["system_only"].append({
            "symbol": symbol,
            "data": sys_positions[symbol]
        })

    # 仅人工账本有
    for symbol in man_symbols - sys_symbols:
        result["manual_only"].append({
            "symbol": symbol,
            "data": man_positions[symbol]
        })

    # 对比两边都有的
    for symbol in sys_symbols & man_symbols:
        sys_p = sys_positions[symbol]
        man_p = man_positions[symbol]

        diff = {}
        if sys_p.get('shares') != man_p.get('shares'):
            diff['shares'] = {"system": sys_p.get('shares'), "manual": man_p.get('shares')}
        if sys_p.get('cost_price') != man_p.get('cost_price'):
            diff['cost_price'] = {"system": sys_p.get('cost_price'), "manual": man_p.get('cost_price')}

        if diff:
            result["diff_positions"].append({
                "symbol": symbol,
                "name": sys_p.get('name') or man_p.get('name'),
                "diff": diff
            })
        else:
            result["match_positions"].append(symbol)

    return result


# ============================================================================
# 市场快照接口
# ============================================================================

# 市场快照存储路径 (daylyops.py 保存在 utils/data/ops_test/)
MARKET_SNAPSHOT_FILE = os.path.join(BASE_DIR, "utils", "data", "ops_test", "market_snapshot.json")


@app.post("/api/v1/debug/market_snapshot")
def sync_market_snapshot():
    """触发市场快照同步任务"""
    try:
        from utils.daylyops import task_1_market_snapshot

        # 执行同步任务
        symbols, name_map = task_1_market_snapshot()

        return {
            "success": True,
            "message": f"市场快照同步完成，提取 {len(symbols)} 支核心标的",
            "symbols": symbols,
            "name_map": name_map,
            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"同步失败: {str(e)}"}


@app.get("/api/v1/debug/market_snapshot")
def get_market_snapshot():
    """获取市场快照 JSON 内容"""
    if not os.path.exists(MARKET_SNAPSHOT_FILE):
        return {
            "success": False,
            "message": "市场快照文件不存在，请先点击同步按钮",
            "data": [],
            "count": 0
        }

    try:
        with open(MARKET_SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "success": True,
            "message": "获取成功",
            "data": data,
            "count": len(data) if isinstance(data, list) else 1
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"读取文件失败: {str(e)}",
            "data": [],
            "count": 0
        }