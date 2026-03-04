import logging
from utils.notifier import MessagePusher, NotificationLevel

# 配置基础的控制台打印，方便测试观察
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def test():
    print("====== 🚀 开始测试推送模块 ======")
    print("提示：系统将自动读取根目录下的 .env 配置文件\n")

    pusher = MessagePusher()

    # 1. 测试普通日志信息
    title_info = "MT_Alpha 实盘警报123"
    content_info = "老板您好，这是一条来自量化实盘系统的常规测试消息！\n当前可用资金：10,000,000.00\n策略模块运行正常。"
    print("\n[测试 1] 发送 INFO 级别消息...")
    pusher.push_message(title_info, content_info, level=NotificationLevel.INFO)

    # 2. 测试紧急错误拦截
    title_crit = "对账失败拦截123"
    content_crit = "系统预期应有 1000 股，真实账本 0 股。\n🚨 已触发回退防守机制！"
    print("\n[测试 2] 发送 CRITICAL 级别消息...")
    pusher.push_message(title_crit, content_crit, level=NotificationLevel.CRITICAL)

    print("\n====== 🏁 测试结束 ======")


if __name__ == "__main__":
    test()