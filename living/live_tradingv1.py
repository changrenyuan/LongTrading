import os
import glob
import json
import pandas as pd
from datetime import datetime

# ==========================================
# 🔴 核心模块导入：绝不瞎写，完全复用量化实验室的成果！
# ==========================================
from data_provider.akshare_pd import AkShareProvider
from strategies.trend import InstitutionalTrendStrategy
from utils.logger import global_logger as logger

ACCOUNT_FILE = "../data/live_account.json"


def get_latest_live_params(log_dir="data/tuning_logs"):
    """
    自动寻找最新的量化实验室战报 (CSV)，并提取 Top 1 的圣杯参数！
    """
    csv_files = glob.glob(f"{log_dir}/optuna_log_*.csv") + glob.glob("optuna_log_*.csv")

    if not csv_files:
        logger.warning("未找到调参日志，将使用备用默认参数！")
        return {
            'ma_short': 5, 'ma_mid': 12, 'ma_long': 50,
            'bias_entry_limit': 1.05, 'pullback_support_upper': 1.04,
            'stop_loss_pct': 0.10, 'trailing_stop_pct': 0.20,
            'profit_tier2': 1.10, 'trailing_tier2': 0.06,
        }

    latest_csv = max(csv_files, key=os.path.getmtime)
    logger.info(f"🧠 正在加载最新量化实验室战报: {latest_csv}")

    try:
        df = pd.read_csv(latest_csv)
        top1 = df.sort_values(by="value", ascending=False).iloc[0]

        live_params = {}
        for col in top1.index:
            if col.startswith("params_"):
                key = col.replace("params_", "")
                val = top1[col]
                if pd.isna(val): continue
                if isinstance(val, float) and val.is_integer():
                    live_params[key] = int(val)
                else:
                    live_params[key] = val

        # 补全定海神针 (匹配 trend.py 的 STRATEGY_PARAMS)
        base_cfg = {
            'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9, 'vol_ma_window': 20,
            'trend_ma_diff': 5, 'trend_strength_buffer': 1.05,
            'pullback_bias_limit': 1.05, 'pullback_support_lower': 0.95,
            'trend_broken_lower': 0.98, 'trend_broken_vol': 1.2,
            'lot_size': 100, 'est_commission': 0.0003,
            'enable_partial_exit': False  # 实盘建议先关掉分批止盈，方便老板挂单
        }
        live_params.update(base_cfg)

        if 'unit_size' in live_params:
            live_params['max_units'] = int(1.0 // live_params['unit_size'])

        return live_params

    except Exception as e:
        logger.error(f"读取参数失败 ({e})，程序终止！")
        return None


def get_live_target_pool(top_n=50):
    """提取实盘关注的股票池，并返回【代码: 名称】的字典映射"""
    logger.info(f"📡 正在扫描全市场成交额 Top {top_n}，匹配公司名称...")
    csv_files = glob.glob("data_provider/test_cache_data/*spot*.csv") + glob.glob(
        "data_provider/test_cache_data/*snapshot*.csv") + glob.glob("data/*snapshot*.csv")

    if not csv_files:
        logger.warning("未找到本地全景快照，使用兜底股票...")
        return ["300308", "601138"], {"300308": "中际旭创", "601138": "工业富联"}

    csv_path = csv_files[0]
    try:
        spot_df = pd.read_csv(csv_path, dtype=str)
        code_col = '代码' if '代码' in spot_df.columns else 'symbol'
        amount_col = '成交额' if '成交额' in spot_df.columns else 'amount'
        name_col = '名称' if '名称' in spot_df.columns else 'name'

        spot_df['clean_code'] = spot_df[code_col].str.extract(r'(\d{6})')
        spot_df = spot_df.dropna(subset=['clean_code'])
        if name_col in spot_df.columns:
            spot_df = spot_df[~spot_df[name_col].astype(str).str.contains('ST')]
        spot_df = spot_df[spot_df['clean_code'].str.startswith(('60', '00', '30'))]
        spot_df[amount_col] = pd.to_numeric(spot_df[amount_col], errors='coerce').fillna(0)
        spot_df = spot_df.sort_values(by=amount_col, ascending=False).head(top_n)

        symbols = spot_df['clean_code'].tolist()
        symbol_names = dict(zip(spot_df['clean_code'], spot_df[name_col])) if name_col in spot_df.columns else {s: s for
                                                                                                                s in
                                                                                                                symbols}
        return symbols, symbol_names
    except Exception as e:
        logger.error(f"提取股票失败: {e}")
        return [], {}


class LiveTradingDesk:
    def __init__(self, symbols, symbol_names, live_cfg, total_capital=1000000):
        self.symbols = symbols
        self.symbol_names = symbol_names
        self.live_cfg = live_cfg
        self.total_capital = total_capital
        self.provider = AkShareProvider()

        # 🟢 100% 实例化你写好的策略大脑
        self.strategy = InstitutionalTrendStrategy(cfg=live_cfg, symbols=symbols)
        self.account = self._load_account()

    def _load_account(self):
        if os.path.exists(ACCOUNT_FILE):
            with open(ACCOUNT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            default_account = {"cash": self.total_capital, "positions": {}}
            os.makedirs(os.path.dirname(ACCOUNT_FILE), exist_ok=True)
            with open(ACCOUNT_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_account, f, indent=4, ensure_ascii=False)
            return default_account

    def _save_account(self):
        with open(ACCOUNT_FILE, 'w', encoding='utf-8') as f: json.dump(self.account, f, indent=4, ensure_ascii=False)

    def generate_tomorrow_orders(self):
        print(f"正在拉取 {len(self.symbols)} 只标的数据，准备生成老板专属战报...\n")

        buy_orders = []
        sell_orders = []
        hold_reports = []

        # ========================================================
        # 🔴 关键修复：完全按照回测引擎的逻辑，批量准备数据喂给大脑！
        # ========================================================
        data_dict = {}
        for symbol in self.symbols:
            df = self.provider.get_data(symbol)
            if not df.empty and len(df) >= self.live_cfg['ma_long']:
                data_dict[symbol] = df

        if not data_dict:
            logger.error("所有目标股票数据拉取失败或数据长度不足！")
            return

        # 真正调用 trend.py 里面的 prepare 方法，一次性算出所有指标！
        try:
            indicators_dict = self.strategy.prepare(data_dict)
        except Exception as e:
            logger.error(f"策略大脑指标计算异常: {e}")
            return

        # 遍历计算好的结果，生成实盘指令
        for symbol, df_analyzed in indicators_dict.items():
            name = self.symbol_names.get(symbol, symbol)
            today = df_analyzed.iloc[-1]

            current_price = float(today['close'])
            ma_mid = float(today['MA_Mid'])

            # --- 场景 A：检查手中持有的股票 ---
            if symbol in self.account['positions']:
                pos = self.account['positions'][symbol]
                cost = float(pos['cost'])
                high_watermark = float(pos['high'])

                if current_price > high_watermark:
                    self.account['positions'][symbol]['high'] = current_price
                    high_watermark = current_price
                    self._save_account()

                profit_pct = (current_price - cost) / cost
                drawdown_from_high = (high_watermark - current_price) / high_watermark

                # 计算精确的具体退场价格（供老板设条件单）
                hard_stop_price = cost * (1 - self.live_cfg['stop_loss_pct'])
                trailing_limit = self.live_cfg['trailing_tier2'] if profit_pct >= self.live_cfg['profit_tier2'] else \
                self.live_cfg['trailing_stop_pct']
                trailing_stop_price = high_watermark * (1 - trailing_limit)
                actual_stop_price = max(hard_stop_price, trailing_stop_price,
                                        ma_mid * self.live_cfg['trend_broken_lower'])

                # 判定卖出
                if current_price <= actual_stop_price or today['Trend_Broken']:
                    sell_orders.append(
                        f"🔴 {symbol} ({name})\n"
                        f"   - 当日价格: {current_price:.2f} 元  | 持仓成本: {cost:.2f} 元\n"
                        f"   - 卖出指令: 明日开盘【清仓卖出】！(已触发防守线或均线破位)"
                    )
                else:
                    hold_reports.append(
                        f"🛡️ {symbol} ({name})\n"
                        f"   - 当日价格: {current_price:.2f} 元  | 浮盈: {profit_pct * 100:.2f}%\n"
                        f"   - 券商条件单设置建议: 只要跌破 【{actual_stop_price:.2f} 元】 自动卖出防守！"
                    )

            # --- 场景 B：捕捉空仓雷达买点 ---
            else:
                is_bullish = today.get('Strong_Trend', False)
                bias = today.get('Bias', 999)

                # 完全复刻 trend.py 第146行的买入逻辑：
                ma_cross_up = today.get('MA_Cross_Up', False)
                macd_bullish = today.get('MACD_Bullish', False)
                ma_short_above_mid = float(today['MA_Short']) > float(today['MA_Mid'])

                # 买入条件：多头趋势 且 乖离率达标 且 (短线上穿中线 或 短线在中线上方且MACD多头)
                if is_bullish and bias < self.live_cfg['bias_entry_limit'] and (
                        ma_cross_up or (ma_short_above_mid and macd_bullish)):
                    max_buy_price = ma_mid * self.live_cfg['bias_entry_limit']
                    initial_stop_price = current_price * (1 - self.live_cfg['stop_loss_pct'])

                    buy_orders.append(
                        f"🟢 {symbol} ({name}) - 【主升浪首次建仓】\n"
                        f"   - 当日收盘: {current_price:.2f} 元\n"
                        f"   - 推荐买入价格: 次日开盘市价 (防追高限价：绝对不可超过 【{max_buy_price:.2f} 元】)\n"
                        f"   - 推荐卖出价格(风控): 建仓后立刻在券商设置 【{initial_stop_price:.2f} 元】 的止损单！"
                    )
                # 额外提示：空中加油与缩量回踩
                elif today.get('Pullback_Support', False):
                    buy_orders.append(
                        f"🟡 {symbol} ({name}) - 【缩量回踩关注】\n"
                        f"   - 当日收盘: {current_price:.2f} 元 (完美回踩生命线，可做低吸加仓备选)"
                    )
                elif today.get('Breakout_Add', False):
                    buy_orders.append(
                        f"🟣 {symbol} ({name}) - 【放量突破关注】\n"
                        f"   - 当日收盘: {current_price:.2f} 元 (高位空中加油，极为强势)"
                    )

        self._print_battle_report(buy_orders, sell_orders, hold_reports)

    def _print_battle_report(self, buy, sell, hold):
        print("\n" + "█" * 80)
        print(f" 🦅 机构量化部 - 每日交易指令审批单 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        print("█" * 80)

        if sell:
            print("\n🚨 【清仓 / 防守指令】(优先级最高)")
            print("-" * 50)
            for order in sell: print(order + "\n")

        if buy:
            print("\n🎯 【买入 / 狙击指令】")
            print("-" * 50)
            for order in buy: print(order + "\n")
            if len([o for o in buy if "🟢" in o]) > 5:
                print(f"⚠️ 注意：建仓信号激增。请老板根据总预算，择优挑选 3-4 只最强龙头执行！\n")

        if hold:
            print("\n📊 【持仓防守线更新】(请同步至券商条件单)")
            print("-" * 50)
            for report in hold: print(report + "\n")

        if not sell and not buy and not hold:
            print("\n ☕ 大盘波澜不惊，雷达未锁定任何目标。老板今日无需操作，喝茶观望。")

        print("█" * 80 + "\n")


def main():
    live_cfg = get_latest_live_params()
    if not live_cfg: return

    target_symbols, symbol_names = get_live_target_pool(top_n=50)

    desk = LiveTradingDesk(symbols=target_symbols, symbol_names=symbol_names, live_cfg=live_cfg)
    desk.generate_tomorrow_orders()


if __name__ == "__main__":
    main()