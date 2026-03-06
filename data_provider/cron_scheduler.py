import sys
import os
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler

# 💡 强制把项目根目录加入路径，防止 ModuleNotFoundError
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_provider.cloudakpd import DataCenter
from utils.logger import global_logger as logger


def auto_sync_job():
    """值班员的核心工作"""
    logger.info(f"🔔 定时任务启动：开始执行全市场快照审计...")
    try:
        dc = DataCenter()
        if dc.sync_market_snapshot(refresh_interval_hours=1):
            logger.info("🎉 数据存盘操作已确认，云端状态同步完成。")
        else:
            logger.warning("⚠️ 同步逻辑已运行，但未产生新的物理写入（可能已是最新状态）。")
    except Exception as e:
        logger.error(f"❌ 自动值班过程发生崩溃: {e}")


if __name__ == "__main__":
    scheduler = BlockingScheduler()

    # 每天周一到周五：10:30 (早盘), 13:30 (午后), 15:45 (收盘定格)
    scheduler.add_job(auto_sync_job, 'cron', day_of_week='mon-fri', hour=10, minute=30)
    scheduler.add_job(auto_sync_job, 'cron', day_of_week='mon-fri', hour=13, minute=30)
    scheduler.add_job(auto_sync_job, 'cron', day_of_week='mon-fri', hour=15, minute=45)

    logger.info("🚀 MT_ALPHA 自动化值班系统已上岗。")
    logger.info("⏰ 预定巡检时间: 10:30 | 13:30 | 15:45")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 值班系统已安全下岗。")