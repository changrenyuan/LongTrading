"""
第2课：股票数据存储与数据库设计
================================

学习目标：
1. CSV文件存储与读取
2. SQLite数据库设计与操作
3. 数据库表结构规划
4. 增量更新策略

作者：Python机器学习教学
"""

import akshare as ak
import pandas as pd
import sqlite3
import os
from datetime import datetime

import akshare as ak
import pandas as pd


def get_stock_history(symbol, start_date, end_date, adjust="qfq"):
    """
    通过新浪接口获取 A 股历史行情数据

    参数:
        symbol: 股票代码（带市场前缀）
               - 上海证券交易所: 'sh' + 代码，如 'sh600519'（贵州茅台）
               - 深圳证券交易所: 'sz' + 代码，如 'sz000001'（平安银行）
               - 北京证券交易所: 'bj' + 代码，如 'bj430017'（星昊医药）
        start_date: 开始日期，格式 'YYYYMMDD'
        end_date: 结束日期，格式 'YYYYMMDD'
        adjust: 复权类型
               - "": 不复权
               - "qfq": 前复权（推荐看盘使用，行情软件默认）
               - "hfq": 后复权（推荐量化研究使用，反映真实收益）

    返回:
        DataFrame，包含日期、开盘价、最高价、最低价、收盘价、成交量等

    注意:
        多次快速请求可能被封 IP，建议添加时间间隔
    """
    df = ak.stock_zh_a_daily(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust
    )

    return df


def get_all_stocks_realtime():
    """
    获取沪深京 A 股所有股票的实时行情

    返回:
        DataFrame，包含代码、名称、最新价、涨跌幅、成交量等

    用途:
        - 查找股票代码
        - 监控市场全貌
        - 筛选符合条件的股票

    注意:
        重复运行会被新浪暂时封 IP，建议增加时间间隔
    """
    df = ak.stock_zh_a_spot()
    return df


# ===== 使用示例 =====

# ============================================================
# 第一部分：CSV文件存储
# ============================================================

def save_to_csv(df, filepath):
    """
    将DataFrame保存为CSV文件

    参数:
        df: 要保存的DataFrame
        filepath: CSV文件路径

    返回:
        保存的文件路径
    """
    # 确保目录存在
    dir_path = os.path.dirname(filepath)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    print(f"✅ CSV文件已保存: {filepath}")
    return filepath


def read_from_csv(filepath):
    """
    从CSV文件读取数据

    参数:
        filepath: CSV文件路径

    返回:
        DataFrame
    """
    df = pd.read_csv(filepath)
    print(f"✅ CSV文件已读取: {len(df)} 条记录")
    return df


# ============================================================
# 第二部分：SQLite数据库设计与操作
# ============================================================

class StockDatabase:
    """
    股票数据库管理类

    数据库设计思路：
    ─────────────────────────────────────────
    表1: stock_basic（股票基本信息表）
    ├── symbol      TEXT PRIMARY KEY  股票代码
    ├── name        TEXT              股票名称
    ├── market      TEXT              市场类型（sh/sz/bj）
    └── update_time TEXT              更新时间

    表2: stock_daily（日线行情表）⭐核心表
    ├── id          INTEGER PRIMARY KEY
    ├── symbol      TEXT              股票代码
    ├── trade_date  TEXT              交易日期
    ├── open        REAL              开盘价
    ├── high        REAL              最高价
    ├── low         REAL              最低价
    ├── close       REAL              收盘价
    ├── volume      REAL              成交量
    ├── amount      REAL              成交额
    └── adjust      TEXT              复权类型
    └── UNIQUE(symbol, trade_date, adjust)  唯一约束
    ─────────────────────────────────────────
    """

    def __init__(self, db_path="stock_data.db"):
        """
        初始化数据库连接

        参数:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.conn = None
        self._init_database()

    def _init_database(self):
        """
        初始化数据库，创建表结构
        """
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()

        # 创建股票基本信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_basic (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                market TEXT,
                update_time TEXT
            )
        ''')

        # 创建日线行情表（核心表）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                outstanding_share REAL,
                turnover REAL,
                adjust TEXT DEFAULT 'qfq',
                created_time TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, trade_date, adjust)
            )
        ''')

        # 创建索引，加速查询
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_symbol_date 
            ON stock_daily(symbol, trade_date)
        ''')

        self.conn.commit()
        print(f"✅ 数据库初始化完成: {self.db_path}")

    def insert_daily_data(self, df, symbol, adjust="qfq"):
        """
        插入日线数据（支持增量更新）

        参数:
            df: 包含日线数据的DataFrame
            symbol: 股票代码（如 'sh600519'）
            adjust: 复权类型

        返回:
            插入/更新的记录数
        """
        if df.empty:
            print("⚠️ 数据为空，跳过插入")
            return 0

        cursor = self.conn.cursor()
        count = 0

        for _, row in df.iterrows():
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_daily 
                    (symbol, trade_date, open, high, low, close, volume, 
                     amount, outstanding_share, turnover, adjust)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol,
                    str(row['date']),
                    row.get('open', None),
                    row.get('high', None),
                    row.get('low', None),
                    row.get('close', None),
                    row.get('volume', None),
                    row.get('amount', None),
                    row.get('outstanding_share', None),
                    row.get('turnover', None),
                    adjust
                ))
                count += 1
            except Exception as e:
                print(f"❌ 插入失败: {row['date']}, 错误: {e}")

        self.conn.commit()
        print(f"✅ 插入/更新 {count} 条记录 (股票: {symbol}, 复权: {adjust})")
        return count

    def query_daily_data(self, symbol, start_date=None, end_date=None, adjust="qfq"):
        """
        查询日线数据

        参数:
            symbol: 股票代码
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            adjust: 复权类型

        返回:
            DataFrame
        """
        cursor = self.conn.cursor()

        sql = '''
            SELECT trade_date, open, high, low, close, volume, amount, turnover
            FROM stock_daily
            WHERE symbol = ? AND adjust = ?
        '''
        params = [symbol, adjust]

        if start_date:
            sql += ' AND trade_date >= ?'
            params.append(start_date)

        if end_date:
            sql += ' AND trade_date <= ?'
            params.append(end_date)

        sql += ' ORDER BY trade_date'

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        df = pd.DataFrame(rows, columns=[
            'trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'turnover'
        ])

        print(f"✅ 查询到 {len(df)} 条记录")
        return df

    def get_table_info(self, table_name="stock_daily"):
        """
        获取表结构信息
        """
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()

        print(f"\n📋 表结构 [{table_name}]:")
        print("-" * 60)
        print(f"{'序号':<6}{'字段名':<20}{'类型':<10}{'是否主键':<10}")
        print("-" * 60)
        for col in columns:
            print(f"{col[0]:<6}{col[1]:<20}{col[2]:<10}{'是' if col[5] else '否':<10}")

    def get_statistics(self):
        """
        获取数据库统计信息
        """
        cursor = self.conn.cursor()

        # 统计记录数
        cursor.execute("SELECT COUNT(*) FROM stock_daily")
        total_records = cursor.fetchone()[0]

        # 统计股票数
        cursor.execute("SELECT COUNT(DISTINCT symbol) FROM stock_daily")
        total_stocks = cursor.fetchone()[0]

        # 统计日期范围
        cursor.execute("SELECT MIN(trade_date), MAX(trade_date) FROM stock_daily")
        date_range = cursor.fetchone()

        print("\n📊 数据库统计:")
        print("-" * 40)
        print(f"总记录数: {total_records:,}")
        print(f"股票数量: {total_stocks}")
        print(f"日期范围: {date_range[0]} ~ {date_range[1]}")
        print("-" * 40)

    def close(self):
        """
        关闭数据库连接
        """
        if self.conn:
            self.conn.close()
            print("✅ 数据库连接已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ============================================================
# 第三部分：完整工作流示例
# ============================================================

def fetch_and_save_stock(symbol, start_date, end_date, adjust="qfq",
                         csv_dir="data/csv", db_path="data/stock.db"):
    """
    完整的数据获取与存储流程

    参数:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        adjust: 复权类型
        csv_dir: CSV存储目录
        db_path: 数据库路径

    返回:
        DataFrame
    """
    # 1. 创建目录
    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)

    # 2. 从AkShare获取数据
    print(f"\n📥 正在获取 {symbol} 数据...")
    df = ak.stock_zh_a_daily(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust
    )

    if df.empty:
        print("⚠️ 未获取到数据")
        return df

    print(f"✅ 获取到 {len(df)} 条记录")

    # 3. 保存为CSV（临时备份）
    csv_file = os.path.join(csv_dir, f"{symbol}_{adjust}.csv")
    save_to_csv(df, csv_file)

    # 4. 保存到数据库（持久化存储）
    with StockDatabase(db_path) as db:
        db.insert_daily_data(df, symbol, adjust)
        db.get_statistics()

    return df


# ============================================================
# 主程序：演示完整流程
# ============================================================

if __name__ == "__main__":


    # 示例1：获取贵州茅台历史数据（前复权）
    print("📊 示例1：获取贵州茅台(sh600519) 2023年历史数据")
    df = get_stock_history('sh600519', '20230101', '20231231', adjust="qfq")
    print(df.head(10))
    print(f"\n共有 {len(df)} 条记录")

    # 示例2：获取平安银行历史数据（后复权，适合量化研究）
    print("\n" + "=" * 50)
    print("📊 示例2：获取平安银行(sz000001) 近期数据（后复权）")
    df2 = get_stock_history('sz000001', '20231001', '20231027', adjust="hfq")
    print(df2.head())

    # 示例3：获取所有股票实时行情（用于查找股票代码）
    print("\n" + "=" * 50)
    print("📊 示例3：获取所有A股实时行情（前10条）")
    all_stocks = get_all_stocks_realtime()
    print(all_stocks.head(10))
    save_to_csv(all_stocks,"all_stocks_20260331.csv")
    print(f"\n当前共有 {len(all_stocks)} 只股票")

    print("=" * 60)
    print("第2课：股票数据存储与数据库设计")
    print("=" * 60)

    # ===== 演示1：CSV存储 =====
    print("\n" + "=" * 50)
    print("📁 演示1：CSV文件存储与读取")
    print("=" * 50)

    # 创建示例数据
    sample_data = pd.DataFrame({
        'date': ['2023-10-23', '2023-10-24', '2023-10-25', '2023-10-26', '2023-10-27'],
        'open': [10.59, 10.54, 10.51, 10.31, 10.38],
        'high': [10.60, 10.61, 10.54, 10.42, 10.48],
        'low': [10.50, 10.52, 10.30, 10.28, 10.32],
        'close': [10.55, 10.58, 10.40, 10.35, 10.42],
        'volume': [100000, 120000, 95000, 88000, 110000]
    })

    # 保存CSV
    csv_path = "data/csv/sample_stock.csv"
    save_to_csv(sample_data, csv_path)

    # 读取CSV
    df_from_csv = read_from_csv(csv_path)
    print("\n前5行数据:")
    print(df_from_csv.head())

    # ===== 演示2：数据库存储 =====
    print("\n" + "=" * 50)
    print("🗄️ 演示2：SQLite数据库存储")
    print("=" * 50)

    db_path = "data/stock.db"

    with StockDatabase(db_path) as db:
        # 查看表结构
        db.get_table_info()

        # 插入示例数据
        db.insert_daily_data(sample_data, 'sz000001', 'qfq')

        # 查询数据
        result = db.query_daily_data('sz000001')
        print("\n查询结果（前5行）:")
        print(result.head())

        # 统计信息
        db.get_statistics()

    # ===== 演示3：完整工作流 =====
    print("\n" + "=" * 50)
    print("🔄 演示3：完整数据获取与存储流程")
    print("=" * 50)

    # 获取真实数据并存储（注意：频繁请求可能被封IP）
    # 取消下面的注释来运行真实数据获取
    # df_real = fetch_and_save_stock(
    #     symbol='sh600519',
    #     start_date='20231001',
    #     end_date='20231027',
    #     adjust='qfq'
    # )

    print("\n💡 提示：取消注释上面的代码来获取真实数据")
    print("   注意：AkShare新浪接口频繁请求会被封IP，建议添加延时")

    # ===== 演示4：数据库设计说明 =====
    print("\n" + "=" * 50)
    print("📐 数据库设计最佳实践")
    print("=" * 50)

    print("""
    1. 表设计原则：
       - 股票基本信息表：存储静态信息（代码、名称、行业等）
       - 日线行情表：存储动态数据（OHLCV）
       - 技术指标表：存储计算后的指标（MA、RSI等）

    2. 索引设计：
       - 主键索引：symbol + trade_date + adjust
       - 查询优化：为常用查询条件创建索引

    3. 数据类型选择：
       - 日期：TEXT（'YYYY-MM-DD'格式，便于查询）
       - 价格：REAL（浮点数）
       - 成交量：REAL（支持大数值）

    4. 扩展建议：
       - 添加 tick 数据表（分钟/秒级数据）
       - 添加财务数据表（季度报表）
       - 添加预测结果表（机器学习输出）
    """)

    print("\n✅ 第2课学习完成！")
