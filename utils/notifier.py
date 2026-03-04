import os
import re
import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
import logging
from enum import Enum
from dotenv import load_dotenv
# 加载 .env 文件中的环境变量
load_dotenv()


class NotificationLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MessagePusher:
    """
    统一消息推送模块 (同步版，专为实盘脚本优化)
    支持 Telegram (自动读取系统代理) 和 钉钉 Webhook
    配置信息通过 .env 文件读取
    """

    def __init__(self):
        # 如果您的项目中已经有了 global_logger，建议换成 from utils.logger import global_logger
        self.logger = logging.getLogger(__name__)

        # 从环境变量读取配置
        self.tg_bot_token = os.getenv("TG_BOT_TOKEN", "")
        self.tg_chat_id = os.getenv("TG_CHAT_ID", "")
        self.dingtalk_webhook = os.getenv("DINGTALK_WEBHOOK", "")
        self.dingtalk_secret = os.getenv("DINGTALK_SECRET", "")
        # 获取代理配置 (优先读取环境变量中的 HTTPS_PROXY)
        self.proxy_url = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("https_proxy") or os.getenv(
            "http_proxy")
        self.proxies = {"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else None

        if self.proxy_url and self.tg_bot_token:
            self.logger.debug(f"Notifier 代理已挂载: {self.proxy_url}")
    def _escape_telegram_markdown(self, text: str) -> str:
        """
        完整转义Telegram MarkdownV2的所有特殊字符
        参考：https://core.telegram.org/bots/api#markdownv2-style
        """
        # 需要转义的特殊字符列表
        escape_chars = r'_*[]()~`>#+-=|{}.!'
        # 使用正则表达式替换所有特殊字符（在前面加反斜杠）
        return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)
    def push_message(self, title: str, content: str, level: NotificationLevel = NotificationLevel.INFO) -> bool:
        """统一推送接口"""
        success = False

        if self.tg_bot_token and self.tg_chat_id:
            if self._send_telegram(title, content, level):
                success = True

        if self.dingtalk_webhook:
            if self._send_dingtalk(title, content, level):
                success = True

        if not self.tg_bot_token and not self.dingtalk_webhook:
            self.logger.warning("🔕 未配置任何推送凭证(Telegram/DingTalk)，跳过推送。")

        return success

    def _send_telegram(self, title: str, content: str, level: NotificationLevel) -> bool:
        """发送 Telegram 通知 (MarkdownV2格式)"""
        url = f"https://api.telegram.org/bot{self.tg_bot_token}/sendMessage"

        emoji_map = {
            NotificationLevel.INFO: "ℹ️",
            NotificationLevel.WARNING: "⚠️",
            NotificationLevel.ERROR: "❌",
            NotificationLevel.CRITICAL: "🚨"
        }

        # Telegram MarkdownV2 需要转义大量特殊字符，防止解析报错发送失败
        safe_title = self._escape_telegram_markdown(title)
        safe_content = self._escape_telegram_markdown(content)
        text = f"{emoji_map.get(level, '')} *{safe_title}*\n\n{safe_content}"

        payload = {
            "chat_id": self.tg_chat_id,
            "text": text,
            "parse_mode": "MarkdownV2"
        }

        try:
            res = requests.post(url, json=payload, timeout=10, proxies=self.proxies)
            if res.status_code == 200:
                self.logger.info("✈️ Telegram 推送成功！")
                return True
            else:
                self.logger.error(f"✈️ Telegram 推送失败: {res.text}")
                return False
        except Exception as e:
            self.logger.error(f"✈️ Telegram 推送异常: {e}")
            return False

    def _send_dingtalk(self, title: str, content: str, level: NotificationLevel) -> bool:
        """发送钉钉通知 (优雅高颜值的 Markdown 格式)"""

        # 💡 获取精确到秒的当前时间
        current_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())

        # 💡 核心优化：去除了丑陋的 ### [INFO] 标签，完全交由内容自行排版。
        # 加入了一条专业的灰色引用签名线（带时间），并隐藏了用来通过安全校验的钉钉密码。
        text_content = f"{content}\n\n---\n*Powered by 3和7 • {current_time}* &nbsp; <font color='#ffffff'>【{self.dingtalk_secret}】</font>"

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,  # 手机端消息列表外显的标题
                "text": text_content
            },
            "at": {
                "isAtAll": False
            }
        }

        try:
            # 钉钉通常国内直连，强制不使用代理
            res = requests.post(
                self.dingtalk_webhook,
                json=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=5,
                proxies={"http": None, "https": None}
            )
            res.raise_for_status()
            response_json = res.json()

            if response_json.get("errcode") == 0:
                self.logger.info("📱 钉钉 机构级战报推送成功！")
                return True
            else:
                self.logger.error(f"📱 钉钉 推送失败: {response_json.get('errmsg', '未知错误')}")
                return False
        except Exception as e:
            self.logger.error(f"📱 钉钉 推送异常: {str(e)}")
            return False