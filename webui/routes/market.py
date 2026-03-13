"""
市场状态路由
===========
"""
import os
import json
import aiofiles
from fastapi import APIRouter, BackgroundTasks
from utils.time import update_market_status_json

router = APIRouter(prefix="/api/v1/market", tags=["市场"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MARKET_STATUS_FILE = os.path.join(BASE_DIR, "data", "market_status.json")


@router.get("/status")
async def get_market_status(background_tasks: BackgroundTasks):
    """
    异步读取市场状态快照
    同时在后台静默触发一次数据刷新
    """
    if not os.path.exists(MARKET_STATUS_FILE):
        update_market_status_json(MARKET_STATUS_FILE)

    try:
        async with aiofiles.open(MARKET_STATUS_FILE, mode='r', encoding='utf-8') as f:
            content = await f.read()
            data = json.loads(content)

        background_tasks.add_task(update_market_status_json, MARKET_STATUS_FILE)
        return data
    except Exception as e:
        return {"error": f"读取快照失败: {str(e)}"}
