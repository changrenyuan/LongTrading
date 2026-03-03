import akshare as ak
import os
# 💡 强制 Python 忽略系统级别的代理，直连东财服务器！
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""
os.environ["trust_env"] = "False"
df = ak.stock_bid_ask_em(symbol="600410")
      # (symbol="002131"))
print(df)