import akshare as stock
import pandas as pd
from sqlalchemy import create_engine
from typing import Optional
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pykalman import KalmanFilter
import akshare as stock
import pandas as pd
from sqlalchemy import create_engine
from typing import Optional
import numpy as np
import os
import torch
import torch.nn as nn

# ===================== 全局配置（统一管理） =====================
# 数据库配置
DB_URL = "sqlite:///stock_data.db"
# 文件存储配置
CSV_DIR = "stock_data"  # 存储文件夹
# 全局数据库引擎（只创建一次，性能提升）
ENGINE = create_engine(DB_URL)

# 自动创建存储文件夹
import os
os.makedirs(CSV_DIR, exist_ok=True)


def fix_symbol(symbol: str) -> str:
    """
    规范化股票代码 (以备其他需要带有 sh/sz 前缀的接口使用)
    """
    raw_code = "".join(filter(str.isdigit, symbol))
    if raw_code.startswith('6'): return f"sh{raw_code}"
    if raw_code.startswith(('0', '3')): return f"sz{raw_code}"
    if raw_code.startswith(('4', '8')): return f"bj{raw_code}"  # 💡 补充了北交所
    return symbol
def fetch_stock_data(
    symbol: str,
    start_date: str,
    end_date: str,
    adjust: str = "qfq"
) -> pd.DataFrame:
    """
    仅获取股票数据（解耦获取与存储，职责单一）
    """
    print(f"正在获取 {symbol} 历史数据...")
    raw_code = fix_symbol(symbol)
    df = stock.stock_zh_a_daily(
        symbol=raw_code,
        # period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust=adjust
    )
    print(f"获取成功！共 {len(df)} 条数据")
    return df


def save_data(
    df: pd.DataFrame,
    symbol: str,
    save_type: str = "db"
) -> None:
    """
    统一存储接口：支持数据库/CSV
    """
    if save_type == "db":
        # 存储到 SQLite
        df.to_sql(
            name=f"stock_{symbol}",
            con=ENGINE,
            if_exists="replace",
            index=False
        )
        print(f"✅ 数据已存入数据库表：stock_{symbol}")

    elif save_type == "csv":
        # 自动生成唯一文件名，避免覆盖
        csv_path = os.path.join(CSV_DIR, f"stock_{symbol}.csv")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"✅ 数据已存入文件：{csv_path}")


def load_data(symbol: str, source: str = "db") -> Optional[pd.DataFrame]:
    """
    统一读取接口：支持从数据库/CSV读取
    :param source: 读取来源 db/csv
    """
    try:
        if source == "db":
            return pd.read_sql(f"SELECT * FROM stock_{symbol}", ENGINE)
        elif source == "csv":
            csv_path = os.path.join(CSV_DIR, f"stock_{symbol}.csv")
            return pd.read_csv(csv_path, encoding="utf-8-sig")
    except Exception as e:
        print(f"❌ 读取失败：{str(e)}")
        return None


def fetch_and_save_data(
    symbol: str,
    start_date: str,
    end_date: str,
    save_type: str = "db"
) -> Optional[pd.DataFrame]:
    """
    【主函数】获取 + 存储 一站式调用
    兼容你原来的函数名，无需修改调用代码
    """
    try:
        df = fetch_stock_data(symbol, start_date, end_date)
        save_data(df, symbol, save_type)
        return df
    except Exception as e:
        print(f"❌ 执行失败：{str(e)}")
        return None



# ===================== 示例用法 =====================
if __name__ == "__main__":
    # 配置参数
    CODE = "300502"
    START = "20230101"
    END = "20260327"

    # 1. 一站式获取并存储（兼容原用法）
    fetch_and_save_data(CODE, START, END, save_type="db")
    fetch_and_save_data(CODE, START, END, save_type="csv")

    # 2. 读取数据
    df_db = load_data(CODE, source="db")
    df_csv = load_data(CODE, source="csv")


