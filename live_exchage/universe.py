import os
import json
import pandas as pd
from sqlalchemy import text
from utils.logger import global_logger as logger
from data_provider.cloudakpd import DataCenter  # 💡 引入云端地基


class UniverseManager:
    def __init__(self, pool_file="data/universe_pool.json"):
        """
        股票池管理器：从云端动态筛选“活水”，并维护实盘监控属性
        """
        self.dc = DataCenter()  # 💡 建立云端数据库连接
        self.pool_file = pool_file
        self.spot_df = pd.DataFrame()

        # 💡 核心列属性：严格保留，禁止删减。对齐 cloudakpd.py 的字段名
        self.price_col = 'latest_price'
        self.name_col = 'name'
        self.amt_col = 'amount'
        self.open_col = 'open'  # 针对 engine.py 的盘中注入
        self.high_col = 'high'  # 针对 engine.py 的盘中注入
        self.low_col = 'low'  # 针对 engine.py 的盘中注入
        self.vol_col = 'volume'  # 针对 engine.py 的盘中注入
        self.turn_col = 'turnover_rate'

        self._load_snapshot()

    def _load_snapshot(self):
        """
        💡 升级：直接从云端 PostgreSQL 获取全量快照，不再依赖本地 CSV
        """
        try:
            # 调用 DataCenter 的云端读取方法
            self.spot_df = self.dc.get_snapshot_from_cloud()
            if not self.spot_df.empty:
                # 确保代码是 6 位字符串并设为索引
                self.spot_df.set_index('symbol', inplace=True)
                logger.info(f"✅ [UniverseManager] 云端全量快照加载成功，当前监控 {len(self.spot_df)} 只标的。")
            else:
                logger.warning("⚠️ [UniverseManager] 云端快照为空，请检查数据同步。")
        except Exception as e:
            logger.error(f"❌ [UniverseManager] 获取全市场快照异常: {e}")

    def get_spot_val(self, sym, col_name, fallback=None):
        """
        从快照中提取指定字段的值（如最新价、开盘价等）
        """
        if self.spot_df.empty or sym not in self.spot_df.index:
            return fallback

        val = self.spot_df.loc[sym, col_name]
        # 处理 Pandas 结果集或空值
        if isinstance(val, pd.Series):
            val = val.iloc[0]

        return fallback if pd.isna(val) or val == '-' or val == '' else val

    def get_sym_name(self, sym):
        """获取股票名称"""
        return str(self.get_spot_val(sym, self.name_col, sym))

    def build_dynamic_stock_pool(self, held_symbols, max_size=20, lookback_days=20):
        """
        💡 升级：基于云端 20 日成交额排名统计热度，构建动态股票池
        """
        pool_details = []
        pool_symbols = []

        # 1. 强制保留当前持仓标的 (🛡️ 老兵)
        for sym in dict.fromkeys(held_symbols):
            sym = str(sym).zfill(6)  # 补齐 6 位
            pool_symbols.append(sym)
            pool_details.append({
                "symbol": sym,
                "name": self.get_sym_name(sym),
                "reason": "🛡️ 实盘持仓标的，强制监控"
            })

        # 2. 💡 从云端数据库进行 SQL 热度审计 (不再扫描本地文件)
        logger.info(f"📊 正在通过云端 SQL 审计近 {lookback_days} 个交易日的热点标的...")
        hot_counter = {}
        try:
            # 统计最近 X 个交易日内，每日成交额排名前 20 的频次
            query = text(f"""
                WITH daily_rank AS (
                    SELECT trade_date, symbol, 
                           ROW_NUMBER() OVER(PARTITION BY trade_date ORDER BY amount DESC) as rk
                    FROM market_snapshots
                    WHERE name NOT LIKE '%ST%' 
                      AND (symbol LIKE '60%' OR symbol LIKE '00%' OR symbol LIKE '30%')
                )
                SELECT symbol, COUNT(*) as hit_count
                FROM daily_rank
                WHERE rk <= 20
                GROUP BY symbol
                ORDER BY hit_count DESC
                LIMIT 50
            """)

            with self.dc.engine.connect() as conn:
                hot_results = conn.execute(query).fetchall()

            for row in hot_results:
                hot_counter[row[0]] = row[1]

        except Exception as e:
            logger.error(f"❌ [UniverseManager] 云端热度审计失败: {e}")

        # 3. 填充活水池标的 (🔥 新秀)
        # 按入榜频次降序排列
        sorted_codes = sorted(hot_counter.keys(), key=lambda x: hot_counter[x], reverse=True)

        for code in sorted_codes:
            if code not in pool_symbols and len(pool_symbols) < max_size:
                pool_symbols.append(code)
                pool_details.append({
                    "symbol": code,
                    "name": self.get_sym_name(code),
                    "reason": f"🔥 近期榜单前20强入围 {hot_counter[code]} 次"
                })

        # 4. 持久化股票池 JSON (供实盘与 WebUI 展示)
        try:
            os.makedirs(os.path.dirname(self.pool_file), exist_ok=True)
            with open(self.pool_file, 'w', encoding='utf-8') as f:
                json.dump(pool_details, f, indent=4, ensure_ascii=False)
            logger.info(f"✅ [UniverseManager] 动态股票池已对齐云端，当前池规模: {len(pool_symbols)}")
        except Exception as e:
            logger.error(f"❌ [UniverseManager] 保存股票池详情失败: {e}")

        return pool_symbols, lookback_days