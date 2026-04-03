import numpy as np
import pandas as pd
import talib as ta  # 技术指标库

class FactorGenerator:
    """
    多因子生成器（量化策略专用）
    输出：标准化、无缺失值、可直接用于训练/回测的因子矩阵
    """

    @staticmethod
    def generate_basic_factors(df: pd.DataFrame) -> pd.DataFrame:
        """
        生成全品类基础因子
        :param df: 日线数据，必须包含字段：open, high, low, close, volume, amount, turnover
        :return: 带全量因子的DataFrame
        """
        # ===================== 初始化与安全复制 =====================
        df = df.copy().reset_index(drop=True)

        # 安全提取字段（防止KeyError）
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        open_ = df["open"].values
        volume = df["volume"].values
        amount = df["amount"].values

        # 防0常量
        EPS = 1e-8

        # ==================================================================================
        # 【1】趋势因子 Trend Factors
        # ==================================================================================
        # 收益率
        for i in [1, 2, 3, 5, 10]:
            df[f"ret_{i}"] = pd.Series(close).pct_change(i)

        # 均线
        for t in [5, 10, 20, 30, 60]:
            df[f"ma{t}"] = pd.Series(close).rolling(t).mean()

        # 动量
        for t in [5, 10, 20]:
            df[f"mom_{t}"] = close / (pd.Series(close).shift(t).values + EPS) - 1

        # 趋势稳定性（向量化加速，替代慢循环）
        df["trend_stability"] = FactorGenerator._rolling_corr(
            pd.Series(close), window=20
        )

        # ==================================================================================
        # 【2】资金与量价因子 Flow & Volume Factors
        # ==================================================================================
        # 成交量强度
        for t in [5, 10, 20]:
            vol_ma = pd.Series(volume).rolling(t).mean()
            df[f"vol_ma_{t}"] = vol_ma
            df[f"vol_ratio_{t}"] = volume / (vol_ma + EPS)
            df[f"amount_ratio_{t}"] = amount / (pd.Series(amount).rolling(t).mean() + EPS)

        # 成交量脉冲
        df["volume_spike"] = volume / (pd.Series(volume).rolling(30).mean() + EPS)

        # 资金流
        df["money_flow"] = (close - open_) * volume
        df["money_flow_ma"] = pd.Series(df["money_flow"]).rolling(10).mean()

        # 价量相关性
        df["price_vol_corr"] = pd.Series(close).pct_change().rolling(10).corr(pd.Series(volume))


        # ==================================================================================
        # 【3】筹码与成本因子 Chip & VWAP Factors（机构核心）
        # ==================================================================================
        # 全局VWAP
        df["vwap"] = np.cumsum(amount) / (np.cumsum(volume) + EPS)

        # 滚动VWAP
        df["vwap_20"] = pd.Series(amount).rolling(20).sum() / (pd.Series(volume).rolling(20).sum() + EPS)
        df["vwap_60"] = pd.Series(amount).rolling(60).sum() / (pd.Series(volume).rolling(60).sum() + EPS)
        df["vwap_120"] = pd.Series(amount).rolling(120).sum() / (pd.Series(volume).rolling(120).sum() + EPS)

        # 价格偏离成本
        df["cost_bias"] = close / (df["vwap"] + EPS) - 1
        df["bias_vwap_20"] = close / (df["vwap_20"] + EPS) - 1
        df["bias_vwap_60"] = close / (df["vwap_60"] + EPS) - 1
        df["bias_vwap_120"] = close / (df["vwap_120"] + EPS) - 1

        # 筹码集中度
        df["price_std_20"] = pd.Series(close).rolling(20).std()
        df["chip_concentration"] = 1 / (df["price_std_20"] + EPS)

        # 获利盘比例
        df["profit_ratio"] = (pd.Series(close) > df["vwap"]).rolling(20).mean()

        # ==================================================================================
        # 【4】波动率因子 Volatility Factors
        # ==================================================================================
        # 标准差 & 变异系数
        for t in [5, 10, 20]:
            df[f"std_{t}"] = pd.Series(close).rolling(t).std()
            df[f"cv_{t}"] = df[f"std_{t}"] / (close + EPS)

        # ATR 真实波幅
        df["atr"] = ta.ATR(high, low, close, timeperiod=14)

        # 波动率突破
        df["volatility_breakout"] = df["std_10"] / (df["std_20"] + EPS)

        # ==================================================================================
        # 【5】均值回归因子 Mean Reversion
        # ==================================================================================
        # 均线乖离
        for t in [5, 10, 20, 30, 60]:
            df[f"ma_diff_{t}"] = close / (df[f"ma{t}"] + EPS) - 1

        df["bias_20"] = close / (df["ma20"] + EPS) - 1
        df["bias_extreme"] = np.abs(df["bias_20"])

        # RSI 超买超卖
        df["rsi"] = ta.RSI(close, timeperiod=14)

        # ==================================================================================
        # 【6】微观结构因子 Microstructure Factors
        # ==================================================================================
        df["body"] = (close - open_) / (open_ + EPS)
        df["upper_shadow"] = (high - np.maximum(open_, close)) / (close + EPS)
        df["lower_shadow"] = (np.minimum(open_, close) - low) / (close + EPS)
        df["range"] = (high - low) / (close + EPS)
        df["close_pos"] = (close - low) / (high - low + EPS)

        # 量价交互
        df["vol_x_ret"] = df["vol_ratio_5"] * df["ret_5"]
        df["mom_x_vol"] = df["mom_10"] * df["cv_10"]
        df["range_x_vol"] = df["range"] * df["vol_ratio_5"]
        df["body_x_mom"] = df["body"] * df["mom_5"]

        # ==================================================================================
        # 【7】均线交叉与趋势结构 MA Structure
        # ==================================================================================
        df["ma_5_20_spread"] = (df["ma5"] - df["ma20"]) / (df["ma20"] + EPS)
        df["ma_20_60_spread"] = (df["ma20"] - df["ma60"]) / (df["ma60"] + EPS)
        df["ma5_slope"] = df["ma5"].pct_change(1)
        df["ma20_slope"] = df["ma20"].pct_change(1)
        df["ma_squeeze"] = df[["ma5", "ma10", "ma20"]].std(axis=1) / (df["ma20"] + EPS)

        # ==================================================================================
        # 【8】非线性数学变换（AI模型增强）Non-linear Transform
        # ==================================================================================
        df["log_vol"] = np.log1p(volume)
        df["log_amt"] = np.log1p(amount)
        df["log_ret_5"] = np.log(close / (pd.Series(close).shift(5).values + EPS))

        # 风险调整收益
        for t in [5, 10]:
            df[f"norm_ret_{t}"] = df[f"ret_{t}"] / (df[f"cv_{t}"] + EPS)

        df["sqrt_atr"] = np.sqrt(df["atr"])
        df["direction_sync"] = np.sign(df["ret_5"]) * np.sign(df["bias_20"])
        df["scaled_bias_60"] = np.tanh(df["bias_vwap_60"] * 10)
        df["price_rank_60"] = pd.Series(close).rolling(60).rank(pct=True)
        df["vol_rank_20"] = pd.Series(volume).rolling(20).rank(pct=True)

        # ==================================================================================
        # 【9】成交量动态与背离因子 Volume Dynamics
        # ==================================================================================
        df["vol_change_3"] = pd.Series(volume).pct_change(3)
        df["vol_change_5"] = pd.Series(volume).pct_change(5)
        df["pv_divergence"] = df["ret_1"] / (pd.Series(volume).pct_change(1) + EPS)

        # OBV 能量潮
        df["obv_delta"] = np.where(df["ret_1"] > 0, volume, -volume)
        df["obv_ma_diff"] = pd.Series(df["obv_delta"]).rolling(10).mean() / (pd.Series(volume).rolling(10).mean() + EPS)

        # ==================================================================================
        # 清洗输出
        # ==================================================================================
        df = df.replace([np.inf, -np.inf], np.nan)  # 清除无穷值
        df = df.replace([np.inf, -np.inf], np.nan).fillna(method='ffill').fillna(0)
        # df = df.dropna().reset_index(drop=True)     # 去空值
        return df

    @staticmethod
    def _rolling_corr(series: pd.Series, window: int) -> pd.Series:
        """向量化滚动相关系数（替代极慢的apply）"""
        x = np.arange(window)
        result = []
        for i in range(len(series)):
            if i < window - 1:
                result.append(np.nan)
            else:
                y = series.iloc[i - window + 1: i + 1].values
                corr = np.corrcoef(x, y)[0, 1]
                result.append(corr if np.isfinite(corr) else np.nan)
        return pd.Series(result, index=series.index)

# ===================== 测试运行 =====================
if __name__ == "__main__":
    import pandas as pd
    from sqlalchemy import create_engine

    # 初始化
    fg = FactorGenerator()
    engine = create_engine('sqlite:///quant_factor_data.db')

    # ===================== 配置 =====================
    symbol = "000001"          # 单股票
    # symbol_list = ["000001", "600000", "000333"]  # 多股票

    # 读取单只股票数据并生成因子
    df = pd.read_sql(f"SELECT * FROM daily_{symbol}", engine)
    print(df.head())
    df_factor = fg.generate_basic_factors(df)
    print(f"股票 {symbol} 因子生成完成，共 {len(df_factor)} 行，{len(df_factor.columns)} 个因子")
    print(df_factor)