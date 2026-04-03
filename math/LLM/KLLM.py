
from transformers import GPT2Config, GPT2Model, Trainer, TrainingArguments
import pandas as pd                      # 数据表格处理核心库
from sqlalchemy import create_engine      # 数据库读写工具
import numpy as np                       # 数值计算核心库
import os                                # 文件/目录管理工具
import torch                             # 深度学习框架（GPU加速）
from torch.utils.data import Dataset, DataLoader  # 时序数据加载器                        # 随机数控制工具
import warnings                          # 警告屏蔽工具
warnings.filterwarnings('ignore')        # 关闭无关警告，保证输出整洁
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import talib as ta
DB_URL = "sqlite:///stock_data.db"        # 本地股票数据库路径
CSV_DIR = "stock_data"                   # CSV文件存储目录
ENGINE = create_engine(DB_URL)           # 数据库连接引擎
os.makedirs(CSV_DIR, exist_ok=True)      # 自动创建存储目录
CODE = "300502"

def load_data(symbol, source="db"):
    try:
        if source == "db":
            return pd.read_sql(f"SELECT * FROM stock_{symbol}", ENGINE)
        else:
            return pd.read_csv(f"{CSV_DIR}/stock_{symbol}.csv")
    except:
        return None  # 读取失败返回空，保证程序不崩溃


def build_base_features(df):
    df = df.copy().reset_index(drop=True)
    close, high, low, open_ = df["close"], df["high"], df["low"], df["open"]
    volume, amount = df["volume"], df["amount"]

    # ==================================================================================
    # 【1】趋势因子 Trend Factors
    # 核心：判断趋势方向、强度、稳定性
    # ==================================================================================
    # 收益率
    for i in [1, 2, 3, 5, 10]:
        df[f"ret_{i}"] = close.pct_change(i)

    # 均线
    for t in [5, 10, 20, 30, 60]:
        df[f"ma{t}"] = close.rolling(t).mean()

    # 动量
    for t in [5, 10, 20]:
        df[f"mom_{t}"] = close / (close.shift(t) + 1e-8) - 1

    # 趋势稳定性（线性相关系数）
    df["trend_stability"] = close.rolling(20).apply(
        lambda x: np.corrcoef(range(len(x)), x)[0, 1] if len(x) == 20 else np.nan
    )

    # ==================================================================================
    # 【2】资金因子 Flow & Money Factors
    # 核心：资金进出、放量缩量、主力行为
    # ==================================================================================
    # 成交量强度
    for t in [5, 10, 20]:
        df[f"vol_ma_{t}"] = volume.rolling(t).mean()
        df[f"vol_ratio_{t}"] = volume / (df[f"vol_ma_{t}"] + 1e-8)
        df[f"amount_ratio_{t}"] = amount / (amount.rolling(t).mean() + 1e-8)

    # 成交量脉冲（主力启动）
    df["volume_spike"] = volume / (volume.rolling(30).mean() + 1e-8)

    # 资金流
    df["money_flow"] = (close - open_) * volume
    df["money_flow_ma"] = df["money_flow"].rolling(10).mean()

    # 价量相关性（上涨放量、下跌缩量）
    df["price_vol_corr"] = close.pct_change().rolling(10).corr(volume)

    # 换手率加速度
    df["turnover_acceleration"] = df["turnover"].pct_change(5)

    # ==================================================================================
    # 【3】筹码因子 Chip & Cost Factors（机构顶级重要）
    # 核心：市场平均成本、获利盘、筹码集中度
    # ==================================================================================
    # 全局 成交量加权平均价 VWAP
    df["vwap"] = amount.cumsum() / (volume.cumsum() + 1e-8)

    # 滚动 成交量加权平均价 成本（20/60/120 日 机构标准）
    df["vwap_20"] = amount.rolling(20).sum() / (volume.rolling(20).sum() + 1e-8)
    df["vwap_60"] = amount.rolling(60).sum() / (volume.rolling(60).sum() + 1e-8)
    df["vwap_120"] = amount.rolling(120).sum() / (volume.rolling(120).sum() + 1e-8)

    # 价格相对成本偏离
    df["cost_bias"] = close / df["vwap"] - 1
    df["bias_vwap_20"] = close / df["vwap_20"] - 1
    df["bias_vwap_60"] = close / df["vwap_60"] - 1
    df["bias_vwap_120"] = close / df["vwap_120"] - 1

    # 筹码集中度
    df["price_std_20"] = close.rolling(20).std()
    df["chip_concentration"] = 1 / (df["price_std_20"] + 1e-8)

    # 获利盘比例（主力控盘）
    df["profit_ratio"] = (close > df["vwap"]).rolling(20).mean()

    # ==================================================================================
    # 【4】波动率因子 Volatility Factors
    # 核心：波动大小、波动结构、突破、风险
    # ==================================================================================
    # 标准差
    for t in [5, 10, 20]:
        df[f"std_{t}"] = close.rolling(t).std()
        df[f"cv_{t}"] = df[f"std_{t}"] / (close + 1e-8)

    # ATR 真实波幅
    df["atr"] = ta.ATR(high.values, low.values, close.values, timeperiod=14)

    # 波动率突破
    df["volatility_breakout"] = df["std_10"] / (df["std_20"] + 1e-8)

    # ==================================================================================
    # 【5】均值回归因子 Mean Reversion
    # 核心：超买超卖、乖离、情绪极值
    # ==================================================================================
    # 均线乖离
    for t in [5, 10, 20, 30, 60]:
        df[f"ma_diff_{t}"] = close / (df[f"ma{t}"] + 1e-8) - 1
    # 20日乖离与极值（过热/超跌）
    df["bias_20"] = close / df["ma20"] - 1
    df["bias_extreme"] = abs(df["bias_20"])
    # RSI 情绪超买超卖
    df["rsi"] = ta.RSI(close.values, timeperiod=14)
    # ==================================================================================
    # 【6】微观结构因子 Microstructure Factors
    # 核心：K线形态、量价交互、日内结构
    # ==================================================================================
    # K线形态
    df["body"] = (close - open_) / (open_ + 1e-8)
    df["upper_shadow"] = (high - np.maximum(open_, close)) / (close + 1e-8)
    df["lower_shadow"] = (np.minimum(open_, close) - low) / (close + 1e-8)
    df["range"] = (high - low) / (close + 1e-8)
    df["close_pos"] = (close - low) / (high - low + 1e-8)
    # 量价共振交互
    df["vol_x_ret"] = df["vol_ratio_5"] * df["ret_5"]
    df["mom_x_vol"] = df["mom_10"] * df["cv_10"]
    df["range_x_vol"] = df["range"] * df["vol_ratio_5"]
    df["body_x_mom"] = df["body"] * df["mom_5"]
    # ==================================================================================
    # ==================================================================================
    # 【8】均线交叉与距离（MA Spreading）
    # 核心：捕捉多头/空头排列的发散程度，判断超买超卖
    # ==================================================================================
    # 1. 均线距离（也叫乖离率的变体）：短期均线偏离长期均线的比例
    df["ma_5_20_spread"] = (df["ma5"] - df["ma20"]) / (df["ma20"] + 1e-8)
    df["ma_20_60_spread"] = (df["ma20"] - df["ma60"]) / (df["ma60"] + 1e-8)

    # 2. 均线斜率（Slope）：判断趋势的“加速度”
    # 逻辑：今天ma5比昨天ma5涨了百分之几
    df["ma5_slope"] = df["ma5"].pct_change(1)
    df["ma20_slope"] = df["ma20"].pct_change(1)

    # 3. 均线挤压（Squeeze）：判断是否即将变盘
    # 逻辑：多条均线的标准差。标准差越小，说明均线越粘合，爆发力可能越强。
    df["ma_squeeze"] = df[["ma5", "ma10", "ma20"]].std(axis=1) / (
                df["ma20"] + 1e-8)  # ==================================================================================
    # 【7】非线性数学变换（增强 AI 识别能力）
    # 核心：处理金融数据长尾分布、压缩极端异常值、模拟复合逻辑
    # ==================================================================================

    # 1. 对数变换（Log Transform）：主要针对成交量和成交额
    # 目的：将指数级增长的数据拉回到线性区间，防止巨大的成交量冲偏 AI 权重
    df["log_vol"] = np.log1p(volume)
    df["log_amt"] = np.log1p(amount)

    # 2. 差分对数（Log Return）：模拟复合增长率
    df["log_ret_5"] = np.log(close / (close.shift(5) + 1e-8))

    # 3. 波动率调整收益率（Volatility Scaled Return / Sharpe-like）
    # 核心：涨得稳比涨得猛更重要。将收益率除以波动率。
    for t in [5, 10]:
        # 逻辑：收益率 / 波动率 = 风险调整后的动量
        df[f"norm_ret_{t}"] = df[f"ret_{t}"] / (df[f"cv_{t}"] + 1e-8)

    # 4. 幂变换（Power / Sqrt Transform）：处理波动
    # 目的：模拟价格波动的非线性感知，减弱尖峰
    df["sqrt_atr"] = np.sqrt(df["atr"])

    # 5. 符号映射（Sign Interaction）：判断方向的共振
    # 逻辑：如果 5日收益和 20日偏离同向，赋予更高权重
    df["direction_sync"] = np.sign(df["ret_5"]) * np.sign(df["bias_20"])

    # 6. 软截断（Sigmoid-like Transformation）：
    # 逻辑：将无穷大的乖离率压缩到 [-1, 1] 之间，防止过大的 Bias 导致模型梯度爆炸
    # 使用 np.tanh 模拟 sigmoid 效果
    df["scaled_bias_60"] = np.tanh(df["bias_vwap_60"] * 10)

    # 7. 相对排名（Rolling Rank）：
    # 逻辑：价格在过去 60 天处于什么位置（0到1之间）
    # 这是机构最喜欢的“时序分位数”因子
    df["price_rank_60"] = close.rolling(60).rank(pct=True)
    df["vol_rank_20"] = volume.rolling(20).rank(pct=True)

    # ==================================================================================
    # ==================================================================================
    # 【9】成交量深度变化（Volume Dynamics）
    # 核心：识别“放量滞涨”或“缩量过顶”
    # ==================================================================================
    # 1. 成交量变化率（ROC）
    df["vol_change_3"] = volume.pct_change(3)  # 3日成交量变化
    df["vol_change_5"] = volume.pct_change(5)  # 5日成交量变化

    # 2. 量价背离因子（Price-Volume Divergence）
    # 逻辑：价格涨幅 / 成交量涨幅。如果价格猛涨但量缩，数值会很大，预示风险。
    df["pv_divergence"] = df["ret_1"] / (volume.pct_change(1) + 1e-8)

    # 3. 换手率相对强度
    # 逻辑：当前的换手率在过去一段时间的排名（0-1之间）
    df["turnover_rank_10"] = df["turnover"].rolling(10).rank(pct=True)

    # 4. 能量潮（OBV）的变体：累积成交量
    # 简单的 OBV 逻辑
    df["obv_delta"] = np.where(df["ret_1"] > 0, volume, -volume)
    df["obv_ma_diff"] = df["obv_delta"].rolling(10).mean() / (volume.rolling(10).mean() + 1e-8)

    # ==================================================================================

    df = df.dropna().reset_index(drop=True)
    return df


# --- 1) Load data ---
df = load_data(CODE, "db")
df = build_base_features(df)
df = df.replace([np.inf, -np.inf], 0).dropna()

# --- 2) Feature engineering ---
features = ["open","high","low","close","volume","amount"]
data = df[features].values.astype(np.float32)



# 标准化
data = (data - data.mean(axis=0)) / (data.std(axis=0) + 1e-9)

# ========= 窗口切片 =========
window = 60
sequences = []

for i in range(len(data)-window):
    seq = data[i:i+window]
    sequences.append(seq)

sequences = np.stack(sequences)

# ========= Dataset =========
class KlineDataset(Dataset):
    def __init__(self, seqs):
        self.seqs = torch.tensor(seqs)

    def __len__(self):
        return len(self.seqs)

    def __getitem__(self, idx):
        x = self.seqs[idx]
        return {
            "inputs_embeds": x,
            "labels": x
        }

dataset = KlineDataset(sequences)

# ========= 模型 =========
class KLLM(torch.nn.Module):
    def __init__(self, feature_dim):
        super().__init__()

        config = GPT2Config(
            n_embd=128,
            n_layer=4,
            n_head=4,
            n_positions=window
        )

        self.encoder = torch.nn.Linear(feature_dim, 128)
        self.transformer = GPT2Model(config)
        self.head = torch.nn.Linear(128, feature_dim)

    def forward(self, inputs_embeds, labels=None):
        x = self.encoder(inputs_embeds)

        out = self.transformer(inputs_embeds=x).last_hidden_state
        pred = self.head(out)

        loss = None
        if labels is not None:
            loss = torch.nn.functional.mse_loss(pred, labels)

        return {"loss": loss, "logits": pred}

model = KLLM(feature_dim=len(features))

# ========= 训练 =========
training_args = TrainingArguments(
    output_dir="./ckpt",
    per_device_train_batch_size=32,
    num_train_epochs=50,
    learning_rate=1e-4,
    logging_steps=50
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset
)

trainer.train()



model.eval()

features = []

device = next(model.parameters()).device

with torch.no_grad():
    for i in range(len(dataset)):
        batch = dataset[i]["inputs_embeds"].unsqueeze(0)
        batch = batch.to(device)
        x = model.encoder(batch)
        out = model.transformer(inputs_embeds=x).last_hidden_state

        vec = out.mean(dim=1)  # sequence embedding
        # features.append(vec.squeeze().numpy())
        features.append(vec.squeeze().cpu().numpy())

features = np.array(features)

print("feature shape:", features.shape)

# 降维
pca = PCA(n_components=2)
reduced = pca.fit_transform(features)

# 聚类
kmeans = KMeans(n_clusters=15)
labels = kmeans.fit_predict(features)

print("发现市场模式数量:", len(set(labels)))
print(labels)

df_test = df.iloc[-len(labels):].copy()
df_test["regime"] = labels

df_test["ret"] = df_test["close"].pct_change()

print(df_test.groupby("regime")["ret"].mean())
print(df_test.groupby("regime")["ret"].std())


def analyze_regime_profitability(df_test, next_days=5):
    """
    分析每个模式出现后，未来 N 天的预期收益和稳定性
    """
    # 计算未来 N 天的累积收益率
    df_test['future_ret'] = df_test['close'].shift(-next_days) / df_test['close'] - 1

    # 按 regime 分组统计
    regime_stats = df_test.groupby('regime').agg({
        'future_ret': ['mean', 'std', 'count'],
        'vol_ratio_5': 'mean',  # 观察该模式是否伴随放量
        'cost_bias': 'mean'  # 观察价格是否偏离平均成本
    })

    # 定义“猎人指纹”：高胜率、高收益、且具有统计显著性的模式
    regime_stats['sharpe'] = regime_stats[('future_ret', 'mean')] / (regime_stats[('future_ret', 'std')] + 1e-8)

    # 筛选出样本数足够且表现异常的模式
    hunter_patterns = regime_stats[regime_stats[('future_ret', 'count')] > 5].sort_values(by='sharpe', ascending=False)

    return hunter_patterns


# 执行分析
hunter_modes = analyze_regime_profitability(df_test)
print("潜在的操纵/获利模式 Top 5:")
print(hunter_modes.head(5))

# ==============================
# ✅ 纯数据驱动 · 自动翻译 K线模式
# 不加入任何人工判断，只看：未来收益 + 风险 + 胜率
# ==============================


# ==============================
# ✅ 修复版：纯数据驱动 · 自动翻译 K线模式
# 不报错 | 只看未来收益 + 风险 + 夏普比率
# ==============================
def interpret_regime_auto(regime_id, future_ret_mean, future_ret_std, sharpe, sample_count):
    desc = []

    # 收益
    if future_ret_mean > 0.08:
        desc.append("【超高收益】")
    elif future_ret_mean > 0.02:
        desc.append("【高收益】")
    elif future_ret_mean > 0.005:
        desc.append("【正收益】")
    elif future_ret_mean > -0.005:
        desc.append("【震荡中性】")
    else:
        desc.append("【负收益】")

    # 风险
    if future_ret_std < 0.04:
        desc.append("【极低风险】")
    elif future_ret_std < 0.08:
        desc.append("【低风险】")
    elif future_ret_std < 0.15:
        desc.append("【中风险】")
    else:
        desc.append("【高风险】")

    # 性价比（自动提取数值，避免报错）
    sharpe_val = float(sharpe)
    if sharpe_val > 2.0:
        desc.append("【极品策略】胜率极高")
    elif sharpe_val > 1.0:
        desc.append("【优质策略】")
    elif sharpe_val > 0.2:
        desc.append("【可参与】")
    else:
        desc.append("【性价比差】")

    # 样本可靠性
    if sample_count < 5:
        desc.append("⚠ 样本不足")

    return f"模式 {regime_id}：{' | '.join(desc)}"


# ======================
# 输出（已修复不报错）
# ======================
print("\n" + "=" * 60)
print("🤖 模型自动解读 K线形态（纯数据驱动 · 无人工判断）")
print("=" * 60)

hunter_modes = analyze_regime_profitability(df_test, next_days=5)

for idx, row in hunter_modes.iterrows():
    regime_id = int(idx)

    # 正确提取数值（修复关键）
    mean_ret = float(row[('future_ret', 'mean')])
    std_ret = float(row[('future_ret', 'std')])
    count = int(row[('future_ret', 'count')])
    sharpe = float(row['sharpe'])

    text = interpret_regime_auto(regime_id, mean_ret, std_ret, sharpe, count)
    print(text)