import akshare as ak
# df = ak.stock_zh_a_hist("000002",period="daily")
#日期    股票代码     开盘     收盘  ...    振幅    涨跌幅   涨跌额   换手率
# 8357  2026-03-20  000001  10.87  10.77  ...  1.65  -1.01 -0.11  0.43
# print(df)

df = ak.stock_zh_a_daily("sh000001")

# date     open     high  ...        amount  outstanding_share  turnover
# 8530  2026-03-19  4028.54  4042.02  ...  9.352650e+11       1.940560e+10  3.438468
print(df)
