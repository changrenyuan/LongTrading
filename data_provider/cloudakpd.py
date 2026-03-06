import os
import time as time_sleep
import pandas as pd
import akshare as ak
from datetime import datetime, time, timedelta
from sqlalchemy import create_engine, text, MetaData, Table, Column, String, Float, Integer, DateTime, inspect
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
from utils.logger import global_logger as logger

# 💡 强制禁用代理，防止 AkShare 连接超时
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''


class DataCenter:
    def __init__(self, db_url=None):
        """
        工业级数据中心 - 支持 PostgreSQL (Neon) 与 SQLite
        """
        load_dotenv()
        if not db_url:
            db_url = os.getenv("DATABASE_URL")

        self.is_postgres = db_url and "postgresql" in db_url
        self.source_desc = "☁️  云端 (PostgreSQL)" if self.is_postgres else "🏠 本地 (SQLite)"

        if not db_url:
            db_path = os.path.join("data", "mt_alpha.db")
            os.makedirs("data", exist_ok=True)
            db_url = f"sqlite:///{db_path}"

        self.engine = create_engine(db_url, pool_recycle=3600, pool_pre_ping=True)
        self.metadata = MetaData()

        logger.info("=" * 60)
        logger.info("📊 [DataCenter] 数据内核启动审计...")
        logger.info(f"   ▫️ 存储模式 : {self.source_desc}")
        logger.info(f"   ▫️ 连接节点 : {db_url.split('@')[-1].split('?')[0] if '@' in db_url else db_url}")

        self._initialize_schema()
        logger.info("=" * 60)

    def _initialize_schema(self):
        """定义全量字段 Schema，适配 PostgreSQL 和 SQLite"""
        try:
            # 使用 TIMESTAMP (Postgres) 或 DATETIME (SQLite)
            col_ts_type = "TIMESTAMP" if self.is_postgres else "DATETIME"

            with self.engine.begin() as conn:
                conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS market_snapshots (
                        trade_date VARCHAR(10),
                        symbol VARCHAR(10),
                        name VARCHAR(20),
                        latest_price FLOAT,
                        open FLOAT,       -- 今日开盘价
                        high FLOAT,       -- 今日最高价
                        low FLOAT,        -- 今日最低价
                        amount FLOAT,     -- 成交额
                        volume FLOAT,     -- 成交量
                        turnover_rate FLOAT, -- 换手率
                        is_closed INTEGER,   -- 是否定格 (1)
                        updated_at {col_ts_type}, -- 写入时间
                        PRIMARY KEY (trade_date, symbol)
                    )
                """))

            # 自动维护：补全缺失列 (针对旧库升级)
            inspector = inspect(self.engine)
            existing_cols = [c['name'] for c in inspector.get_columns('market_snapshots')]

            needed_cols = {
                'open': 'FLOAT', 'high': 'FLOAT', 'low': 'FLOAT',
                'volume': 'FLOAT', 'is_closed': 'INTEGER DEFAULT 0',
                'updated_at': col_ts_type
            }

            with self.engine.begin() as conn:
                for col, dtype in needed_cols.items():
                    if col not in existing_cols:
                        conn.execute(text(f"ALTER TABLE market_snapshots ADD COLUMN {col} {dtype}"))
                        logger.info(f"🛠️  Schema 自动补全: 增加字段 [{col}]")

            logger.info(f"📂 字段审计完成，当前支持: {', '.join(set(existing_cols + list(needed_cols.keys())))}")
        except Exception as e:
            logger.error(f"❌ 数据库内核架构维护失败: {e}")

    def get_real_trade_date_info(self):
        """判定归属日期及定格状态 (15:35 分界)"""
        try:
            trade_days_df = ak.tool_trade_date_hist_sina()
            trade_days = pd.to_datetime(trade_days_df['trade_date']).dt.date.tolist()
            now = datetime.now()
            today = now.date()

            if today in trade_days:
                # 交易日 15:35 后视为收盘定格
                is_closed = 1 if now.time() >= time(15, 35) else 0
                return today.strftime("%Y-%m-%d"), is_closed
            else:
                # 非交易日归属到上一个交易日，状态为定格
                last_day = [d for d in trade_days if d < today][-1]
                return last_day.strftime("%Y-%m-%d"), 1
        except Exception as e:
            logger.error(f"⚠️ 交易日历获取异常: {e}")
            return datetime.now().strftime("%Y-%m-%d"), 0

    def sync_market_snapshot(self, refresh_interval_hours=1, keep_days=20):
        """
        核心刷新逻辑：
        1. 超过1小时自动刷新盘中价。
        2. 收盘后强制执行一次定格写入。
        3. 定格成功后清理过期快照。
        """
        target_date_str, is_closed_now = self.get_real_trade_date_info()

        query = text("SELECT is_closed, updated_at ,open FROM market_snapshots WHERE trade_date = :dt LIMIT 1")
        try:
            with self.engine.connect() as conn:
                record = conn.execute(query, {"dt": target_date_str}).fetchone()

            if record:
                db_is_closed, db_updated_at,db_open = record[0], record[1], record[2]

                # 已定格，直接跳过
                if db_is_closed == 1 and db_open is not None:
                    logger.info(f"✅ [{target_date_str}] 历史数据已定格，无需同步。")
                    return True
                if db_open is None:
                    logger.warning(f"⚠️  检测到 [{target_date_str}] 存在残缺数据(OHLC缺失)，强制重新同步补全...")
                # 盘中保鲜逻辑
                elif db_is_closed == 0 and is_closed_now == 0 and db_updated_at:
                    time_diff = datetime.now() - db_updated_at
                    if time_diff < timedelta(hours=refresh_interval_hours):
                        logger.info(f"⏳ 数据保鲜期内 (上次同步: {db_updated_at.strftime('%H:%M')})，跳过同步。")
                        return True

            # 执行同步
            success = self._execute_real_sync(target_date_str, is_closed_now)

            # 如果定格成功，触发代谢清理
            if success and is_closed_now == 1:
                self._cleanup_old_data(keep_days=keep_days)

            return success
        except Exception as e:
            logger.error(f"同步前置自检失败: {e}")
            return False

    def _execute_real_sync(self, target_date_str, is_closed):
        """执行物理抓取并写入，确保全量字段"""
        try:
            df_raw = pd.DataFrame()
            for _ in range(3):
                try:
                    df_raw = ak.stock_zh_a_spot()
                    if not df_raw.empty: break
                except:
                    time_sleep.sleep(2)

            if df_raw.empty: return False

            # 💡 物理映射：严禁删减
            potential_map = {
                'symbol': ['code', '代码'], 'name': ['name', '名称'], 'latest_price': ['trade', '最新价'],
                'open': ['open', '今开'], 'high': ['high', '最高'], 'low': ['low', '最低'],
                'amount': ['amount', '成交额'], 'volume': ['volume', '成交量'],
                'turnover_rate': ['turnoverratio', '换手率']
            }
            mapping = {cand: target for target, cands in potential_map.items() for cand in cands if
                       cand in df_raw.columns}

            clean_df = df_raw[list(mapping.keys())].rename(columns=mapping)
            clean_df['trade_date'] = target_date_str
            clean_df['is_closed'] = is_closed
            clean_df['updated_at'] = datetime.now()
            clean_df['symbol'] = clean_df['symbol'].astype(str).str.extract(r'(\d{6})')

            with self.engine.begin() as conn:
                conn.execute(text("DELETE FROM market_snapshots WHERE trade_date = :dt"), {"dt": target_date_str})
                clean_df.to_sql('market_snapshots', con=conn, if_exists='append', index=False)

            self._logger_audit(clean_df, f"同步完成: {target_date_str}")
            return True
        except Exception as e:
            logger.error(f"物理写入异常: {e}")
            return False

    def get_snapshot_from_cloud(self, date_str=None):
        if not date_str: date_str, _ = self.get_real_trade_date_info()
        try:
            query = f"SELECT * FROM market_snapshots WHERE trade_date = '{date_str}' ORDER BY is_closed DESC, updated_at DESC"
            df = pd.read_sql(query, con=self.engine)
            df = df.drop_duplicates(subset=['symbol'])
            if not df.empty:
                self._logger_audit(df, f"读取成功: {date_str}")
            return df
        except Exception as e:
            logger.error(f"云端提取异常: {e}")
            return pd.DataFrame()

    def _logger_audit(self, df, title):
        logger.info("-" * 45)
        logger.info(f"🔍 [审计] {title}")
        logger.info(f"   ▫️ 标的总数 : {len(df)} 条")
        logger.info(f"   ▫️ 资金状态 : {'已收盘定格' if df['is_closed'].iloc[0] == 1 else '盘中实时'}")
        logger.info(f"   ▫️ 存入时间 : {df['updated_at'].iloc[0]}")
        top3 = df[['symbol', 'name', 'open', 'latest_price', 'high', 'low', 'volume', 'amount','trade_date']].head(3).to_string(index=False)
        logger.info(f"\n{top3}")
        logger.info("-" * 45)

    def _cleanup_old_data(self, keep_days=20):
        """自动代谢：保留 20 个交易日"""
        try:
            query_dates = text("SELECT DISTINCT trade_date FROM market_snapshots ORDER BY trade_date DESC")
            with self.engine.connect() as conn:
                existing_dates = [row[0] for row in conn.execute(query_dates).fetchall()]

            if len(existing_dates) > keep_days:
                threshold_date = existing_dates[keep_days - 1]
                with self.engine.begin() as conn:
                    conn.execute(text("DELETE FROM market_snapshots WHERE trade_date < :dt"), {"dt": threshold_date})
                    logger.info(f"🧹 自动代谢：已清理 {threshold_date} 之前的过期快照。")
        except Exception as e:
            logger.error(f"❌ 自动清理失败: {e}")


if __name__ == "__main__":
    # --- 💡 实时校验环节 ---
    dc = DataCenter()
    dc.sync_market_snapshot()

    # 读取第一行数据进行校验
    df_check = dc.get_snapshot_from_cloud()
    if not df_check.empty:
        print("\n" + "=" * 50)
        print("✅ 数据库列名校验:")
        print(df_check.columns.tolist())
        print("\n✅ 第一行数据值校验:")
        print(df_check.iloc[0].to_dict())
        print("=" * 50)