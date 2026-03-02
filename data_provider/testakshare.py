import akshare as ak
df = ak.stock_zh_a_hist("000001",period="daily")
print(df)

df = ak.stock_zh_a_daily("sh000001")
print(df)