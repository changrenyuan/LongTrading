# ==========================================
# 因子挖掘 - 掘金量化版本
# 核心用途：从股票量价数据中，通过深度学习自动挖掘高预测性非线性因子
# 适用场景：单股票择时 / 因子研究 / 量化策略开发
# 改造说明：适配掘金量化API，数据源从AkShare改为GM
# ==========================================

# ==========================================
# 模块1：第三方库导入
# ==========================================
import gm.api as gm                        # 掘金量化API（替代AkShare）
import pandas as pd                        # 数据表格处理核心库
import numpy as np                         # 数值计算核心库
import os                                  # 文件/目录管理工具
import torch                               # 深度学习框架（GPU加速）
import torch.nn as nn                      # 神经网络构建模块
from torch.utils.data import Dataset, DataLoader  # 时序数据加载器
from sklearn.preprocessing import StandardScaler  # 数据标准化工具
import random                              # 随机数控制工具
import warnings                            # 警告屏蔽工具
import talib as ta                         # 技术指标库
import time
from datetime import timedelta
gm.set_serv_addr("192.168.3.12:7001")
gm.set_token('aa08f4cebff6539a76396d3f1f4123e5f7d5f108')
warnings.filterwarnings('ignore')

# ==========================================
# 模块2：随机种子固定（实验可复现性）
# ==========================================
seed = 42
torch.manual_seed(seed)
torch.cuda.manual_seed(seed)
torch.cuda.manual_seed_all(seed)
np.random.seed(seed)
random.seed(seed)
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.deterministic = True

# ==========================================
# 模块3：全局参数配置
# ==========================================
CSV_DIR = "stock_data"
os.makedirs(CSV_DIR, exist_ok=True)

SEQ_LEN = 10                             # 时序输入窗口：10日K线
LATENT_DIM = 32                          # 挖掘AI隐因子数量：32个
BATCH_SIZE = 128                         # 训练批次大小
EPOCHS = 150                             # 每窗口训练轮数
TRAIN_WINDOW = 200                       # 滚动训练窗口：200日历史数据
PRED_STEP = 20                           # 滚动预测步长：20日
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ==========================================
# 模块4：股票代码转换工具
# ==========================================
def ak_to_gm_symbol(code: str) -> str:
    """
    将普通股票代码转换为掘金格式
    
    输入: '600519' 或 '300502'
    输出: 'SHSE.600519' 或 'SZSE.300502'
    """
    raw_code = "".join(filter(str.isdigit, str(code)))
    if raw_code.startswith('6'):
        return f"SHSE.{raw_code}"        # 上交所
    elif raw_code.startswith(('0', '3')):
        return f"SZSE.{raw_code}"        # 深交所
    elif raw_code.startswith(('4', '8')):
        return f"BJSE.{raw_code}"        # 北交所
    return code


def gm_to_ak_symbol(gm_symbol: str) -> str:
    """
    将掘金格式转换为普通代码
    
    输入: 'SHSE.600519'
    输出: '600519'
    """
    return gm_symbol.split('.')[-1] if '.' in gm_symbol else gm_symbol


# ==========================================
# 模块5：数据获取（掘金API版本）
# ==========================================
def fetch_stock_data(symbol, start_date, end_date, adjust=gm.ADJUST_PREV, save_csv=True):
    """
    从掘金API获取股票历史数据
    
    参数:
        symbol: 股票代码，支持两种格式
                - '300502' 或 '600519'（自动转换）
                - 'SZSE.300502' 或 'SHSE.600519'（掘金格式）
        start_date: 开始日期，格式 '2019-01-01' 或 '20190101'
        end_date: 结束日期
        adjust: 复权方式
                - gm.ADJUST_PREV: 前复权（默认）
                - gm.ADJUST_POST: 后复权
                - gm.ADJUST_NONE: 不复权
        save_csv: 是否保存到CSV文件
    
    返回:
        DataFrame，包含日期、OHLCV等
    """
    # 转换股票代码格式
    if '.' not in str(symbol):
        gm_symbol = ak_to_gm_symbol(symbol)
    else:
        gm_symbol = symbol
    
    # 格式化日期
    # start_str = str(start_date).replace('-', '')
    # end_str = str(end_date).replace('-', '')
    
    # 从掘金获取数据
    print(f"📥 正在获取 {gm_symbol} 数据 ({start_date} ~ {end_date})...")
    
    df = gm.history(
        symbol=gm_symbol,
        frequency='1d',
        start_time=f"{start_date} 09:30:00",
        end_time=f"{end_date} 15:00:00",
        adjust=adjust,
        df=True
    )
    
    if df is None or len(df) == 0:
        print(f"❌ 获取数据失败：{gm_symbol}")
        return None
    
    # 重命名列（掘金列名 → 标准列名）
    column_map = {
        'eob': 'date',      # 使用 eob (结束时间) 作为日期
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume',
        'amount': 'amount'
    }
        # 只保留需要的列
    keep_cols = ['eob', 'open', 'high', 'low', 'close', 'volume', 'amount']
    df = df[keep_cols].copy()
        # 重命名列
    df = df.rename(columns=column_map)
    
    # 处理日期格式：去掉时区信息，只保留日期
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    # 确保必要的列存在
    required_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
    for col in required_cols:
        if col not in df.columns:
            print(f"❌ 缺少列: {col}")
            return None
    
    # # 添加换手率（如果有）
    # if 'turnover' not in df.columns:
    #     df['turnover'] = 0  # 默认值
    
    # 保存到CSV
    if save_csv:
        csv_path = f"{CSV_DIR}/stock_{gm_to_ak_symbol(gm_symbol)}.csv"
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"✅ 数据已保存: {csv_path}")
    
    print(f"✅ 获取到 {len(df)} 条数据")
    return df


def load_data(symbol, source="gm", start_date='2019-01-01', end_date='2024-12-31'):
    """
    统一数据加载入口
    
    参数:
        symbol: 股票代码
        source: 数据来源
                - "gm": 从掘金API获取（推荐）
                - "csv": 从本地CSV读取
        start_date: 开始日期（仅gm模式有效）
        end_date: 结束日期（仅gm模式有效）
    
    返回:
        DataFrame
    """
    try:
        if source == "gm":
            return fetch_stock_data(symbol, start_date, end_date)
        else:
            code = gm_to_ak_symbol(symbol) if '.' in str(symbol) else symbol
            return pd.read_csv(f"{CSV_DIR}/stock_{code}.csv")
    except Exception as e:
        print(f"❌ 数据加载失败: {e}")
        return None


# ==========================================
# 模块6：基础量价因子生成（保持不变）
# ==========================================
def build_base_features(df):
    """
    从原始K线生成120+个传统量化因子
    
    注意: 需要确保 df 包含以下列:
          - open, high, low, close, volume, amount, turnover
    """
    df = df.copy().reset_index(drop=True)
    
    # 确保必要列存在
    required = ['open', 'high', 'low', 'close', 'volume']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"缺少必要列: {col}")
    
    # 如果缺少 amount，用 close * volume 估算
    if 'amount' not in df.columns:
        df['amount'] = df['close'] * df['volume']
    
    # 如果缺少 turnover，设为默认值
    if 'turnover' not in df.columns:
        df['turnover'] = 0
    
    close, high, low, open_ = df["close"], df["high"], df["low"], df["open"]
    volume, amount = df["volume"], df["amount"]

    # ==================================================================================
    # 【1】趋势因子 Trend Factors
    # ==================================================================================
    for i in [1, 2, 3, 5, 10]:
        df[f"ret_{i}"] = close.pct_change(i)

    for t in [5, 10, 20, 30, 60]:
        df[f"ma{t}"] = close.rolling(t).mean()

    for t in [5, 10, 20]:
        df[f"mom_{t}"] = close / (close.shift(t) + 1e-8) - 1

    df["trend_stability"] = close.rolling(20).apply(
        lambda x: np.corrcoef(range(len(x)), x)[0, 1] if len(x) == 20 else np.nan
    )

    # ==================================================================================
    # 【2】资金因子 Flow & Money Factors
    # ==================================================================================
    for t in [5, 10, 20]:
        df[f"vol_ma_{t}"] = volume.rolling(t).mean()
        df[f"vol_ratio_{t}"] = volume / (df[f"vol_ma_{t}"] + 1e-8)
        df[f"amount_ratio_{t}"] = amount / (amount.rolling(t).mean() + 1e-8)

    df["volume_spike"] = volume / (volume.rolling(30).mean() + 1e-8)
    df["money_flow"] = (close - open_) * volume
    df["money_flow_ma"] = df["money_flow"].rolling(10).mean()
    df["price_vol_corr"] = close.pct_change().rolling(10).corr(volume)
    # df["turnover_acceleration"] = df["turnover"].pct_change(5)

    # ==================================================================================
    # 【3】筹码因子 Chip & Cost Factors
    # ==================================================================================
    df["vwap"] = amount.cumsum() / (volume.cumsum() + 1e-8)
    df["vwap_20"] = amount.rolling(20).sum() / (volume.rolling(20).sum() + 1e-8)
    df["vwap_60"] = amount.rolling(60).sum() / (volume.rolling(60).sum() + 1e-8)
    df["vwap_120"] = amount.rolling(120).sum() / (volume.rolling(120).sum() + 1e-8)

    df["cost_bias"] = close / df["vwap"] - 1
    df["bias_vwap_20"] = close / df["vwap_20"] - 1
    df["bias_vwap_60"] = close / df["vwap_60"] - 1
    df["bias_vwap_120"] = close / df["vwap_120"] - 1

    df["price_std_20"] = close.rolling(20).std()
    df["chip_concentration"] = 1 / (df["price_std_20"] + 1e-8)
    df["profit_ratio"] = (close > df["vwap"]).rolling(20).mean()

    # ==================================================================================
    # 【4】波动率因子 Volatility Factors
    # ==================================================================================
    for t in [5, 10, 20]:
        df[f"std_{t}"] = close.rolling(t).std()
        df[f"cv_{t}"] = df[f"std_{t}"] / (close + 1e-8)

    try:
        df["atr"] = ta.ATR(high.values, low.values, close.values, timeperiod=14)
    except:
        df["atr"] = 0

    df["volatility_breakout"] = df["std_10"] / (df["std_20"] + 1e-8)

    # ==================================================================================
    # 【5】均值回归因子 Mean Reversion
    # ==================================================================================
    for t in [5, 10, 20, 30, 60]:
        df[f"ma_diff_{t}"] = close / (df[f"ma{t}"] + 1e-8) - 1

    df["bias_20"] = close / df["ma20"] - 1
    df["bias_extreme"] = abs(df["bias_20"])

    try:
        df["rsi"] = ta.RSI(close.values, timeperiod=14)
    except:
        df["rsi"] = 50  # 默认中性值

    # ==================================================================================
    # 【6】微观结构因子 Microstructure Factors
    # ==================================================================================
    df["body"] = (close - open_) / (open_ + 1e-8)
    df["upper_shadow"] = (high - np.maximum(open_, close)) / (close + 1e-8)
    df["lower_shadow"] = (np.minimum(open_, close) - low) / (close + 1e-8)
    df["range"] = (high - low) / (close + 1e-8)
    df["close_pos"] = (close - low) / (high - low + 1e-8)

    df["vol_x_ret"] = df["vol_ratio_5"] * df["ret_5"]
    df["mom_x_vol"] = df["mom_10"] * df["cv_10"]
    df["range_x_vol"] = df["range"] * df["vol_ratio_5"]
    df["body_x_mom"] = df["body"] * df["mom_5"]

    # ==================================================================================
    # 【7】均线交叉与距离
    # ==================================================================================
    df["ma_5_20_spread"] = (df["ma5"] - df["ma20"]) / (df["ma20"] + 1e-8)
    df["ma_20_60_spread"] = (df["ma20"] - df["ma60"]) / (df["ma60"] + 1e-8)
    df["ma5_slope"] = df["ma5"].pct_change(1)
    df["ma20_slope"] = df["ma20"].pct_change(1)
    df["ma_squeeze"] = df[["ma5", "ma10", "ma20"]].std(axis=1) / (df["ma20"] + 1e-8)

    # ==================================================================================
    # 【8】非线性数学变换
    # ==================================================================================
    df["log_vol"] = np.log1p(volume)
    df["log_amt"] = np.log1p(amount)
    df["log_ret_5"] = np.log(close / (close.shift(5) + 1e-8))

    for t in [5, 10]:
        df[f"norm_ret_{t}"] = df[f"ret_{t}"] / (df[f"cv_{t}"] + 1e-8)

    try:
        df["sqrt_atr"] = np.sqrt(df["atr"])
    except:
        df["sqrt_atr"] = 0

    df["direction_sync"] = np.sign(df["ret_5"]) * np.sign(df["bias_20"])
    df["scaled_bias_60"] = np.tanh(df["bias_vwap_60"] * 10)
    df["price_rank_60"] = close.rolling(60).rank(pct=True)
    df["vol_rank_20"] = volume.rolling(20).rank(pct=True)

    # ==================================================================================
    # 【9】成交量深度变化
    # ==================================================================================
    df["vol_change_3"] = volume.pct_change(3)
    df["vol_change_5"] = volume.pct_change(5)
    df["pv_divergence"] = df["ret_1"] / (volume.pct_change(1) + 1e-8)
    df["turnover_rank_10"] = df["turnover"].rolling(10).rank(pct=True)
    df["obv_delta"] = np.where(df["ret_1"] > 0, volume, -volume)
    df["obv_ma_diff"] = df["obv_delta"].rolling(10).mean() / (volume.rolling(10).mean() + 1e-8)

    df = df.dropna().reset_index(drop=True)
    return df


# ==========================================
# 模块：时序数据集构建类
# ==========================================
class StockSeqDataset(Dataset):
    def __init__(self, data, seq_len=10):
        self.data = torch.FloatTensor(data)
        self.seq_len = seq_len

    def __len__(self):
        return max(0, len(self.data) - self.seq_len)

    def __getitem__(self, idx):
        return self.data[idx:idx + self.seq_len]


# ==========================================
# 模块：AI深度因子编码器
# ==========================================
class AlphaSeqEncoder(nn.Module):
    def __init__(self, input_dim, latent_dim=32):
        super().__init__()
        self.gru = nn.GRU(input_dim, 512, num_layers=2, batch_first=True, bidirectional=False)
        self.proj = nn.Sequential(
            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.GELU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.GELU(),
            nn.Linear(128, latent_dim)
        )

    def forward(self, x):
        x, _ = self.gru(x)
        return self.proj(x[:, -1, :])


# ==========================================
# 模块：滚动窗口训练
# ==========================================
def walk_forward_latent_features(df, factor_cols):
    df = df.reset_index(drop=True)
    feat_raw = df[factor_cols].values
    n_features = len(factor_cols)
    print(f"📊 原始基础因子数量：{n_features}...")
    
    all_latents = np.zeros((len(df), LATENT_DIM)) * np.nan
    scaler = StandardScaler()

    print("\n🔄 滚动训练（Walk-forward）...")
    start_time = time.time()
    total_steps = len(range(TRAIN_WINDOW, len(df) - SEQ_LEN, PRED_STEP))
    current_step = 0
    print(f"📊 总样本数：{len(df)} ｜ 总滚动轮次：{total_steps}")

    for end_idx in range(TRAIN_WINDOW, len(df) - SEQ_LEN, PRED_STEP):
        current_step += 1
        progress = current_step / total_steps * 100
        elapsed = time.time() - start_time
        eta = elapsed / current_step * (total_steps - current_step) if current_step > 0 else 0
        
        if current_step < 2:
            print(f"\n📌 滚动轮次 [{current_step}/{total_steps}] | 进度 {progress:.1f}%")
        else:
            print(f"\n📌 进度 {progress:.1f}%")

        train_start = end_idx - TRAIN_WINDOW
        train_end = end_idx

        train_feat = feat_raw[train_start:train_end]
        train_feat = scaler.fit_transform(train_feat)
        
        ds = StockSeqDataset(train_feat, SEQ_LEN)
        if len(ds) <= 0: continue
        dl = DataLoader(ds, BATCH_SIZE, shuffle=True)

        model = AlphaSeqEncoder(n_features, LATENT_DIM).to(DEVICE)
        opt = torch.optim.AdamW(model.parameters(), lr=5e-4)
        criterion = nn.MSELoss()

        model.train()
        if current_step < 2:
            print(f"   └─ 开始训练｜Epochs: {EPOCHS}｜Device: {DEVICE.type}")
        
        total_loss = 0.0
        for _ in range(EPOCHS):
            epoch_loss = 0.0
            for batch in dl:
                x = batch.to(DEVICE)
                loss = criterion(model(x), x[:, -1, :LATENT_DIM])
                opt.zero_grad()
                loss.backward()
                opt.step()
                epoch_loss += loss.item()
            avg_loss = epoch_loss / len(dl)
            total_loss += avg_loss
        
        if current_step < 2:
            print(f"   └─ 平均损失: {total_loss / EPOCHS:.4f}")

        pred_start = end_idx
        pred_end = min(end_idx + PRED_STEP, len(df))
        pred_feat = feat_raw[pred_start:pred_end]
        if len(pred_feat) < SEQ_LEN: continue
        
        pred_feat = scaler.transform(pred_feat)
        ds_pred = StockSeqDataset(pred_feat, SEQ_LEN)
        dl_pred = DataLoader(ds_pred, BATCH_SIZE, shuffle=False)

        model.eval()
        lat = []
        with torch.no_grad():
            for b in dl_pred:
                lat.append(model(b.to(DEVICE)).cpu().numpy())
        lat = np.concatenate(lat)

        pos_start = end_idx + SEQ_LEN
        pos_end = pos_start + len(lat)
        if pos_end <= len(all_latents):
            all_latents[pos_start:pos_end] = lat

    total_time = time.time() - start_time
    print(f"✅ 全部滚动训练完成！总耗时：{timedelta(seconds=int(total_time))}")

    for i in range(LATENT_DIM):
        df[f"latent_{i + 1}"] = all_latents[:, i]

    df = df.dropna().reset_index(drop=True)
    return df


# ==========================================
# 模块：IC 分析
# ==========================================
def ic_analysis(df):
    df["target"] = df["close"].shift(-5) / df["close"] - 1
    latent_cols = [c for c in df.columns if c.startswith("latent_")]
    ic_dict = {}
    new_latent_cols = []

    print("\n" + "=" * 50)
    print("📊 AI 隐因子方向对齐与 IC 分析")
    print("=" * 50)

    for col in latent_cols:
        ic = df[col].corr(df["target"], method="spearman")
        
        if ic < 0:
            new_col_name = f"{col}_N"
            df[new_col_name] = -df[col]
            current_ic = -ic
        else:
            new_col_name = f"{col}_P"
            df[new_col_name] = df[col]
            current_ic = ic
        
        df.drop(columns=[col], inplace=True)
        ic_dict[new_col_name] = current_ic
        new_latent_cols.append(new_col_name)
        print(f"{col:10s} | 原始IC: {ic:+.3f} | 对齐后: {new_col_name}")

    best = [c for c, v in ic_dict.items() if v > 0.03]
    best = sorted(best, key=lambda x: ic_dict[x], reverse=True)
    sorted_cols = sorted(new_latent_cols, key=lambda x: ic_dict[x], reverse=True)

    non_latent_cols = [c for c in df.columns if not c.startswith("latent_")]
    df = df[non_latent_cols + sorted_cols]

    print(f"\n🎯 有效因子清单（已对齐至正向）：{best}")
    return df, best, ic_dict


# ==========================================
# 模块：隐因子构成解释
# ==========================================
def explain_latent_factors(df):
    base_cols = [c for c in df.columns if c not in [
        "date", "open", "high", "low", "close", "volume", "amount", "turnover",
        "alpha_score", "signal", "target"
    ] and not c.startswith("latent_")]

    latent_cols = [c for c in df.columns if c.startswith("latent_")]
    
    print("\n" + "=" * 80)
    print("                🔍 隐因子构成解释")
    print("=" * 80)

    for latent in latent_cols[:10]:
        corr = df[base_cols].corrwith(df[latent]).sort_values(ascending=False)
        print(f"\n📌 {latent} 核心构成：")
        print(corr.head(10).round(3))


# ==========================================
# 模块：Alpha交易信号生成
# ==========================================
def build_alpha_signal(df, best_factors):
    df["alpha_score"] = df[best_factors].sum(axis=1)
    df["alpha_score"] = df["alpha_score"].rolling(20).apply(
        lambda x: (x.iloc[-1] - x.mean()) / (x.std() + 1e-8)
    )

    df["signal"] = "观望"
    df.loc[df["alpha_score"] > 1.0, "signal"] = "买入"
    df.loc[df["alpha_score"] < -1.0, "signal"] = "卖出"
    return df


# ==========================================
# 模块：简单回测（掘金框架外）
# ==========================================
def backtest_simple(df):
    """简单的回测逻辑（不使用掘金回测框架）"""
    buy = df[df["signal"] == "买入"]
    if len(buy) == 0:
        print("\n📛 无有效信号")
        return

    profit = []
    win = 0
    for i, row in buy.iterrows():
        c = row["close"]
        f = df.loc[i:i + 5, "close"].mean()
        r = (f - c) / c
        profit.append(r)
        if r > 0:
            win += 1

    print("\n" + "=" * 60)
    print("             回测结果")
    print("=" * 60)
    print(f"信号总数：{len(profit)} 个")
    print(f"预测胜率：{win / len(profit) * 100:.2f}%")
    print(f"单次收益：{np.mean(profit) * 100:.2f}%")
    print(f"累计收益：{np.sum(profit) * 100:.2f}%")


# ==========================================
# 模块：月度IC稳定性分析
# ==========================================
def rolling_ic_stability(df):
    if 'date' not in df.columns:
        print("⚠️ 缺少date列，跳过月度IC分析")
        return
    
    df["yearmonth"] = pd.to_datetime(df["date"]).dt.to_period("M")
    df["target"] = df["close"].shift(-5) / df["close"] - 1

    print("\n" + "=" * 80)
    print("               📈 月度 IC 稳定性")
    print("=" * 80)

    ic_month = df.groupby("yearmonth").apply(
        lambda x: x["alpha_score"].corr(x["target"], method="spearman")
    )
    print(ic_month.round(3))
    print(f"\n✅ IC 均值：{ic_month.mean():.3f} | 标准差：{ic_month.std():.3f}")


# ==========================================
# 模块：因子分层回测
# ==========================================
def factor_group_test(df):
    df["target"] = df["close"].shift(-5) / df["close"] - 1
    df["group"] = pd.qcut(df["alpha_score"], 10, labels=False)

    print("\n" + "=" * 80)
    print("             🏆 因子分层收益")
    print("=" * 80)
    group_ret = df.groupby("group")["target"].mean() * 100
    print(group_ret.round(2))


# ===================== 主流程 =====================
def ai_pipeline(df):
    """完整的AI因子挖掘流程"""
    df = build_base_features(df)
    
    exclude = ["date", "open", "high", "low", "close", "volume", "amount", "target", "turnover"]
    factor_cols = [c for c in df.columns if c not in exclude and not c.startswith("latent")]
    
    df = walk_forward_latent_features(df, factor_cols)
    df, best, ic_dict = ic_analysis(df)
    df = build_alpha_signal(df, best)
    backtest_simple(df)

    explain_latent_factors(df)
    rolling_ic_stability(df)
    factor_group_test(df)
    return df


# ===================== 掘金策略集成示例 =====================
def create_gm_strategy_file(symbol, output_file="ai_factor_strategy.py"):
    """
    生成可在掘金框架中运行的策略文件
    
    参数:
        symbol: 股票代码（如 'SZSE.300502'）
        output_file: 输出的策略文件名
    """
    strategy_code = f'''# coding=utf-8
"""
AI因子挖掘策略 - 掘金量化版本
股票: {symbol}
"""

import gm.api as gm
import pandas as pd
import numpy as np

# 策略参数
SYMBOL = '{symbol}'
HOLDING_DAYS = 5
ALPHA_THRESHOLD_BUY = 1.0
ALPHA_THRESHOLD_SELL = -1.0

def init(context):
    """策略初始化"""
    context.symbol = SYMBOL
    context.holding_days = HOLDING_DAYS
    context.entry_day = None
    
    # 订阅日线数据
    gm.subscribe(symbols=context.symbol, frequency='1d', count=200)
    print(f"✅ 策略初始化完成: {{context.symbol}}")


def on_bar(context, bars):
    """K线回调"""
    bar = bars[0]
    
    # 获取历史数据
    df = gm.history_n(
        symbol=context.symbol,
        frequency='1d',
        count=200,
        fields='open,high,low,close,volume,amount',
        adjust=gm.ADJUST_PREV,
        df=True
    )
    
    if df is None or len(df) < 100:
        return
    
    # TODO: 在这里调用因子计算和信号生成
    # alpha_score = calculate_alpha(df)
    # signal = generate_signal(alpha_score)
    
    # 简单示例：5日均线上穿20日均线买入
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    
    current_price = bar['close']
    ma5 = df['ma5'].iloc[-1]
    ma20 = df['ma20'].iloc[-1]
    prev_ma5 = df['ma5'].iloc[-2]
    prev_ma20 = df['ma20'].iloc[-2]
    
    # 金叉买入
    if prev_ma5 <= prev_ma20 and ma5 > ma20:
        print(f"🔔 金叉信号，买入 {{context.symbol}}")
        gm.order_target_percent(
            symbol=context.symbol,
            percent=0.95,
            order_type=gm.OrderType_Market,
            position_side=gm.PositionSide_Long
        )
        context.entry_day = context.now
    
    # 死叉卖出
    if prev_ma5 >= prev_ma20 and ma5 < ma20:
        print(f"🔔 死叉信号，卖出 {{context.symbol}}")
        gm.order_target_percent(
            symbol=context.symbol,
            percent=0,
            order_type=gm.OrderType_Market,
            position_side=gm.PositionSide_Long
        )
        context.entry_day = None


def on_order_status(context, order):
    """委托状态回调"""
    if order['status'] == 3:
        print(f"✅ 成交: {{order['symbol']}} 价格:{{order['price']}} 数量:{{order['volume']}}")


def on_backtest_finished(context, indicator):
    """回测完成回调"""
    print('*' * 60)
    print('📊 回测绩效摘要')
    print('*' * 60)
    print(f"总收益率: {{indicator.get('pnl_ratio', 0) * 100:.2f}}%")
    print(f"年化收益: {{indicator.get('pnl_ratio_annual', 0) * 100:.2f}}%")
    print(f"最大回撤: {{indicator.get('max_drawdown', 0) * 100:.2f}}%")
'''
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(strategy_code)
    
    print(f"✅ 掘金策略文件已生成: {output_file}")


# ===================== 运行示例 =====================
if __name__ == "__main__":
    # 示例1：获取数据并运行因子挖掘
    print("=" * 60)
    print("AI因子挖掘系统 - 掘金量化版本")
    print("=" * 60)
    
    # 配置掘金连接（如果需要从GM获取数据）
    # gm.set_serv_addr("192.168.3.12:7001")
    # gm.set_token('your_token')
    
    # 股票代码
    CODE = "300502"  # 新易盛
    
    # 方式1：从本地CSV读取（需要先准备好数据）
    # df = load_data(CODE, source="csv")
    
    # 方式2：从掘金API获取（需要先配置连接）
    df = load_data(CODE, source="gm", start_date='2023-01-01', end_date='2026-03-31')
    
    if df is not None:
        print("\n📊 原始数据前5行：")
        print(df.head())

        # 运行AI因子挖掘流程
        df_result = ai_pipeline(df)

        print("\n" + "=" * 60)
        print("              最终交易信号")
        print("=" * 60)
        print(df_result[["date", "close", "alpha_score", "signal"]].tail(15))

        # 保存结果
        df_result.to_csv(f"{CODE}_AI_32因子_掘金版.csv", index=False, encoding="utf-8-sig")
        print(f"\n✅ 全部因子已保存：{CODE}_AI_32因子_掘金版.csv")
        
        # 生成掘金策略文件
        create_gm_strategy_file(ak_to_gm_symbol(CODE))
