# MT_Alpha 自动化量化交易系统

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> 一套高度稳健、安全、可视化的 Python 自动化交易系统，专为机构级趋势跟踪策略设计

## 📋 项目简介

MT_Alpha 是一个完整的量化交易解决方案，集成了历史回测、实盘交易、风险管理、绩效评估和可视化监控等核心功能。系统采用模块化架构设计，支持多股票并发交易，具备完善的资金隔离和风险控制机制。

### 核心特性

- ✅ **机构级回测引擎**：时间驱动架构，支持多股票并发回测
- ✅ **智能趋势策略**：基于均线系统、MACD、成交量等多维度信号
- ✅ **动态风险管理**：分档止盈、移动止损、仓位控制、破位清仓
- ✅ **参数网格优化**：支持 Optuna 自动寻参，持续进化
- ✅ **实时交易监控**：Streamlit 可视化看板 + FastAPI 接口
- ✅ **完善的绩效评估**：夏普比率、最大回撤、胜率、盈亏比等专业指标

## 🏗️ 系统架构

```
LongTrading/
├── core/                    # 核心引擎模块
│   ├── account.py          # 资金与持仓管理（子基金隔离）
│   ├── engineBacktest.py   # 时间驱动回测引擎
│   └── testacc.py          # 账户单元测试
├── strategies/              # 交易策略库
│   ├── base.py             # 策略基类（支持多股票快速迭代）
│   ├── trend.py            # 机构级趋势跟踪策略
│   └── paratuning/         # 参数调优专用策略
├── data_provider/           # 数据接口层
│   ├── akshare_pd.py       # AkShare 数据提供者（A股专用）
│   ├── base.py             # 数据接口基类
│   └── cron_scheduler.py   # 定时任务调度
├── live_exchage/            # 实盘交易引擎
│   ├── engine.py           # 实盘主引擎
│   ├── executor.py         # 订单执行器
│   ├── universe.py         # 动态股票池管理
│   ├── ledger.py           # 交易流水账本
│   └── config.py           # 策略参数装载
├── utils/                   # 工具库
│   ├── metrics.py          # 绩效指标计算（夏普、卡玛等）
│   ├── plotter.py          # 机构级可视化图表
│   ├── logger.py           # 结构化日志系统
│   ├── notifier.py         # 消息推送（钉钉/微信）
│   └── pushjson.py         # 前端数据总线导出
├── webui/                   # Web 可视化界面
│   ├── web_dashboard.py    # Streamlit 监控看板
│   └── api_server.py       # FastAPI RESTful 接口
├── data/                    # 数据存储目录
│   ├── live_broker_account.json    # 人工账本（实盘持仓）
│   └── system_account.json         # 系统账本（自动同步）
├── backtest.py              # 回测主入口
├── live.py                  # 实盘主入口
└── StatementofWork.md       # 项目任务书
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- pip 或 conda

### 安装依赖

```bash
# 克隆项目
git clone https://github.com/changrenyuan/LongTrading.git
cd LongTrading

# 安装依赖
pip install -r requirements.txt
```

### 运行回测

```python
# 运行历史数据回测
python backtest.py
```

回测结果将生成：
- 📊 资产曲线图（data/charts/）
- 📈 策略绩效报告（控制台输出）
- 📁 交易流水账本（data/main_ledger.csv）

### 启动实盘引擎

```python
# 启动实盘交易引擎
python live.py
```

### 启动监控看板

```bash
# 启动 FastAPI 后端
cd webui
python api_server.py

# 启动 Streamlit 前端（新终端）
streamlit run web_dashboard.py
```

访问 `http://localhost:8501` 查看实时交易监控看板。

## 📊 策略详解

### 机构级趋势跟踪策略 (InstitutionalTrendStrategy)

基于多维度技术指标的机构级趋势跟踪策略，核心逻辑包括：

#### 1. 多头趋势确认
- **均线系统**：MA5（短期）、MA20（中期生命线）、MA60（牛熊分界线）
- **趋势强度**：中期均线 > 长期均线 × 1.05，且长期均线向上
- **MACD 配合**：DIF > DEA 且 DIF > 0

#### 2. 建仓信号
- **首次建仓**：多头排列 + 乖离率 < 1.08（防追高）
- **回踩加仓**：股价回落至中期均线支撑区 + 缩量确认
- **突破加仓**：突破近 N 日高点 + 放量 + 强趋势

#### 3. 风险控制
- **硬止损**：亏损达到 10% 无条件清仓
- **移动止盈**：
  - 利润 < 30%：回撤 25% 止盈
  - 利润 30%-50%：回撤 15% 止盈
  - 利润 > 50%：回撤 10% 止盈
- **分批止盈**：触发止盈时先抛 50%，剩余仓位继续跟踪
- **技术破位**：收盘价 < 中期均线 × 0.98 且放量

#### 4. 仓位管理
- **资金隔离**：每只股票独立预算，互不干扰
- **分批建仓**：每次消耗该股总预算的 25%，最多加仓 4 次
- **盈利加仓铁律**：底仓浮盈 ≥ 8% 才允许加仓

### 参数配置

```python
STRATEGY_PARAMS = {
    # 资金与风控
    'stop_loss_pct': 0.10,           # 硬止损线
    'trailing_stop_pct': 0.25,       # 基础移动止盈
    'unit_size': 0.25,               # 每次加仓比例
    'max_units': 4,                  # 最大建仓次数
    
    # 技术指标周期
    'ma_short': 5,                   # 短期均线
    'ma_mid': 20,                    # 中期均线
    'ma_long': 60,                   # 长期均线
    'macd_fast': 12,                 # MACD 快线
    'macd_slow': 26,                 # MACD 慢线
    
    # 信号过滤
    'bias_entry_limit': 1.08,        # 首次建仓乖离率上限
    'add_pos_min_profit': 0.08,      # 加仓最低浮盈要求
}
```

## 📈 绩效评估指标

系统提供机构级绩效评估报告，包括：

### 收益指标
- 累计收益率
- 年化收益率

### 风险指标
- 最大回撤
- 年化波动率
- 下行波动率

### 风险调整收益
- **夏普比率**：风险调整后收益（> 1.5 为优秀）
- **索提诺比率**：下行风险调整收益
- **卡玛比率**：收益回撤比

### 交易统计
- 胜率（基于真实平仓流水）
- 盈亏比
- 平均盈利/亏损

## 🎯 核心亮点

### 1. 子基金隔离架构
每只股票拥有独立预算和资金池，互不干扰，避免"拆东墙补西墙"。

### 2. 审计对账系统
策略意向信号与真实成交记录自动对账，精准定位废单和异常。

### 3. 动态股票池
基于成交额、流动性、趋势强度自动筛选监控标的，优胜劣汰。

### 4. 极致性能优化
- Pandas 向量化指标预计算（比逐行循环快 100 倍）
- 使用 `.iloc` 按位置索引（比 `.loc` 快 10 倍）
- 避免深拷贝，全程原地操作

### 5. 可扩展性
- 策略基类抽象，轻松实现自定义策略
- 数据接口统一，可快速接入其他数据源
- FastAPI 接口标准化，便于系统集成

## 📦 数据接口

### AkShare 数据提供者

默认使用 AkShare 获取 A 股市场数据：

```python
from data_provider.akshare_pd import AkShareProvider

provider = AkShareProvider()

# 获取单只股票历史数据
df = provider.get_data("300502")  # 新易盛

# 获取全市场实时快照
snapshot = provider.get_market_snapshot()
```

### 自定义数据源

继承 `BaseDataProvider` 实现自定义数据接口：

```python
from data_provider.base import BaseDataProvider

class MyDataProvider(BaseDataProvider):
    def get_data(self, symbol: str) -> pd.DataFrame:
        # 实现你的数据获取逻辑
        pass
```

## 🔧 配置说明

### 实盘账本配置

编辑 `data/live_broker_account.json`：

```json
{
    "available_cash": 10000.0,
    "positions": [
        {
            "symbol": "300502",
            "name": "新易盛",
            "shares": 100,
            "cost_price": 45.20,
            "highest_price": 48.50
        }
    ]
}
```

### 策略参数调优

系统支持 Optuna 自动寻参：

```python
# 调参结果存储在 data/tuning_logs/optuna_log_*.csv
# 实盘引擎启动时自动加载最优参数
python live.py
```

## 📊 可视化看板

### Streamlit 监控界面

- 💰 资产总览：现金、持仓市值、净资产、浮盈浮亏
- 📈 持仓明细：实时价格、持仓成本、浮盈比例
- 📋 今日操作：买入/卖出订单实时记录
- 🔍 监控池状态：持仓、观望、拒绝名单一目了然

### FastAPI 接口

```bash
# 获取资产状态
GET /api/v1/ledger/assets

# 获取今日交易
GET /api/v1/orders/today

# 手动触发策略推演
POST /api/v1/engine/run_once
```

## 🧪 测试

```bash
# 运行账户管理测试
python core/testacc.py

# 运行数据接口测试
python data_provider/testak.py
```

## 📝 开发计划

- [ ] 接入更多券商接口（华泰、银河等）
- [ ] 支持港股、美股市场
- [ ] 增加机器学习策略模块
- [ ] 移动端 App 监控
- [ ] 分布式回测引擎

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## ⚠️ 风险提示

**本项目仅供学习和研究使用，不构成任何投资建议。**

- 量化交易存在市场风险、技术风险、模型风险等多种风险
- 历史回测表现不代表未来实盘收益
- 请在充分了解风险的基础上，谨慎使用实盘交易功能
- 建议先在模拟账户充分测试后再考虑实盘部署

## 📧 联系方式

项目维护者：changrenyuan

- GitHub: [@changrenyuan](https://github.com/changrenyuan)
- 项目地址: [https://github.com/changrenyuan/LongTrading](https://github.com/changrenyuan/LongTrading)

---

**如果这个项目对您有帮助，请给一个 ⭐ Star 支持一下！**
