"""
MT_Alpha API 服务器
==================
FastAPI 主入口，整合各路由模块
"""
import os
import json
import pandas as pd
from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware
from webui.routes import market_router, ledger_router, backtest_router, debug_router

# ==================== 应用初始化 ====================

app = FastAPI(title="MT_Alpha 核心数据总线", version="1.0.0")

# CORS 配置
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://your-domain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(market_router)
app.include_router(ledger_router)
app.include_router(backtest_router)
app.include_router(debug_router)

# ==================== 基础接口 ====================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIVERSE_POOL_FILE = os.path.join(BASE_DIR, "data", "universe_pool.json")
STRATEGY_CONFIG_FILE = os.path.join(BASE_DIR, "data", "best_params_win50p.json")
LIVE_LEDGER_FILE = os.path.join(BASE_DIR, "data", "live_trade_ledger.csv")


@app.get("/")
def ping():
    """健康检查"""
    return {"status": "ok"}


# ==================== 股票池接口 ====================

@app.get("/api/v1/universe/pool")
def get_universe_pool():
    """获取股票池"""
    if not os.path.exists(UNIVERSE_POOL_FILE):
        return []
    with open(UNIVERSE_POOL_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ==================== 策略参数接口 ====================

@app.get("/api/v1/strategy/params")
def get_params():
    """获取策略参数"""
    if not os.path.exists(STRATEGY_CONFIG_FILE):
        return {}
    with open(STRATEGY_CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/v1/strategy/params")
def update_params(new_params: dict):
    """更新策略参数"""
    try:
        with open(STRATEGY_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(new_params, f, indent=4, ensure_ascii=False)
        return {"status": "success"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 订单接口 ====================

@app.get("/api/v1/orders/today")
def get_recent_trades(limit: int = 50):
    """获取今日成交"""
    if not os.path.exists(LIVE_LEDGER_FILE):
        return []
    try:
        df = pd.read_csv(LIVE_LEDGER_FILE, dtype=str).fillna("")
        return df.tail(limit).iloc[::-1].to_dict(orient="records")
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))
