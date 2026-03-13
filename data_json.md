# MT_Alpha 数据目录规划方案

> 版本：v2.0  
> 更新时间：2026-03-27  
> 设计原则：优先保留原有JSON命名和数据结构，按功能模块清晰分层

---

## 📁 整体目录结构

```
LongTrading/data/
│
├── 📂 config/              # ⚙️ 配置模块 - 策略的"大脑"参数
│   ├── strategy_params.json       # 策略参数（原 best_params_win50p.json）
│   ├── universe_pool.json         # 股票池配置
│   └── risk_config.json           # 风控参数配置
│
├── 📂 market/              # 📈 行情快照 - 实盘环境复现
│   ├── snapshot.json              # 全市场快照（原 market_status.json）
│   ├── kline_cache/               # K线数据缓存目录
│   │   ├── 300502.json           # 按股票代码存储
│   │   └── 300308.json
│   └── realtime_quotes.json       # 实时行情快照（最新tick）
│
├── 📂 ledger/              # 💰 账户与账本 - Dashboard核心展示
│   ├── broker_account.json        # 人工/券商账本（原 live_broker_account.json）
│   ├── system_account.json        # 系统账本（保持原名）
│   ├── portfolio.json             # 资产组合快照（原 portfolio_assets.json）
│   ├── nav_history.json           # 净值历史（从CSV迁移）
│   └── reconciliation.json        # 对账状态记录
│
├── 📂 trade/               # ⚡ 信号与交易 - "为什么买"和"买了什么"
│   ├── signals_today.json         # 今日交易信号（核心）
│   ├── orders_pending.json        # 待处理订单
│   ├── orders_history.json        # 历史订单记录
│   └── ledger.csv                 # 交易流水（保留CSV格式）
│
├── 📂 backtest/            # 🧪 回测与寻优 - 解耦耗时任务
│   ├── latest_result.json         # 最新回测结果
│   ├── summary.json               # 绩效汇总
│   ├── equity_curve.json          # 权益曲线
│   ├── drawdown.json              # 回撤曲线
│   ├── trades.json                # 回测交易流水
│   ├── stocks_overview.json       # 股票概览（原 backtest_stocks.json）
│   ├── kline/                     # 个股K线与信号
│   │   ├── 300502.json
│   │   └── 300308.json
│   └── optimization/              # 寻优相关
│       ├── progress.json          # 寻优进度
│       ├── best_params.json       # 最优参数备份
│       └── sensitivity.json       # 参数敏感度
│
├── 📂 system/              # 🛠️ 系统状态与调试
│   ├── engine_state.json          # 引擎状态（空闲/运行中/寻优中）
│   ├── runtime_metrics.json       # 运行时指标
│   ├── logs/                      # 日志目录
│   │   ├── 2026-03-27_trade.log   # 按日期存储
│   │   └── 2026-03-27_debug.log
│   └── debug/                     # 调试快照
│       ├── signal_compare.json    # 信号对比
│       └── data_integrity.json    # 数据完整性检查
│
└── 📂 archive/             # 📦 历史归档 - 按日期备份
    ├── 2026-03-26/
    │   ├── portfolio.json
    │   └── signals.json
    └── 2026-03-25/
        └── portfolio.json
```

---

## 📋 详细文件说明

### 1️⃣ 配置模块 (`/data/config/`)

#### `strategy_params.json` - 策略参数配置
**来源**：原 `best_params_win50p.json`  
**用途**：存储策略的核心参数，实盘引擎启动时优先读取

```json
{
  "version": "2.0",
  "last_update": "2026-03-27T14:30:00",
  "source": "optuna_optimization",
  
  "params": {
    // 均线系统
    "ma_short": 5,
    "ma_mid": 12,
    "ma_long": 50,
    
    // 风控参数
    "stop_loss_pct": 0.10,
    "trailing_stop_pct": 0.20,
    
    // 仓位管理
    "unit_size": 0.25,
    "max_units": 4,
    
    // 信号过滤
    "bias_entry_limit": 1.08,
    "add_pos_min_profit": 0.08
  },
  
  "performance": {
    "sharpe_ratio": 1.85,
    "win_rate": 0.65,
    "optimization_date": "2026-03-20"
  }
}
```

#### `universe_pool.json` - 股票池配置
**保持原名**：`universe_pool.json`  
**用途**：定义监控的股票池及筛选规则

```json
{
  "version": "2.0",
  "last_update": "2026-03-27T14:30:00",
  
  "pool": [
    {
      "symbol": "300502",
      "name": "新易盛",
      "reason": "🛡️ 实盘持仓标的",
      "add_date": "2026-03-01",
      "priority": 1
    },
    {
      "symbol": "300308",
      "name": "中际旭创",
      "reason": "📊 成交额Top20",
      "add_date": "2026-03-27",
      "priority": 2
    }
  ],
  
  "filter_rules": {
    "min_amount": 500000000,
    "max_pool_size": 20,
    "exclude_st": true,
    "exclude_suspended": true
  }
}
```

#### `risk_config.json` - 风控参数配置（新增）
**用途**：独立的风控参数配置，支持前端动态调整

```json
{
  "version": "1.0",
  "last_update": "2026-03-27T14:30:00",
  
  "position_limits": {
    "max_positions": 5,
    "max_single_position_pct": 0.30,
    "max_total_position_pct": 0.95
  },
  
  "stop_loss": {
    "hard_stop_pct": 0.10,
    "time_stop_days": 30,
    "max_drawdown_pct": 0.15
  },
  
  "trading_hours": {
    "market_open": "09:30:00",
    "market_close": "15:00:00",
    "lunch_break": ["11:30:00", "13:00:00"]
  }
}
```

---

### 2️⃣ 行情快照模块 (`/data/market/`)

#### `snapshot.json` - 全市场快照
**来源**：原 `market_status.json`  
**用途**：存储最后一次引擎运行时的全市场行情快照

```json
{
  "timestamp": "2026-03-27T14:30:00",
  "market_status": "交易中",
  "trading_day": "2026-03-27",
  
  "overview": {
    "total_stocks": 5234,
    "advancing": 2856,
    "declining": 2134,
    "unchanged": 244
  },
  
  "top_gainers": [
    {"symbol": "300xxx", "name": "xxx科技", "change_pct": 10.01}
  ],
  
  "top_losers": [
    {"symbol": "600xxx", "name": "xxx股份", "change_pct": -9.98}
  ],
  
  "snapshot_data": [
    {
      "symbol": "300502",
      "name": "新易盛",
      "latest_price": 45.20,
      "open": 44.80,
      "high": 45.60,
      "low": 44.50,
      "volume": 1234567,
      "amount": 55678900,
      "turnover_rate": 2.35,
      "change_pct": 1.25
    }
  ]
}
```

#### `kline_cache/{symbol}.json` - K线数据缓存
**来源**：原 `backtest/kline_{symbol}.json`（拆分）  
**用途**：缓存历史K线数据，避免重复请求API

```json
{
  "symbol": "300502",
  "name": "新易盛",
  "last_update": "2026-03-27T14:30:00",
  "data_source": "akshare",
  
  "kline": [
    {
      "date": "2026-03-27",
      "open": 44.80,
      "high": 45.60,
      "low": 44.50,
      "close": 45.20,
      "volume": 1234567,
      "amount": 55678900
    }
  ],
  
  "indicators": {
    "ma5": [45.10, 44.95, ...],
    "ma20": [44.50, 44.45, ...],
    "ma60": [43.80, 43.75, ...]
  }
}
```

---

### 3️⃣ 账户与账本模块 (`/data/ledger/`)

#### `broker_account.json` - 人工/券商账本
**来源**：原 `live_broker_account.json`（仅改名）  
**用途**：人工维护的真实持仓账本，系统只读

```json
{
  "version": "2.0",
  "last_update": "2026-03-27T09:00:00",
  "source": "manual_input",
  
  "available_cash": 50000.00,
  
  "positions": [
    {
      "symbol": "300502",
      "name": "新易盛",
      "shares": 700,
      "cost_price": 40.50,
      "highest_price": 45.60,
      "buy_date": "2026-03-01",
      "notes": "首次建仓"
    }
  ]
}
```

#### `system_account.json` - 系统账本
**保持原名**：`system_account.json`  
**用途**：系统自动维护的账本，包含实时计算的盈亏

```json
{
  "version": "2.0",
  "last_update": "2026-03-27T14:30:00",
  
  "available_cash": 50000.00,
  "total_equity": 108200.00,
  
  "positions": [
    {
      "symbol": "300502",
      "name": "新易盛",
      "shares": 700,
      "cost_price": 40.50,
      "current_price": 45.20,
      "market_value": 31640.00,
      "pnl": 3290.00,
      "pnl_pct": "+11.60%",
      "highest_price": 45.60,
      "buy_date": "2026-03-01",
      "buy_reason": "多头趋势确认+缩量回踩"
    }
  ]
}
```

#### `portfolio.json` - 资产组合快照
**来源**：原 `portfolio_assets.json`  
**用途**：前端Dashboard展示的核心数据，包含绩效指标

```json
{
  "version": "2.0",
  "last_update": "2026-03-27T14:30:00",
  "snapshot_time": "2026-03-27T14:30:00",
  
  "assets": {
    "available_cash": 50000.00,
    "total_cost": 63000.00,
    "total_market_value": 70190.00,
    "total_equity": 120190.00,
    "floating_pnl": 7190.00,
    "floating_pnl_pct": 11.41
  },
  
  "positions": [
    {
      "symbol": "300502",
      "name": "新易盛",
      "shares": 700,
      "cost_price": 40.50,
      "current_price": 45.20,
      "market_value": 31640.00,
      "pnl": 3290.00,
      "pnl_pct": 11.60,
      "weight_pct": 26.35,
      "hold_days": 26,
      "status": "holding"
    }
  ],
  
  "metrics": {
    "sharpe_ratio": 1.85,
    "max_drawdown": -8.23,
    "win_rate": 65.5,
    "profit_loss_ratio": 2.3,
    "annualized_return": 25.6,
    "calmar_ratio": 3.11
  },
  
  "pnl_summary": {
    "today_pnl": 1250.00,
    "today_pnl_pct": 1.05,
    "week_pnl": 3560.00,
    "month_pnl": 7190.00
  }
}
```

#### `nav_history.json` - 净值历史
**来源**：原 `daily_nav.csv`（迁移为JSON）  
**用途**：绘制资产曲线图

```json
{
  "version": "1.0",
  "last_update": "2026-03-27T14:30:00",
  "initial_capital": 100000.00,
  
  "nav_curve": [
    {
      "date": "2026-03-01",
      "equity": 100000.00,
      "nav": 1.0000,
      "cash": 100000.00,
      "position_value": 0.00
    },
    {
      "date": "2026-03-27",
      "equity": 120190.00,
      "nav": 1.2019,
      "cash": 50000.00,
      "position_value": 70190.00
    }
  ],
  
  "statistics": {
    "total_days": 26,
    "trading_days": 19,
    "max_nav": 1.2019,
    "min_nav": 0.9820
  }
}
```

#### `reconciliation.json` - 对账状态
**用途**：记录系统账本与人工账本的对比结果

```json
{
  "version": "1.0",
  "last_check": "2026-03-27T14:30:00",
  "is_match": true,
  
  "details": {
    "cash_match": true,
    "position_match": true,
    "position_count_match": true,
    
    "differences": [],
    
    "broker_total": {
      "cash": 50000.00,
      "positions": 1
    },
    
    "system_total": {
      "cash": 50000.00,
      "positions": 1
    }
  }
}
```

---

### 4️⃣ 交易信号模块 (`/data/trade/`)

#### `signals_today.json` - 今日交易信号（核心）
**用途**：引擎生成的买卖建议信号，前端实时展示

```json
{
  "version": "2.0",
  "last_update": "2026-03-27T14:30:00",
  "trading_day": "2026-03-27",
  
  "signals": [
    {
      "signal_id": "live_300502_20260327143000_BUY",
      "timestamp": "2026-03-27T14:30:00",
      "symbol": "300502",
      "name": "新易盛",
      "action": "BUY",
      "suggested_shares": 100,
      "suggested_price": 45.20,
      "confidence": 0.85,
      "reason": "多头趋势确认+缩量回踩至MA20支撑",
      "status": "pending",
      
      "indicators": {
        "ma5": 44.95,
        "ma20": 44.50,
        "bias": 1.015,
        "volume_ratio": 0.85
      },
      
      "risk_params": {
        "stop_loss_price": 40.68,
        "take_profit_price": 54.24
      }
    },
    {
      "signal_id": "live_300308_20260327143000_SELL",
      "timestamp": "2026-03-27T14:30:00",
      "symbol": "300308",
      "name": "中际旭创",
      "action": "SELL",
      "suggested_shares": 200,
      "suggested_price": 120.50,
      "confidence": 0.92,
      "reason": "触发移动止盈（利润回撤25%）",
      "status": "pending"
    }
  ],
  
  "summary": {
    "total_signals": 2,
    "buy_signals": 1,
    "sell_signals": 1,
    "high_confidence": 2
  }
}
```

#### `orders_pending.json` - 待处理订单
**用途**：记录尚未成交的订单

```json
{
  "version": "1.0",
  "last_update": "2026-03-27T14:35:00",
  
  "orders": [
    {
      "order_id": "ORD_20260327_001",
      "signal_id": "live_300502_20260327143000_BUY",
      "timestamp": "2026-03-27T14:30:00",
      "symbol": "300502",
      "action": "BUY",
      "shares": 100,
      "price": 45.20,
      "status": "pending",
      "expire_time": "2026-03-27T15:00:00"
    }
  ]
}
```

#### `orders_history.json` - 历史订单记录
**用途**：记录已成交或已取消的订单

```json
{
  "version": "1.0",
  "last_update": "2026-03-27T15:30:00",
  
  "orders": [
    {
      "order_id": "ORD_20260327_001",
      "signal_id": "live_300502_20260327143000_BUY",
      "timestamp": "2026-03-27T14:30:00",
      "symbol": "300502",
      "action": "BUY",
      "shares": 100,
      "price": 45.20,
      "status": "filled",
      "filled_price": 45.25,
      "filled_time": "2026-03-27T14:31:00",
      "commission": 1.36
    }
  ]
}
```

#### `ledger.csv` - 交易流水
**保持原名**：`live_trade_ledger.csv`  
**保持格式**：CSV格式，便于Excel查看

```csv
timestamp,symbol,name,action,shares,price,trade_value,fee,realized_pnl,reason,status
2026-03-27T14:30:00,300502,新易盛,BUY,100,45.20,4520.00,1.36,0.00,多头趋势确认,待确认
2026-03-27T14:35:00,300502,新易盛,BUY,100,45.25,4525.00,1.36,0.00,多头趋势确认,已执行
```

---

### 5️⃣ 回测模块 (`/data/backtest/`)

#### `latest_result.json` - 最新回测结果
**用途**：存储最后一次回测的完整结果

```json
{
  "version": "2.0",
  "backtest_id": "bt_20260327_143000",
  "start_date": "2024-01-01",
  "end_date": "2026-03-27",
  "initial_capital": 1000000.00,
  "final_equity": 1250000.00,
  
  "performance": {
    "total_return": 25.0,
    "annualized_return": 12.5,
    "sharpe_ratio": 1.85,
    "max_drawdown": -8.23,
    "calmar_ratio": 3.11,
    "win_rate": 65.5,
    "profit_loss_ratio": 2.3,
    "total_trades": 120
  },
  
  "symbols": ["300502", "300308", "601606"],
  "strategy_name": "InstitutionalTrendStrategy",
  "params_used": {}
}
```

#### `summary.json` - 绩效汇总
**保持原名**：`summary.json`  
**保持结构**：原有格式

#### `equity_curve.json` - 权益曲线
**保持原名**：`equity_curve.json`  
**保持结构**：原有格式

#### `drawdown.json` - 回撤曲线
**保持原名**：`drawdown.json`  
**保持结构**：原有格式

#### `trades.json` - 回测交易流水
**保持原名**：`trades.json`  
**保持结构**：原有格式

#### `stocks_overview.json` - 股票概览
**来源**：原 `backtest_stocks.json`（改名）  
**保持结构**：原有格式

#### `kline/{symbol}.json` - 个股K线与信号
**来源**：原 `kline_{symbol}.json`（移动到子目录）  
**保持结构**：原有格式

#### `optimization/progress.json` - 寻优进度
**用途**：前端进度条显示

```json
{
  "version": "1.0",
  "task_id": "opt_20260327_143000",
  "status": "running",
  "progress_pct": 45.5,
  "current_trial": 91,
  "total_trials": 200,
  "best_value": 1.85,
  "elapsed_time": 1200,
  "estimated_remaining": 1440,
  "start_time": "2026-03-27T14:30:00",
  "last_update": "2026-03-27T14:50:00"
}
```

---

### 6️⃣ 系统状态模块 (`/data/system/`)

#### `engine_state.json` - 引擎状态
**用途**：记录引擎当前状态，便于前端监控

```json
{
  "version": "1.0",
  "last_update": "2026-03-27T14:30:00",
  
  "status": "running",
  "mode": "live",
  
  "last_run": {
    "start_time": "2026-03-27T14:30:00",
    "end_time": "2026-03-27T14:31:00",
    "duration_seconds": 60,
    "status": "success",
    "signals_generated": 2
  },
  
  "next_scheduled_run": "2026-03-28T09:30:00",
  
  "health": {
    "database": "connected",
    "data_provider": "akshare",
    "api_server": "running",
    "last_data_update": "2026-03-27T14:30:00"
  },
  
  "statistics": {
    "total_runs": 156,
    "success_runs": 152,
    "failed_runs": 4,
    "uptime_hours": 720
  }
}
```

#### `runtime_metrics.json` - 运行时指标
**用途**：记录系统运行时的性能指标

```json
{
  "version": "1.0",
  "last_update": "2026-03-27T14:30:00",
  
  "performance": {
    "avg_execution_time_ms": 125,
    "max_execution_time_ms": 350,
    "avg_memory_usage_mb": 256,
    "max_memory_usage_mb": 512,
    "cpu_usage_pct": 15.5
  },
  
  "data_freshness": {
    "market_snapshot_age_seconds": 300,
    "portfolio_age_seconds": 120,
    "nav_history_age_seconds": 3600
  }
}
```

---

## 🔄 数据流转逻辑

### 实盘运行流程

```
1. 引擎启动
   ├─ 读取 config/strategy_params.json
   ├─ 读取 config/universe_pool.json
   └─ 读取 config/risk_config.json

2. 数据获取
   ├─ 读取 market/snapshot.json（检查是否过期）
   ├─ 如果过期 → 从API获取新数据 → 更新 snapshot.json
   └─ 读取 market/kline_cache/{symbol}.json

3. 策略计算
   ├─ 生成交易信号
   └─ 写入 trade/signals_today.json

4. 账户更新
   ├─ 读取 ledger/broker_account.json
   ├─ 写入 ledger/system_account.json
   ├─ 写入 ledger/portfolio.json
   ├─ 写入 ledger/nav_history.json
   └─ 写入 ledger/reconciliation.json

5. 状态同步
   ├─ 写入 system/engine_state.json
   └─ 写入 system/runtime_metrics.json

6. 前端展示
   ├─ GET /api/v1/ledger/portfolio → 读取 portfolio.json
   ├─ GET /api/v1/trade/signals → 读取 signals_today.json
   └─ GET /api/v1/system/status → 读取 engine_state.json
```

### 回测运行流程

```
1. 参数加载
   └─ 读取 config/strategy_params.json

2. 历史数据
   └─ 读取 market/kline_cache/{symbol}.json

3. 回测计算
   ├─ 运行回测引擎
   └─ 生成结果数据

4. 结果保存
   ├─ 写入 backtest/latest_result.json
   ├─ 写入 backtest/summary.json
   ├─ 写入 backtest/equity_curve.json
   ├─ 写入 backtest/drawdown.json
   ├─ 写入 backtest/trades.json
   ├─ 写入 backtest/stocks_overview.json
   └─ 写入 backtest/kline/{symbol}.json

5. 寻优任务（如启用）
   ├─ 更新 backtest/optimization/progress.json
   └─ 写入 backtest/optimization/best_params.json
```

---

## 🛠️ 实施步骤

### 第一阶段：目录重构（保持向后兼容）

1. **创建新的目录结构**
```bash
mkdir -p data/{config,market,ledger,trade,system,archive}
mkdir -p data/market/kline_cache
mkdir -p data/backtest/{kline,optimization}
mkdir -p data/system/{logs,debug}
```

2. **迁移现有文件（软链接或复制）**
```bash
# 配置文件
mv data/best_params_win50p.json data/config/strategy_params.json
mv data/universe_pool.json data/config/universe_pool.json

# 账户文件
mv data/live_broker_account.json data/ledger/broker_account.json
# system_account.json 保持位置
# portfolio_assets.json 移动到 ledger/

# 市场数据
mv data/market_status.json data/market/snapshot.json

# 交易数据
mv data/live_trade_ledger.csv data/trade/ledger.csv

# 回测数据
mv data/backtest/kline_*.json data/backtest/kline/
```

3. **创建兼容性链接（过渡期）**
```python
# 在代码中添加兼容层
import os
import shutil

# 保持向后兼容的文件映射
LEGACY_FILE_MAPPING = {
    "data/live_broker_account.json": "data/ledger/broker_account.json",
    "data/best_params_win50p.json": "data/config/strategy_params.json",
    "data/market_status.json": "data/market/snapshot.json",
}

def ensure_compatibility():
    """确保旧路径的文件仍然可用（创建软链接）"""
    for old_path, new_path in LEGACY_FILE_MAPPING.items():
        if os.path.exists(new_path) and not os.path.exists(old_path):
            os.symlink(os.path.abspath(new_path), old_path)
```

### 第二阶段：代码适配

1. **更新文件路径常量**
```python
# webui/api_server.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 新的文件路径定义
CONFIG_DIR = os.path.join(BASE_DIR, "data", "config")
MARKET_DIR = os.path.join(BASE_DIR, "data", "market")
LEDGER_DIR = os.path.join(BASE_DIR, "data", "ledger")
TRADE_DIR = os.path.join(BASE_DIR, "data", "trade")
BACKTEST_DIR = os.path.join(BASE_DIR, "data", "backtest")
SYSTEM_DIR = os.path.join(BASE_DIR, "data", "system")

# 具体文件路径
STRATEGY_PARAMS_FILE = os.path.join(CONFIG_DIR, "strategy_params.json")
UNIVERSE_POOL_FILE = os.path.join(CONFIG_DIR, "universe_pool.json")
BROKER_ACCOUNT_FILE = os.path.join(LEDGER_DIR, "broker_account.json")
SYSTEM_ACCOUNT_FILE = os.path.join(LEDGER_DIR, "system_account.json")
PORTFOLIO_FILE = os.path.join(LEDGER_DIR, "portfolio.json")
SNAPSHOT_FILE = os.path.join(MARKET_DIR, "snapshot.json")
SIGNALS_FILE = os.path.join(TRADE_DIR, "signals_today.json")
ENGINE_STATE_FILE = os.path.join(SYSTEM_DIR, "engine_state.json")
```

2. **更新数据读写逻辑**
```python
# utils/data_manager.py（新增）
import json
import os
from typing import Dict, Any

class DataManager:
    """统一数据管理器，处理所有JSON文件的读写"""
    
    @staticmethod
    def load_json(file_path: str) -> Dict[str, Any]:
        """加载JSON文件"""
        if not os.path.exists(file_path):
            return {}
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def save_json(file_path: str, data: Dict[str, Any]):
        """保存JSON文件"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def load_strategy_params() -> dict:
        """加载策略参数"""
        return DataManager.load_json(STRATEGY_PARAMS_FILE)
    
    @staticmethod
    def save_portfolio(data: dict):
        """保存资产组合"""
        DataManager.save_json(PORTFOLIO_FILE, data)
```

### 第三阶段：前端适配

前端API调用保持不变，后端负责路径映射：

```python
@app.get("/api/v1/ledger/assets")
def get_portfolio_status():
    """获取资产组合状态"""
    return DataManager.load_json(PORTFOLIO_FILE)
```

---

## 📊 文件命名规范

### 通用规范

1. **小写字母 + 下划线**：`nav_history.json`（推荐）
2. **避免空格和特殊字符**
3. **语义清晰**：文件名应能直接反映内容
4. **版本字段**：每个JSON文件包含 `version` 字段

### 时间相关命名

- **日志文件**：`YYYY-MM-DD_{type}.log`（如 `2026-03-27_trade.log`）
- **归档文件**：`YYYY-MM-DD/{filename}.json`

---

## ✅ 优势总结

### 1. 调试友好
- JSON文件按功能模块分类，一目了然
- 可以直接复制 `market/snapshot.json` 到回测环境复现问题
- 所有文件都有 `last_update` 字段，便于排查数据新鲜度

### 2. 向后兼容
- 核心数据结构保持不变
- 通过软链接支持旧路径
- 渐进式迁移，不影响现有功能

### 3. 扩展性强
- 模块化设计，易于添加新功能
- 清晰的分层架构
- 支持未来的Redis迁移

### 4. 生产就绪
- 符合成熟交易系统的最佳实践
- 支持多环境部署（开发/测试/生产）
- 便于监控和运维

---

## 🔗 参考资料

- 主流量化平台数据架构（QuantConnect, Zipline, Backtrader）
- 金融数据存储最佳实践（时序数据库 vs JSON）
- 事件驱动系统设计模式

---

**文档版本**：v2.0  
**维护者**：MT_Alpha团队  
**最后更新**：2026-03-27
