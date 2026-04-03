import pandas as pd
import akshare as ak
import gm.api as gm
from sqlalchemy import create_engine
import datetime
import warnings
import os
warnings.filterwarnings("ignore")

# ===================== 全局核心配置（必须修改） =====================
# 掘金终端IP地址 + 端口
GM_SERVER_ADDR = "192.168.3.12:7001"
# 掘金TOKEN
GM_TOKEN = "aa08f4cebff6539a76396d3f1f4123e5f7d5f108"
# 数据库路径
DB_PATH = 'sqlite:///quant_factor_data.db'
# 数据存储根目录
DATA_SAVE_PATH = "./quant_data/"
# 日线数据CSV子目录
DAILY_CSV_PATH = "./quant_data/daily/"
# ==================================================================

class DataManager:
    def __init__(self, db_path=DB_PATH):
        """初始化：数据库连接 + 掘金初始化 + 创建目录"""
        self.engine = create_engine(db_path, echo=False)
        self._init_gm()
        self._init_dirs()

    def _init_gm(self):
        """初始化掘金SDK（标准格式）"""
        try:
            gm.set_serv_addr(GM_SERVER_ADDR)
            gm.set_token(GM_TOKEN)
            print("✅ 掘金SDK初始化成功")
        except Exception as e:
            print(f"❌ 掘金SDK初始化失败：{str(e)}")

    def _init_dirs(self):
        """创建所需文件夹"""
        for path in [DATA_SAVE_PATH, DAILY_CSV_PATH]:
            if not os.path.exists(path):
                os.makedirs(path)

    # ===================== 股票&指数数据（无掘金代码存储） =====================
    def fetch_all_stocks(self):
        """获取全市场A股：代码+名称，存储到 all_stocks"""
        stock_info = ak.stock_info_a_code_name()
        stock_info.columns = ["symbol", "name"]
        # 仅存通用6位代码，不存掘金格式
        stock_info.to_sql("all_stocks", self.engine, if_exists="replace", index=False)
        stock_info.to_csv(f"{DATA_SAVE_PATH}all_stocks.csv", index=False, encoding="utf-8-sig")
        print(f"✅ 全市场股票保存完成，共 {len(stock_info)} 只")
        return stock_info["symbol"].tolist()

    def fetch_index_stocks(self, index_code, index_name):
        """获取指数成分股：上证50/沪深300/中证1000"""
        index_df = ak.index_stock_cons_weight_csindex(symbol=index_code)
        index_df.rename(columns={"成分券代码":"symbol", "成分券名称":"name", "权重":"weight"}, inplace=True)
        # 仅存通用6位代码
        index_df = index_df[["symbol", "name", "weight"]]
        table_name = f"universe_{index_name}"
        index_df.to_sql(table_name, self.engine, if_exists="replace", index=False)
        index_df.to_csv(f"{DATA_SAVE_PATH}{table_name}.csv", index=False, encoding="utf-8-sig")
        print(f"✅ {index_name} 成分股保存完成，共 {len(index_df)} 只")
        return index_df["symbol"].tolist()

    def fetch_all_index_universe(self):
        """一键获取三大指数"""
        sz50 = self.fetch_index_stocks("000016", "sz50")
        hs300 = self.fetch_index_stocks("000300", "hs300")
        zz1000 = self.fetch_index_stocks("000852", "zz1000")
        return sz50, hs300, zz1000

    # ===================== 交易日历 =====================
    def fetch_trade_dates(self):
        """获取A股所有交易日"""
        trade_dates = ak.tool_trade_date_hist_sina()
        trade_dates.columns = ["trade_date"]
        trade_dates["trade_date"] = pd.to_datetime(trade_dates["trade_date"]).dt.strftime("%Y-%m-%d")
        trade_dates.to_sql("trade_dates", self.engine, if_exists="replace", index=False)
        trade_dates.to_csv(f"{DATA_SAVE_PATH}trade_dates.csv", index=False)
        print(f"✅ 交易日历保存完成")
        return trade_dates

    # ===================== 核心：日K数据（每只股票一张表 + 统一字段） =====================
    def _convert_to_gm_symbol(self, symbol):
        """6位通用代码 → 掘金标准格式：SHSE / SZSE"""
        if symbol.startswith("6"):
            return f"SHSE.{symbol}"
        elif symbol.startswith("0") or symbol.startswith("3"):
            return f"SZSE.{symbol}"
        else:
            return None

    def fetch_daily_data(self, symbol_list, days=30):
        """
        日K数据：统一字段 + 每只股票单独一张表
        字段：symbol, date, lastdate, open, high, low, close, volume, amount
        """
        end_date = datetime.date.today().strftime("%Y-%m-%d")
        start_date = (datetime.date.today() - datetime.timedelta(days=days*2)).strftime("%Y-%m-%d")
        lastdate = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 数据保存时间

        # 批量转换为掘金代码
        gm_symbols = [self._convert_to_gm_symbol(s) for s in symbol_list if self._convert_to_gm_symbol(s)]

        try:
            # 掘金获取日线（gm.调用）
            data = gm.history(
                symbol=gm_symbols,
                frequency='1d',
                start_time=start_date,
                end_time=end_date,
                df=True
            )

            # ===================== 统一字段格式 =====================
            data.rename(columns={"eob": "date"}, inplace=True)
            data["date"] = pd.to_datetime(data["date"]).dt.strftime("%Y-%m-%d")
            data["lastdate"] = lastdate
            # 从掘金代码提取6位通用 symbol
            data["symbol"] = data["symbol"].apply(lambda x: x.split(".")[-1])

            # 最终固定字段
            data = data[["symbol", "date", "lastdate", "open", "high", "low", "close", "volume", "amount"]]

            # ===================== 每只股票单独存表 + 单独CSV =====================
            for sym, df_group in data.groupby("symbol"):
                # 数据库表名：daily_6位代码
                table_name = f"daily_{sym}"
                df_group.to_sql(table_name, self.engine, if_exists="replace", index=False)
                # 单独保存CSV
                df_group.to_csv(f"{DAILY_CSV_PATH}{sym}.csv", index=False, encoding="utf-8-sig")

            print(f"✅ 日K数据获取完成 | 共 {data['symbol'].nunique()} 只股票 | 每只股票单独存储")
            return data

        except Exception as e:
            print(f"❌ 日K数据获取失败：{str(e)}")
            return pd.DataFrame()

    # ===================== 一键全量更新 =====================
    def full_update(self, days=30):
        print("="*50)
        print("开始全量数据更新")
        print("="*50)
        self.fetch_all_stocks()        # 全市场股票
        self.fetch_all_index_universe()# 三大指数
        self.fetch_trade_dates()       # 交易日历
        all_symbols = self.fetch_all_stocks()
        self.fetch_daily_data(all_symbols, days=days)
        print("🎉 所有数据更新完成！")

    # ===================== 数据库读取工具 =====================
    def read_table(self, table_name):
        """读取任意表"""
        try:
            return pd.read_sql(f"SELECT * FROM {table_name}", self.engine)
        except:
            return pd.DataFrame()

    def read_daily(self, symbol):
        """快速读取单只股票日K数据"""
        return self.read_table(f"daily_{symbol}")

# ===================== 测试运行 =====================
if __name__ == "__main__":
    dm = DataManager()
    # 全量更新（近30日日K）
    # dm.full_update(days=30)

    # 读取示例
    df = dm.read_daily("601869")
    print(df)
    # dm.fetch_daily_data(symbols, days=1000)