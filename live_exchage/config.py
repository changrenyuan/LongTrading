import os
import glob
import pandas as pd
from utils.logger import global_logger as logger

# 💡 核心修复：锁定项目根目录，彻底解决相对路径找不到文件的问题
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class LiveConfig:
    @staticmethod
    def get_latest_live_params(log_dir=None):
        if log_dir is None:
            log_dir = os.path.join(BASE_DIR, "data", "tuning_logs")

        # 使用绝对路径去匹配文件
        csv_files = glob.glob(os.path.join(log_dir, "trials_*.csv")) + \
                    glob.glob(os.path.join(BASE_DIR, "trials_*.csv"))

        base_cfg = {
            'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9, 'vol_ma_window': 20,
            'trend_ma_diff': 5, 'trend_strength_buffer': 1.05, 'pullback_bias_limit': 1.05,
            'pullback_support_lower': 0.95, 'trend_broken_lower': 0.98, 'trend_broken_vol': 1.2,
            'lot_size': 100, 'est_commission': 0.0003, 'enable_partial_exit': False
        }

        if not csv_files:
            logger.warning("未找到调参日志，将使用备用默认参数！")
            live_params = {'ma_short': 5, 'ma_mid': 12, 'ma_long': 50, 'bias_entry_limit': 1.05,
                           'pullback_support_upper': 1.04, 'stop_loss_pct': 0.10, 'trailing_stop_pct': 0.20,
                           'profit_tier2': 1.10, 'trailing_tier2': 0.06}
        else:
            latest_csv = max(csv_files, key=os.path.getmtime)
            df = pd.read_csv(latest_csv)
            top1 = df.sort_values(by="value", ascending=False).iloc[0]

            live_params = {}
            for col in top1.index:
                if col.startswith("params_"):
                    key = col.replace("params_", "")
                    val = top1[col]
                    if pd.isna(val): continue
                    live_params[key] = int(val) if isinstance(val, float) and val.is_integer() else round(val,
                                                                                                          4) if isinstance(
                        val, float) else val

            logger.info("-" * 80)
            logger.info(f"⚙️ 【策略参数装载与核对】 -> 依据: {os.path.basename(latest_csv)}")
            dynamic_params = {k: v for k, v in live_params.items() if k not in base_cfg}
            logger.info(f"   - 注入动态寻优参数 : {', '.join([f'{k}: {v}' for k, v in dynamic_params.items()])}")
            logger.info("-" * 80)

        live_params.update(base_cfg)
        if 'unit_size' in live_params:
            live_params['max_units'] = int(1.0 // live_params['unit_size'])

        return live_params