import streamlit as st
import requests
import pandas as pd
import time

# 页面基础配置
st.set_page_config(page_title="MT_Alpha 战情室", page_icon="📈", layout="wide")
API_BASE_URL = "http://127.0.0.1:8000"

def fetch_data(endpoint):
    try:
        res = requests.get(f"{API_BASE_URL}{endpoint}")
        return res.json() if res.status_code == 200 else None
    except:
        return None

# ==========================================
# 🕹️ 侧边栏：引擎启停控制
# ==========================================
st.sidebar.title("⚙️ 引擎控制台")
if st.sidebar.button("🚀 一键触发实盘推演", use_container_width=True):
    with st.sidebar.status("引擎推演中，请稍候...", expanded=True) as status:
        try:
            res = requests.post(f"{API_BASE_URL}/api/v1/engine/run_once", timeout=130)
            if res.status_code == 200:
                status.update(label="推演完成！", state="complete", expanded=False)
                st.sidebar.success("推演成功，页面数据已刷新！")
                time.sleep(1)
                st.rerun()
            else:
                status.update(label="推演报错！", state="error")
                st.sidebar.error(res.json().get("detail", "未知错误"))
        except Exception as e:
            status.update(label="请求超时或失败", state="error")

st.sidebar.markdown("---")
if st.sidebar.button("🔄 手动刷新页面数据"):
    st.rerun()

# 抓取数据
ledger_status = fetch_data("/api/v1/ledger/status") or {}
portfolio_data = fetch_data("/api/v1/ledger/assets") or {}
trades_data = fetch_data("/api/v1/orders/today?limit=30") or []

# ==========================================
# 📺 第一屏：宏观战情室 (Executive Dashboard)
# ==========================================
st.title("🚀 MT_Alpha 量化指挥中心")

# 右上角对账状态
is_match = ledger_status.get("is_match", True)
msg = ledger_status.get("message", "未知对账状态")
if is_match:
    st.success(f"**对账系统**：{msg}")
else:
    st.error(f"**对账系统**：{msg}")
    if st.button("⚠️ 以人工账本为准强制同步"):
        requests.post(f"{API_BASE_URL}/api/v1/ledger/manual_sync")
        st.rerun()

st.markdown("### 📊 宏观资产总览")
available_cash = portfolio_data.get("available_cash", 0.0)
positions = portfolio_data.get("positions", [])
total_cost = sum(p.get("shares", 0) * p.get("cost_price", 0.0) for p in positions)
total_equity = available_cash + total_cost  # 简易版净资产

col1, col2, col3 = st.columns(3)
col1.metric("💰 预估总净资产", f"¥ {total_equity:,.2f}")
col2.metric("💵 可用现金", f"¥ {available_cash:,.2f}")
exposure = (total_cost / total_equity * 100) if total_equity > 0 else 0
col3.metric("🔋 仓位使用率", f"{exposure:.1f}%")

st.progress(exposure / 100 if exposure <= 100 else 1.0)
st.markdown("---")

# ==========================================
# 📺 第二屏：持仓核算仪 (Portfolio Heatmap)
# ==========================================
st.markdown("### 🎯 持仓状态审计")
if positions:
    df_pos = pd.DataFrame(positions)
    df_pos = df_pos.rename(columns={
        "symbol": "代码", "shares": "股数", "cost_price": "成本价", "highest_price": "历史最高 (防守线)"
    })
    # 使用 Streamlit 原生 dataframe 支持排序
    st.dataframe(df_pos, use_container_width=True, hide_index=True)
else:
    st.info("大管家当前空仓休整中。")

st.markdown("---")

# ==========================================
# 📺 第三屏：参谋部军情 (Orders & Signals)
# ==========================================
col_left, col_right = st.columns([6, 4])

with col_left:
    st.markdown("### 📜 近期实盘流水")
    if trades_data:
        df_trades = pd.DataFrame(trades_data)
        st.dataframe(df_trades, use_container_width=True, hide_index=True)
    else:
        st.info("暂无交易记录。")

with col_right:
    st.markdown("### 🛡️ 雷达监控日志 (规划中)")
    st.warning("监控日志目前打印在系统日志中，下一版将通过 WebSocket 推送至此模块展示。")