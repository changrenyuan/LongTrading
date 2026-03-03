import os
import shutil
import pandas as pd
from data_provider.akshare_pd import AkShareProvider
from utils.logger import global_logger as logger


def test_akshare_provider():
    logger.info("🚀 开始测试 AkShare 数据接口...")
    print("-" * 50)

    # 1. 初始化 Provider，使用一个专门的测试缓存目录，避免污染正式数据
    test_cache_dir = "test_cache_data"
    provider = AkShareProvider(cache_dir=test_cache_dir)
    print(f"✅ 初始化成功，缓存目录设为: {test_cache_dir}")

    # 2. 测试获取全市场快照
    print("\n⏳ [测试 1/2] 正在获取全市场快照 (get_market_snapshot)...")
    try:
        snapshot_df = provider.get_market_snapshot()
        if not snapshot_df.empty:
            print(f"✅ 快照获取成功！共获取到 {len(snapshot_df)} 只股票的数据。")
            print("👉 数据前 3 行预览:")
            # 只打印关键列，防止终端刷屏
            if '代码' in snapshot_df.columns and '名称' in snapshot_df.columns:
                print(snapshot_df.head(3))
            else:
                print(snapshot_df.head(3))
        else:
            print("❌ 警告：获取到的快照为空 DataFrame！")
    except Exception as e:
        print(f"❌ 快照获取失败，错误信息: {e}")

    # 3. 测试获取个股历史数据 dc
    print("\n⏳ [测试 2/2] 正在获取个股日线数据 (get_data)...")
    test_symbols = ["000001", "600519"]  # 平安银行(深市), 贵州茅台(沪市)

    for symbol in test_symbols:
        try:
            print(f"正在拉取 {symbol} 的数据...")
            daily_df = provider.get_data(symbol)

            if not daily_df.empty:
                print(f"✅ {symbol} 获取成功！共 {len(daily_df)} 条记录。")
                print("👉 数据列名检查: ", list(daily_df.columns))
                print("👉 最近 2 天数据预览:")
                print(daily_df.tail(2))

                # 检查列名是否符合 base.py 的规范
                expected_columns = {'open', 'high', 'low', 'close', 'volume', 'turnover'}
                if expected_columns.issubset(set(daily_df.columns)):
                    print("✅ 列名规范检查通过！")
                else:
                    print(f"❌ 列名不符合规范！预期包含 {expected_columns}，实际为 {set(daily_df.columns)}")
            else:
                print(f"❌ 警告：获取到的 {symbol} 数据为空！")
        except Exception as e:
            print(f"❌ 获取 {symbol} 失败，错误信息: {e}")

    print("-" * 50)
    print("🎉 测试流程结束。")

    # 4. (可选) 清理测试产生的缓存文件
    # 如果你想查看缓存文件，可以注释掉下面两行
    # if os.path.exists(test_cache_dir):
    #     shutil.rmtree(test_cache_dir)
    #     print("🧹 已自动清理测试缓存目录。")


if __name__ == "__main__":
    test_akshare_provider()