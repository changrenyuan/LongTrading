import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from scipy.stats import pearsonr
import sqlite3
import os
import gc
import warnings
from sqlalchemy import create_engine
warnings.filterwarnings("ignore")

# ===================== 【全局固定种子：100%可复现】 =====================
SEED = 42
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.cuda.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
os.environ['PYTHONHASHSEED'] = str(SEED)

# --------------------- 导入你的因子生成 ---------------------
from factor import FactorGenerator

# --------------------- 全局配置 ---------------------
DB_PATH = "quant_factor_data.db"
MODEL_SAVE_PATH = "./models/"
CSV_SAVE_PATH = "./latent_factors/"

MAX_DATA_LENGTH = 700
SEQ_LEN = 10
LATENT_DIM = 32
TRAIN_WINDOW = 150
PRED_STEP = 20
EPOCHS = 120
LR = 1e-3
BATCH_SIZE = 128
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

PATIENCE = 3
MIN_DELTA = 1e-6

for path in [MODEL_SAVE_PATH, CSV_SAVE_PATH]:
    if not os.path.exists(path):
        os.makedirs(path)

# ======================================================
# 早停
# ======================================================
class EarlyStopping:
    def __init__(self, patience=PATIENCE, min_delta=MIN_DELTA):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = np.inf
        self.stop = False

    def step(self, val_loss):
        if val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.stop = True

# ======================================================
# 数据集
# ======================================================
class StockDataset(Dataset):
    def __init__(self, X, y, seq_len=10):
        self.X = X
        self.y = y
        self.seq_len = seq_len

    def __len__(self):
        return max(0, len(self.X) - self.seq_len + 1)

    def __getitem__(self, idx):
        x_seq = self.X[idx:idx+self.seq_len]
        y_label = self.y[idx+self.seq_len-1]
        return torch.FloatTensor(x_seq), torch.FloatTensor([y_label])

# ======================================================
# GRU 模型
# ======================================================
class GRUAlphaModel(nn.Module):
    def __init__(self, input_dim, latent_dim=16):
        super().__init__()
        self.gru = nn.GRU(input_dim, 64, num_layers=1, batch_first=True)
        self.hidden_proj = nn.Linear(64, latent_dim)
        self.predictor = nn.Linear(latent_dim, 1)

    def forward(self, x):
        _, h = self.gru(x)
        latent = self.hidden_proj(h[-1])
        pred = self.predictor(latent)
        return pred, latent

# ======================================================
# 【核心修复】支持多股票，内部逐只生成因子
# ======================================================
def load_stock_data(symbols):
    df_list = []
    fg = FactorGenerator()
    engine = create_engine('sqlite:///' + DB_PATH)

    for sym in symbols:
        try:
            df = pd.read_sql(f"SELECT * FROM daily_{sym}", engine)
            df_factor = fg.generate_basic_factors(df)
            df_factor["symbol"] = sym
            df_factor = df_factor.tail(MAX_DATA_LENGTH).copy()
            df_list.append(df_factor)
            print(f"✅ 已处理：{sym} | 因子数量：{len(df_factor.columns)}")
        except Exception as e:
            print(f"❌ 失败：{sym} | {str(e)}")
            continue

    return pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()

# ======================================================
# 构建标签（多股票支持）
# ======================================================
def build_target(df):
    df = df.sort_values(["symbol", "date"]).copy()
    df["target"] = df.groupby("symbol")["close"].shift(-5) / df["close"] - 1
    df.dropna(subset=["target"], inplace=True)
    return df

# ======================================================
# 滚动训练 + 【保存模型】
# ======================================================
def rolling_train_and_extract_latent(df, factor_cols):
    scaler = StandardScaler()
    all_latent = []
    dates = sorted(df["date"].unique())
    n = len(dates)

    print("=" * 80)
    print(f"📅 总交易日：{n} | 每 {PRED_STEP} 天滚动训练一次")
    print("=" * 80)

    for i in range(TRAIN_WINDOW, n - PRED_STEP, PRED_STEP):
        gc.collect()
        torch.cuda.empty_cache() if torch.cuda.is_available() else None

        train_end = i
        pred_end = i + PRED_STEP
        train_dates = dates[train_end-TRAIN_WINDOW:train_end]
        pred_dates = dates[train_end:pred_end]

        print(f"\n🟢 训练窗口：{train_dates[0]} ~ {train_dates[-1]}")
        print(f"🔵 预测窗口：{pred_dates[0]} ~ {pred_dates[-1]}")

        train_df = df[df["date"].isin(train_dates)].copy()
        pred_df = df[df["date"].isin(pred_dates)].copy()
        if len(train_df) < 50 or len(pred_df) < 5: continue

        X_train = scaler.fit_transform(train_df[factor_cols])
        y_train = train_df["target"].values
        X_pred = scaler.transform(pred_df[factor_cols])

        train_ds = StockDataset(X_train, y_train, SEQ_LEN)
        if len(train_ds) == 0: continue

        train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
        model = GRUAlphaModel(len(factor_cols), LATENT_DIM).to(DEVICE)
        optimizer = optim.Adam(model.parameters(), lr=LR)
        criterion = nn.MSELoss()
        early_stop = EarlyStopping()

        model.train()
        for epoch in range(EPOCHS):
            total_loss = 0
            for x, y in train_loader:
                x, y = x.to(DEVICE), y.to(DEVICE)
                pred, _ = model(x)
                loss = criterion(pred, y)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            avg_loss = total_loss / len(train_loader)
            early_stop.step(avg_loss)
            if early_stop.stop:
                print(f"⏹️  早停 Epoch {epoch} | Loss: {avg_loss:.4f}")
                break

        # ====================== 【保存模型】 ======================
        model_path = os.path.join(MODEL_SAVE_PATH, f"gru_model_{train_dates[0]}_{train_dates[-1]}.pth")
        torch.save(model.state_dict(), model_path)
        print(f"💾 模型已保存：{model_path}")

        model.eval()
        with torch.no_grad():
            X_seq = [X_pred[j:j+SEQ_LEN] for j in range(len(X_pred)-SEQ_LEN+1)]
            if not X_seq: continue
            X_tensor = torch.FloatTensor(X_seq).to(DEVICE)
            _, latent = model(X_tensor)
            latent = latent.cpu().numpy()

        valid_df = pred_df.iloc[SEQ_LEN-1 : SEQ_LEN-1+len(latent)].copy()
        valid_df[[f"latent_{i}" for i in range(LATENT_DIM)]] = latent
        all_latent.append(valid_df)

        del model, X_tensor
        gc.collect()

    df_latent_all = pd.concat(all_latent, ignore_index=True) if all_latent else pd.DataFrame()

    # ====================== 【保存隐因子 → CSV + DB】 ======================
    if not df_latent_all.empty:
        csv_path = os.path.join(CSV_SAVE_PATH, "latent_factors_all.csv")
        df_latent_all.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"💾 隐因子已保存到：{csv_path}")

        engine = create_engine(f'sqlite:///{DB_PATH}')
        df_latent_all.to_sql("latent_factors", engine, if_exists="replace", index=False)
        print(f"💾 隐因子已保存到SQLite：latent_factors 表")

    return df_latent_all

# ======================================================
# 打印 IC
# ======================================================
def print_latent_ic(df):
    print("\n" + "="*80)
    print("📊 隐因子 vs 未来收益 IC（真实正负）")
    print("="*80)
    latent_cols = [f"latent_{i}" for i in range(LATENT_DIM)]
    for c in latent_cols:
        try:
            ic, _ = pearsonr(df[c], df["target"])
            print(f"{c:>10} | IC = {ic:+.4f}")
        except:
            print(f"{c:>10} | IC = +0.0000")

def print_latent_basis_corr(df, factor_cols):
    print("\n" + "="*80)
    print("🔍 隐因子 ↔ 基础因子 真实相关性（带正负）")
    print("="*80)
    latent_cols = [f"latent_{i}" for i in range(LATENT_DIM)]
    for lat in latent_cols[:3]:
        corrs = {f: df[lat].corr(df[f]) for f in factor_cols if f in df.columns}
        top5 = sorted(corrs.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        print(f"\n{lat} 最相关因子：")
        for k, v in top5:
            print(f"   {k:<12} {v:+.4f}")

# ======================================================
# 月度排名 + 【保存排名】
# ======================================================
def monthly_factor_correlation_rank(df):
    factor_cols = [f for f in df.columns if f.startswith("ret_") or f.startswith("ma_") or f.startswith("latent_")]
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M")
    
    print("\n" + "="*80)
    print("📅 月度因子 IC 排名（真实正负）")
    print("="*80)

    rank_list = []
    for m, group in df.groupby("month"):
        corrs = {}
        for f in factor_cols:
            try:
                corrs[f] = pearsonr(group[f], group["target"])[0]
            except:
                corrs[f] = 0.0

        sorted_corrs = sorted(corrs.items(), key=lambda x: abs(x[1]), reverse=True)[:10]
        print(f"\n月份：{m}")
        row = {"month": m}
        for i, (fac, ic) in enumerate(sorted_corrs, 1):
            print(f"  {i:2d}. {fac:<18} IC = {ic:+.4f}")
            row[f"top{i}_{fac}"] = ic
        rank_list.append(row)

    # 保存排名
    rank_df = pd.DataFrame(rank_list)
    rank_df.to_csv("monthly_ic_rank.csv", index=False, encoding="utf-8-sig")
    print("💾 月度IC排名已保存：monthly_ic_rank.csv")

# ======================================================
# 交易信号 + 【保存信号 → CSV + DB】
# ======================================================
def generate_trade_signals(df):
    latent_cols = [f"latent_{i}" for i in range(LATENT_DIM)]
    sign_dict = {c:1 for c in latent_cols}
    for c in latent_cols:
        try:
            ic, _ = pearsonr(df[c], df["target"])
            if not np.isnan(ic):
                sign_dict[c] = np.sign(ic)
        except: pass

    df["alpha_score"] = sum(df[c] * sign_dict[c] for c in latent_cols)
    def cross(x):
        # 同时满足：排名够高 + 分数为正 → 买入
        buy_condition = (x >= x.quantile(0.95)) & (x > 2)
        
        # 同时满足：排名够低 + 分数为负 → 卖出
        sell_condition = (x <= x.quantile(0.5)) & (x < 1)
        
        return np.where(buy_condition, 1,  # 满足 → 买
               np.where(sell_condition, -1, # 满足 → 卖
               0))                         # 其他 → 不动
    df["signal"] = df.groupby("date")["alpha_score"].transform(cross)

    # ====================== 【保存交易信号】 ======================
    signal_df = df[["date", "symbol", "alpha_score", "signal"]].copy()
    signal_df.to_csv("trade_signals.csv", index=False, encoding="utf-8-sig")
    engine = create_engine(f'sqlite:///{DB_PATH}')
    signal_df.to_sql("trade_signals", engine, if_exists="replace", index=False)

    print("\n" + "="*80)
    print("📈 交易信号（1=买入 -1=卖出）")
    print(signal_df.head(10))
    print("💾 交易信号已保存 → CSV + SQLite")
    return df
def cleanup_environment():
    print("🧹 正在清理旧环境数据...")

    # 1. 清理 CSV 文件
    files_to_delete = [
        "trade_signals.csv", 
        "latent_factors_all.csv", 
        "monthly_ic_rank.csv"
    ]
    for f in files_to_delete:
        full_path = os.path.join(CSV_SAVE_PATH, f) if "latent" in f else f
        if os.path.exists(full_path):
            os.remove(full_path)
            print(f"  🗑️ 已删除文件: {full_path}")

    # 2. 清理旧模型 (.pth)
    if os.path.exists(MODEL_SAVE_PATH):
        for f in os.listdir(MODEL_SAVE_PATH):
            if f.endswith(".pth"):
                os.remove(os.path.join(MODEL_SAVE_PATH, f))
        print(f"  🗑️ 已清空模型目录: {MODEL_SAVE_PATH}")

    # 3. 清理数据库中的表
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            # 需要清空的表名列表
            tables_to_drop = ["latent_factors", "trade_signals"]
            for table in tables_to_drop:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
            conn.commit()
            conn.close()
            print(f"  🗑️ 已清理数据库表: {', '.join(tables_to_drop)}")
        except Exception as e:
            print(f"  ⚠️ 数据库清理失败: {e}")

    print("✨ 环境清理完成！\n")
# ======================================================
# 主程序
# ======================================================
if __name__ == "__main__":
    cleanup_environment()
    # symbol_list = ["300502", "300394"]
    symbol_list = ["300502"]
    df_factor = load_stock_data(symbol_list)
    df_final = build_target(df_factor)
    factor_cols = [c for c in df_final.columns if c not in ["date","symbol","lastdate","target"]]

    df_latent = rolling_train_and_extract_latent(df_final, factor_cols)
    print_latent_ic(df_latent)
    print_latent_basis_corr(df_latent, factor_cols)
    monthly_factor_correlation_rank(df_latent)
    generate_trade_signals(df_latent)

    print("\n🎉 多股票 GRU 训练 + 全部保存完成！")