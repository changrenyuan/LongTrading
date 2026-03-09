import os
import json
import pandas as pd
from data_provider.cloudakpd import DataCenter  #
from data_provider.akshare_pd import AkShareProvider  #
from utils.logger import global_logger as logger  #

# 配置存储路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", "ops_test")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# 创建 K 线存储子目录
KLINE_DIR = os.path.join(DATA_DIR, "klines")
if not os.path.exists(KLINE_DIR):
    os.makedirs(KLINE_DIR)


def task_1_market_snapshot():
    """
    🎯 任务 1: 全市场快照审计
    """
    logger.info("🚀 启动任务 1: 同步当日市场全貌...")

    dc = DataCenter()
    # 同步云端数据
    dc.sync_market_snapshot()
    # 从云端获取快照
    df = dc.get_snapshot_from_cloud()

    if df.empty:
        logger.error("❌ 获取快照失败")
        return [], {}

    # 日期脱敏处理，防止 JSON 序列化 Timestamp 报错
    df_save = df.copy()
    for col in ['trade_date', 'updated_at']:
        if col in df_save.columns:
            df_save[col] = df_save[col].astype(str)

    # 1.2 筛选成交额 (amount) 最大的 5 支股票
    top_5_df = df.sort_values("amount", ascending=False).head(5)

    # 1.3 保存全貌 JSON
    snapshot_path = os.path.join(DATA_DIR, "market_snapshot.json")
    with open(snapshot_path, 'w', encoding='utf-8') as f:
        json.dump(df_save.to_dict(orient="records"), f, indent=4, ensure_ascii=False)

    # 构造返回结果：代码列表和名称映射
    symbols = top_5_df['symbol'].tolist()
    name_map = dict(zip(top_5_df['symbol'], top_5_df['name']))

    logger.info(f"✅ 任务 1 完成，提取核心标单: {name_map}")
    return symbols, name_map


def task_2_kline(symbols, name_map):
    """
    🎯 任务 2: 结构化分层存储 (一票一文)
    """
    logger.info(f"🚀 启动任务 2: 执行 {len(symbols)} 支票的结构化存盘...")

    provider = AkShareProvider()

    for i, sym in enumerate(symbols):
        # 1. 抓取 500 日 K 线
        df = provider.get_data(sym)
        if df.empty:
            continue

        # 截取最后 500 行，确保数据量统一
        df_500 = df.tail(500).copy()

        # 2. 🛠️ 修复：提取元数据并处理日期格式化
        # 使用 .iloc[-1] 避免 FutureWarning，并指定 strftime 格式
        try:
            if 'updated_at' in df_500.columns:
                last_update = df_500['updated_at'].iloc[-1]
                # 检查是否为时间对象，若是则格式化
                if hasattr(last_update, 'strftime'):
                    last_update_str = last_update.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    last_update_str = str(last_update)
            else:
                last_update_str = df_500.index[-1].strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            logger.warning(f"⚠️ 标的 {sym} 日期解析失败: {e}")
            last_update_str = "N/A"

        # 3. 🛠️ 核心结构化封装：元数据在顶层，序列在数组
        structured_data = {
            "symbol": sym,
            "name": name_map.get(sym, "未知"),
            "updated_at": last_update_str,
            "data_series": {
                "dates": df_500.index.strftime('%Y-%m-%d').tolist(),
                "open": df_500['open'].tolist(),
                "high": df_500['high'].tolist(),
                "low": df_500['low'].tolist(),
                "close": df_500['close'].tolist(),
                "volume": df_500['volume'].tolist(),
                "amount": df_500['amount'].tolist(),
                "turnover": df_500['turnover'].tolist() if 'turnover' in df_500.columns else []
            }
        }

        # 4. 物理落盘：一票一文
        file_path = os.path.join(KLINE_DIR, f"kline_{sym}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, indent=4, ensure_ascii=False)

        # 5. Logger 审计输出 (前两支股票预览)
        if i < 2:
            logger.info(f"📊 [审计] {sym}({structured_data['name']}) 存盘完成")
            logger.info(f"   ▫️ 最后更新: {last_update_str}")
            logger.info(f"   ▫️ 数据长度: {len(structured_data['data_series']['close'])} 日")
            # 打印最后 3 日价格核对
            print(f"   ▫️ 近3日收盘价: {structured_data['data_series']['close'][-3:]}")

    logger.info(f"✅ 任务 2 成功：K线文件已独立存入 {KLINE_DIR}")


if __name__ == "__main__":
    # 执行任务 1：获取代码及名称映射
    symbols, name_map = task_1_market_snapshot()

    # 执行任务 2：结构化抓取并存盘
    if symbols:
        task_2_kline(symbols, name_map)