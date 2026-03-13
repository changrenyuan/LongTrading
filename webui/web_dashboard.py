# web_dashboard.py已经废弃。
# 采用nextjs作为前端

import streamlit as st
import requests
import pandas as pd
import time

st.set_page_config(page_title="MT_Alpha 战情室", page_icon="📈", layout="wide")
API_BASE_URL = "http://127.0.0.1:8000"

def fetch_data(endpoint):
    try:
        res = requests.get(f"{API_BASE_URL}{endpoint}")
        return res.json() if res.status_code == 200 else None
    except:
        return None

st.sidebar.title("⚙️ 引擎控制台")
if st.sidebar.button("🚀 一键触发实盘推演", use_container_width=True):
    with st.sidebar.status("引擎深度推演中，请稍候...", expanded=True) as status:
        res = requests.post(f"{API_BASE_URL}/api/v1/engine/run_once", timeout=180)
        if res and res.status_code == 200:
            status.update(label="推演完成！", state="complete", expanded=False)
            time.sleep(1)
            st.rerun()
        else:
            status.update(label="推演报错！", state="error")
st.sidebar.markdown("---")
if st.sidebar.button("🔄 手动刷新页面数据"): st.rerun()

ledger_status = fetch_data("/api/v1/ledger/status") or {}
portfolio_data = fetch_data("/api/v1/ledger/assets") or {}
trades_data = fetch_data("/api/v1/orders/today?limit=50") or []
universe_pool = fetch_data("/api/v1/universe/pool") or []

st.title("🚀 MT_Alpha 量化指挥中心")

if ledger_status.get("is_match", True):
    st.success(f"**对账系统**：{ledger_status.get('message')}")
else:
    st.error(f"**对账系统**：{ledger_status.get('message')}")
    if st.button("⚠️ 以人工账本为准强制同步"):
        requests.post(f"{API_BASE_URL}/api/v1/ledger/manual_sync")
        st.rerun()

st.markdown("### 📊 宏观资产总览")
available_cash = portfolio_data.get("available_cash", 0.0)
positions = portfolio_data.get("positions", [])
metrics = portfolio_data.get("metrics", {})

total_cost = sum(p.get("shares", 0) * p.get("cost_price", 0.0) for p in positions)
total_market_value = sum(p.get("shares", 0) * p.get("current_price", p.get("cost_price", 0.0)) for p in positions)
total_equity = available_cash + total_market_value

c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 预估总净资产", f"¥ {total_equity:,.2f}", f"总盈亏: ¥ {metrics.get('total_pnl', 0):,.2f}")
c2.metric("💵 可用现金", f"¥ {available_cash:,.2f}")
exposure = (total_market_value / total_equity * 100) if total_equity > 0 else 0
c3.metric("🔋 仓位使用率", f"{exposure:.1f}%")
c4.metric("📈 年化收益率", f"{metrics.get('annualized_return', 0):.2f}%")

c5, c6, c7, c8 = st.columns(4)
c5.metric("夏普比率 (Sharpe)", f"{metrics.get('sharpe_ratio', 0):.2f}")
c6.metric("卡玛比率 (Calmar)", f"{metrics.get('calmar_ratio', 0):.2f}")
c7.metric("最大回撤 (Max DD)", f"{metrics.get('max_drawdown', 0):.2f}%")
c8.metric("持仓个股数", f"{len(positions)} 只")

st.markdown("---")

# 💡 上下独立排版，解决拥挤问题
st.markdown("### 🎯 持仓审计与实时盈亏")
if positions:
    df_pos = pd.DataFrame(positions)
    for col in ["name", "current_price", "pnl", "pnl_pct", "buy_date", "buy_reason"]:
        if col not in df_pos.columns: df_pos[col] = "—"
    df_pos = df_pos.astype(str).rename(columns={
        "symbol": "代码", "name": "名称", "shares": "股数", "cost_price": "成本价", "current_price": "现价",
        "pnl": "浮盈亏(元)", "pnl_pct": "盈亏率", "highest_price": "最高(防守线)", "buy_date": "买入日期", "buy_reason": "开仓逻辑"
    })
    st.dataframe(df_pos[["代码", "名称", "股数", "成本价", "现价", "盈亏率", "浮盈亏(元)", "最高(防守线)", "买入日期", "开仓逻辑"]], width="stretch", hide_index=True)
else:
    st.info("大管家当前空仓休整中。")

st.markdown("---")
st.markdown("### 📜 策略干预与执行流水 (审计记录)")
if trades_data:
    df_trades = pd.DataFrame(trades_data).astype(str)
    rename_dict = {"Date": "建议日期", "Symbol": "代码", "Name": "名称", "Action": "系统指令", "Shares": "数量", "Price": "参考价", "Reason": "核心逻辑", "Status": "审计核销状态"}
    df_trades = df_trades.rename(columns={k: v for k, v in rename_dict.items() if k in df_trades.columns})
    st.dataframe(df_trades, width="stretch", hide_index=True)
else:
    st.info("暂无交易记录。")

st.markdown("---")
st.markdown("### 📡 动态活水雷达池 (近20日 Top 活跃股)")
if universe_pool:
    df_pool = pd.DataFrame(universe_pool).rename(columns={"symbol": "代码", "name": "名称", "reason": "入选雷达池理由"})
    st.dataframe(df_pool, width="stretch", hide_index=True)
else:
    st.info("暂无股票池数据。")