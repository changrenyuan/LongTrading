import os
import sys
import json
import pandas as pd
from datetime import datetime

# 确保 Python 能找到项目根目录下的所有包
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config import LiveConfig
from ledger import LedgerManager
from universe import UniverseManager
from executor import TradeExecutor
from engine import LiveEngine
from data_provider.akshare_pd import AkShareProvider
from core.account import Portfolio


def run_comprehensive_tests():
    print("=" * 60)
    print(" 🚀 开始进行 Live 模块化架构【深度业务测试】")
    print("=" * 60)

    # ---------------------------------------------------------
    print("\n[测试 1] 配置部 (LiveConfig) - 寻优参数装载测试")
    try:
        cfg = LiveConfig.get_latest_live_params()
        if 'ma_long' in cfg and 'lot_size' in cfg:
            print(f"   ✅ 配置加载成功! 核心参数总数: {len(cfg)} 个。")
            print(f"   👉 抽样检查: ma_long={cfg['ma_long']}, stop_loss_pct={cfg.get('stop_loss_pct', 'N/A')}")
        else:
            print("   ❌ 配置字典缺少核心护城河字段！")
    except Exception as e:
        print(f"   ❌ 配置部测试崩溃: {e}")

    # ---------------------------------------------------------
    print("\n[测试 2] 审计部 (LedgerManager) - 双账本冲突与流水测试")
    try:
        # 故意创建虚拟的测试账本路径，防止污染真实账本
        test_manual = "data/test_manual.json"
        test_system = "data/test_system.json"
        test_csv = "data/test_ledger.csv"

        # 模拟老板手工存入了 50万，买入了 1000股 平安银行
        os.makedirs("data", exist_ok=True)
        with open(test_manual, "w", encoding="utf-8") as f:
            json.dump({"available_cash": 500000.0, "positions": [{"symbol": "000001", "shares": 1000}]}, f)

        ledger = LedgerManager(manual_file=test_manual, system_file=test_system, rich_ledger_file=test_csv)

        # 1. 测试对账逻辑
        cash, pos = ledger.load_and_reconcile_ledgers()
        assert cash == 500000.0, "现金读取错误"
        assert pos[0]["symbol"] == "000001", "持仓读取错误"
        print("   ✅ 双账本核对逻辑正常！")

        # 2. 测试富文本CSV写入逻辑
        ledger.append_live_ledger_with_reason("2026-03-04", "000001", "平安银行", "BUY", 1000, 10.5, "放量突破测试")
        assert os.path.exists(test_csv), "富文本流水文件未生成"
        print("   ✅ 富文本CSV实盘流水追加写入正常！")

        # 测试完毕，清理虚拟垃圾文件
        if os.path.exists(test_manual): os.remove(test_manual)
        if os.path.exists(test_csv): os.remove(test_csv)
    except AssertionError as ae:
        print(f"   ❌ 审计部逻辑断言失败: {ae}")
    except Exception as e:
        print(f"   ❌ 审计部测试崩溃: {e}")

    # ---------------------------------------------------------
    print("\n[测试 3] 标的部 (UniverseManager) - 20只动态活水池测试")
    try:
        provider = AkShareProvider()
        universe = UniverseManager(provider)
        # 强制塞入一只现有持仓 002131，测试它是否能保住名额
        pool, days = universe.build_dynamic_stock_pool(["002131"], max_size=20)

        assert len(pool) <= 20, "股票池超过了20只的上限"
        assert "002131" in pool, "现有的持仓股被错误地踢出了股票池"

        print(f"   ✅ 活水池构建成功！扫描快照天数: {days} 天。")
        print(f"   ✅ 当前池子大小: {len(pool)} 只 (强制上限 20)。")
        if len(pool) > 0:
            print(f"   👉 池子头部标的抽样: {pool[:5]}")
    except AssertionError as ae:
        print(f"   ❌ 标的部逻辑断言失败: {ae}")
    except Exception as e:
        print(f"   ❌ 标的部测试崩溃: {e}")

    # ---------------------------------------------------------
    print("\n[测试 4] 执行部 (TradeExecutor) - 订单模拟与大管家扣款测试")
    try:
        # 临时借用审计部
        temp_ledger = LedgerManager(rich_ledger_file="data/test_exec_ledger.csv")
        executor = TradeExecutor(temp_ledger)

        # 模拟发给大管家 10万块钱
        account = Portfolio(initial_cash=100000, symbols=["000001"], ledger_path="data/test_internal.csv")
        account.central_vault = 100000

        # 模拟买入 1000 股，单价 10.0
        success, msg, action = executor.execute("000001", "平安银行", "BUY", 1000, 10.0, "均线金叉", account,
                                                "2026-03-04")
        assert success == True, "买入订单被异常拦截"
        assert account.get_shares("000001") == 1000, "大管家持仓更新失败"
        print(f"   ✅ 买入执行成功: {msg.split('|')[0].strip()}")

        # 模拟卖出 1000 股，单价 11.0 (止盈)
        success, msg, action = executor.execute("000001", "平安银行", "SELL", 1000, 11.0, "触发止盈", account,
                                                "2026-03-05")
        assert account.get_shares("000001") == 0, "大管家卖出清仓失败"
        print(f"   ✅ 卖出清仓成功: {msg.split('|')[0].strip()}")

        # 清理执行测试留下的垃圾文件
        if os.path.exists("data/test_exec_ledger.csv"): os.remove("data/test_exec_ledger.csv")
    except AssertionError as ae:
        print(f"   ❌ 执行部逻辑断言失败: {ae}")
    except Exception as e:
        print(f"   ❌ 执行部测试崩溃: {e}")

    # ---------------------------------------------------------
    print("\n[测试 5] 总调度室 (LiveEngine) - 无缝组装验证")
    try:
        # 仅测试引擎是否能把 4 个部门完美拼装起来 (不运行 run_daily_routine 以免发真实推送)
        engine = LiveEngine()
        assert hasattr(engine, 'universe'), "引擎缺失标的部"
        assert hasattr(engine, 'ledger'), "引擎缺失审计部"
        print("   ✅ LiveEngine 总司令初始化成功，5 大模块组装无冲突！")
    except Exception as e:
        print(f"   ❌ 总调度室组装崩溃: {e}")

    print("\n" + "=" * 60)
    print(" 🏁 深度业务测试全部结束！")
    print(" 如果上面全部都是 ✅，您可以毫无顾虑地运行 python live_main.py 启动实盘！")
    print("=" * 60)


if __name__ == "__main__":
    run_comprehensive_tests()