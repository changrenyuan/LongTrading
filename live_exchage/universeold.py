import os
import glob
import json
import pandas as pd
from utils.logger import global_logger as logger


class UniverseManager:
    def __init__(self, provider, pool_file="data/universe_pool.json"):
        self.provider = provider
        self.pool_file = pool_file
        self.spot_df = pd.DataFrame()
        self.price_col = None
        self.open_col, self.high_col, self.low_col = '今开', '最高', '最低'
        self.vol_col, self.turn_col = '成交量', '换手率'
        self.name_col = '名称'
        self._load_snapshot()

    def _load_snapshot(self):
        try:
            spot_df = self.provider.get_market_snapshot()
            if not spot_df.empty:
                code_raw = '代码' if '代码' in spot_df.columns else ('code' if 'code' in spot_df.columns else 'symbol')
                spot_df['clean_code'] = spot_df[code_raw].astype(str).str.extract(r'(\d{6})')
                spot_df = spot_df.dropna(subset=['clean_code'])
                spot_df.set_index('clean_code', inplace=True)
                self.price_col = '最新价' if '最新价' in spot_df.columns else (
                    'trade' if 'trade' in spot_df.columns else None)
                self.name_col = '名称' if '名称' in spot_df.columns else 'name'
                self.spot_df = spot_df
        except Exception as e:
            logger.warning(f"获取全市场快照异常: {e}")

    def get_spot_val(self, sym, col_name, fallback=None):
        if self.spot_df.empty or sym not in self.spot_df.index or not col_name:
            return fallback
        info = self.spot_df.loc[sym]
        if isinstance(info, pd.DataFrame): info = info.iloc[0]
        val = info.get(col_name)
        return fallback if pd.isna(val) or val == '-' or val == '' else val

    def get_sym_name(self, sym):
        return str(self.get_spot_val(sym, self.name_col, sym))

    def build_dynamic_stock_pool(self, held_symbols, max_size=20):
        pool_details = []
        pool_symbols = []

        # 1. 强制保留当前持仓
        for sym in dict.fromkeys(held_symbols):
            pool_symbols.append(sym)
            pool_details.append({
                "symbol": sym,
                "name": self.get_sym_name(sym),
                "reason": "🛡️ 当前持仓，强制保留名额"
            })

        # 2. 统计近期热度
        hot_counter = {}
        csv_files = glob.glob("data_provider/test_cache_data/*spot*.csv") + glob.glob(
            "data_provider/test_cache_data/*snapshot*.csv") + glob.glob("data/*snapshot*.csv")
        csv_files.sort(key=os.path.getmtime, reverse=True)
        recent_files = csv_files[:20]

        for f in recent_files:
            try:
                spot_df = pd.read_csv(f, dtype=str)
                code_col = '代码' if '代码' in spot_df.columns else 'symbol'
                amt_col = '成交额' if '成交额' in spot_df.columns else 'amount'
                name_col = '名称' if '名称' in spot_df.columns else 'name'

                spot_df['clean_code'] = spot_df[code_col].str.extract(r'(\d{6})')
                spot_df = spot_df.dropna(subset=['clean_code'])
                if name_col in spot_df.columns:
                    spot_df = spot_df[~spot_df[name_col].astype(str).str.contains('ST')]
                spot_df = spot_df[spot_df['clean_code'].str.startswith(('60', '00', '30'))]
                spot_df[amt_col] = pd.to_numeric(spot_df[amt_col], errors='coerce').fillna(0)

                top10 = spot_df.sort_values(by=amt_col, ascending=False).head(10)['clean_code'].tolist()
                for code in top10:
                    hot_counter[code] = hot_counter.get(code, 0) + 1
            except:
                continue

        sorted_hot = sorted(hot_counter.keys(), key=lambda x: hot_counter[x], reverse=True)

        # 3. 填充活水池
        for code in sorted_hot:
            if code not in pool_symbols and len(pool_symbols) < max_size:
                pool_symbols.append(code)
                pool_details.append({
                    "symbol": code,
                    "name": self.get_sym_name(code),
                    "reason": f"🔥 近 {len(recent_files)} 日内霸榜全市场成交额 Top10 共 {hot_counter[code]} 次"
                })

        # 💡 新增：保存股票池和入选理由给前端展示
        os.makedirs(os.path.dirname(self.pool_file), exist_ok=True)
        with open(self.pool_file, 'w', encoding='utf-8') as f:
            json.dump(pool_details, f, indent=4, ensure_ascii=False)

        return pool_symbols, len(recent_files)