from fastapi.testclient import TestClient
from api_server import app

# 实例化测试客户端
client = TestClient(app)


def test():
    print("====== 🚀 开始测试 WebUI API 引擎 V2 ======")

    # 1. 基础连通性测试
    print("\n[测试 1] 引擎 Ping 测试 (/)...")
    response = client.get("/")
    if response.status_code == 200:
        print("   ✅ 成功连接 API 总线！状态: ", response.json()["status"])
    else:
        print(f"   ❌ 连接失败，状态码: {response.status_code}")

    # 2. 双账本对账测试
    print("\n[测试 2] 获取双账本对账状态 (/api/v1/ledger/status)...")
    response = client.get("/api/v1/ledger/status")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ 读取成功！对账结论: {data.get('message')}")
    else:
        print(f"   ⚠️ 读取失败: {response.text}")

    # 3. 资产看板测试
    print("\n[测试 3] 获取宏观资产看板 (/api/v1/ledger/assets)...")
    response = client.get("/api/v1/ledger/assets")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ 读取成功！可用现金: {data.get('available_cash', 0):,.2f}")
    else:
        print(f"   ⚠️ 读取失败: {response.text}")

    # 4. 流水读取测试
    print("\n[测试 4] 获取近期实盘流水 (/api/v1/orders/today)...")
    response = client.get("/api/v1/orders/today")
    if response.status_code == 200:
        trades = response.json()
        print(f"   ✅ 读取成功！共提取到 {len(trades)} 条交易流水。")
    else:
        print(f"   ⚠️ 读取失败: {response.text}")

    print("\n====== 🏁 测试结束 ======")


if __name__ == "__main__":
    test()