import logging
import os,sys
import colorlog
from logging.handlers import RotatingFileHandler

def setup_logger(logger_name="MT_Alpha"):
    """
    初始化全局日志配置。
    规则：
    1. INFO 及以上级别的信息会打印在控制台（屏幕）。
    2. DEBUG 及以上级别的所有信息会保存在本地文件中。
    """
    # 确保日志文件夹存在
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, "trading_system.log")

    # 创建一个 Logger 实例
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)  # 设定最低捕获级别为 DEBUG

    # 如果 logger 已经有 handler，说明已经配置过，直接返回，防止重复打印
    if logger.handlers:
        return logger

    # 1. 配置文件输出 (保存到本地，单个文件最大 5MB，保留 3 个备份)
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    # 文件里的日志格式：时间 - 级别 - [文件名:行号] - 信息
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
    file_handler.setFormatter(file_formatter)

    # 2. 配置控制台输出 (打印到屏幕)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    # 屏幕上的日志格式简单一点：时间 - 级别 - 信息
    # console_formatter = logging.Formatter('%(asctime)s - %(levelname)s- [%(filename)s:%(lineno)d] - %(message)s')
    console_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(levelname)s- [%(filename)s:%(lineno)d] - %(message)s',
        log_colors={
            'DEBUG': 'cyan',  # 青色
            'INFO': 'green',  # 绿色 (看起来很安心)
            'WARNING': 'yellow',  # 黄色 (警告)
            'ERROR': 'red',  # 红色 (报错)
            'CRITICAL': 'bold_red',  # 加粗大红 (崩溃)
        }
    )
    console_handler.setFormatter(console_formatter)

    # 将两个 handler 挂载到 logger 上
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# 提供一个全局便捷实例，其他文件直接 import 这个全局变量即可
global_logger = setup_logger()