import logging
import os, sys
import colorlog
from logging.handlers import RotatingFileHandler
from datetime import datetime  # 💡 引入时间模块


def setup_logger(logger_name="MT_Alpha"):
    """
    初始化全局日志配置。
    规则：
    1. INFO 及以上级别的信息会打印在控制台（屏幕）。
    2. DEBUG 及以上级别的所有信息会保存在本地文件中。
    3. 💡 动态日志命名：[入口文件名]_[YYYYMMDD].log
    """
    # 确保日志文件夹存在
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # ==========================================
    # 💡 核心修复：让日志拥有“名字”和“时间”烙印
    # ==========================================
    # 1. 自动抓取当前运行的入口 Python 脚本名称 (比如 "live_tradingv2.py" -> "live_tradingv2")
    try:
        entry_script_name = os.path.basename(sys.argv[0]).replace(".py", "")
        if not entry_script_name:
            entry_script_name = "unknown_process"
    except Exception:
        entry_script_name = "unknown_process"

    # 2. 获取今天的日期 (格式：20260303)
    today_str = datetime.now().strftime("%Y%m%d")

    # 3. 拼接出专属的日志文件名
    log_filename = f"{entry_script_name}_{today_str}.log"
    log_file = os.path.join(log_dir, log_filename)
    # ==========================================

    # 创建一个 Logger 实例
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)  # 设定最低捕获级别为 DEBUG

    # 如果 logger 已经有 handler，说明已经配置过，直接返回，防止重复打印
    if logger.handlers:
        return logger

    # 1. 配置文件输出 (保存到本地，单个文件最大 5MB，保留 3 个备份)
    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    # 文件里的日志格式：时间 - 级别 - [文件名:行号] - 信息
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
    file_handler.setFormatter(file_formatter)

    # 2. 配置控制台输出 (打印到屏幕)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    console_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(levelname)s- [%(filename)s:%(lineno)d] - %(message)s',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    )
    console_handler.setFormatter(console_formatter)

    # 将两个 handler 挂载到 logger 上
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# 提供一个全局便捷实例，其他文件直接 import 这个全局变量即可
global_logger = setup_logger()