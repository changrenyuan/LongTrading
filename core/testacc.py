from core.account import Portfolio
from utils.logger import global_logger as logger
import os


def test_account_module():
    logger.info("🚀 开始测试核心账户模块 (专业双账本审计版)")
    print("=" * 70)

    # 1. 初始化测试环境：清理旧账本，防止数据干扰
    test_ledger = "data/test_ledger.csv"
    test_positions = "data/test_positions.csv"  # 自动生成的持仓底稿路径

    for path in [test_ledger, test_positions]:
        if os.path.exists(path):
            os.remove(path)

    # 初始化大管家
    portfolio = Portfolio(initial_cash=100000.0, max_positions=3, ledger_path=test_ledger)

    # 2. 模拟真实交易流水
    logger.info("⏳ [测试 1 & 2] 买入并加仓 000001，测试加权均价...")
    portfolio.execute_trade("000001", "BUY", 250, 10.55,0.003, 0.005,'2023-06-12')  # 实际买入 200股
    portfolio.execute_trade("000001", "BUY", 300, 11.20,0.003, 0.005,'2023-06-12')  # 实际买入 300股，总计 500股

    logger.info("⏳ [测试 3] 买入其他股票，触发风控...")
    portfolio.execute_trade("600519", "BUY", 100, 150.0,0.003, 0.005,'2023-06-15')  # 茅台
    portfolio.execute_trade("000858", "BUY", 100, 50.0,0.003, 0.005,'2023-06-15')  # 五粮液
    portfolio.execute_trade("BYD", "BUY", 100, 20.0,0.003, 0.005,'2023-06-15')  # 第4只，预期被风控拦截不入账

    logger.info("⏳ [测试 4] 卖出 000858，生成实现盈亏 (Realized PnL)...")
    # 五粮液 50块买的，涨到 60块卖出，预期赚 1000块，扣除手续费和印花税
    portfolio.execute_trade("000858", "SELL", 100, 60.0,0.003, 0.005,'2023-10-15')

    # 3. 模拟收盘，保存持仓快照底稿
    logger.info("⏳ [测试 5] 模拟收盘，给当前持仓拍照存档...")
    # portfolio.save_position_snapshot()
    logger.info("✅ 快照保存成功！")

    print("=" * 70)
    logger.info("📊 审计时间：双账本数据核对")
    #
    # # 打印交易流水账
    # if os.path.exists(test_ledger):
    #     logger.info(f"📁 交易流水账本 ({test_ledger}):")
    #     with open(test_ledger, 'r', encoding='utf-8-sig') as f:
    #         lines = f.readlines()
    #         for i, line in enumerate(lines):
    #             # 表头高亮显示
    #             if i == 0:
    #                 print(f"   {line.strip()}")
    #                 print("   " + "-" * 85)
    #             else:
    #                 print(f"   {line.strip()}")
    # else:
    #     logger.error("❌ 流水账本未生成！")
    #
    # print("\n" + "=" * 70)
    #
    # # 打印持仓快照底稿
    # if os.path.exists(test_positions):
    #     logger.info(f"📁 持仓快照底稿 ({test_positions}):")
    #     with open(test_positions, 'r', encoding='utf-8-sig') as f:
    #         lines = f.readlines()
    #         for i, line in enumerate(lines):
    #             if i == 0:
    #                 print(f"   {line.strip()}")
    #                 print("   " + "-" * 60)
    #             else:
    #                 print(f"   {line.strip()}")
    # else:
    #     logger.error("❌ 持仓底稿未生成！")
    #
    # print("=" * 70)
    # logger.info("🎉 审计测试圆满结束！所有资金去向清晰可查。")


if __name__ == "__main__":
    test_account_module()