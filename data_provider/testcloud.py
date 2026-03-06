from data_provider.cloudakpd import DataCenter
from utils.logger import global_logger as logger


def test_mechanism():
    # 1. 初始化 (现在会自动识别 Postgres 补全 updated_at 字段)
    dc = DataCenter()

    # 2. 获取判定状态
    dt, is_closed = dc.get_real_trade_date_info()
    status_msg = "收盘定格" if is_closed else "盘中实时"
    logger.info(f"🚀 测试启动: 目标日期 {dt} | 判定状态: {status_msg}")

    # 3. 运行同步 (内部包含 1小时刷新校验)
    if dc.sync_market_snapshot(refresh_interval_hours=1):
        # 4. 验证读取
        df = dc.get_snapshot_from_cloud(dt)
        if not df.empty:
            logger.info("✅ 冒烟测试完美通过！")
            logger.info(f"   ▫️ 数据库日期: {df['trade_date'].iloc[0]}")
            logger.info(f"   ▫️ 存入时间戳: {df['updated_at'].iloc[0]}")
        else:
            logger.error("❌ 数据库提取异常。")
    else:
        logger.error("❌ 同步环节发生错误，请检查日志。")


if __name__ == "__main__":
    test_mechanism()