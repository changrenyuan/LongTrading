# MT_Alpha 量化交易系统 - Next.js 前端

现代化的量化交易管理平台，基于 Next.js 16 + shadcn/ui 构建。

## 📁 项目结构

```
webui/nextjs/
├── src/
│   ├── app/                  # 页面路由
│   │   ├── dashboard/       # 首页 - 资产总览
│   │   ├── positions/       # 持仓详情
│   │   ├── trades/          # 交易记录
│   │   ├── settings/        # 策略配置
│   │   └── logs/            # 实时日志
│   ├── components/
│   │   ├── ui/             # shadcn/ui 基础组件
│   │   ├── charts/         # 图表组件
│   │   ├── portfolio/      # 持仓组件
│   │   └── layout/         # 布局组件
│   ├── lib/                # 工具函数 & API 客户端
│   └── types/              # TypeScript 类型定义
└── .coze                   # 项目配置（端口 5000）
```

## 🚀 快速开始

### 启动开发环境

```bash
cd webui/nextjs
pnpm install
pnpm dev
```

服务将在 `http://localhost:5000` 启动

### 构建生产版本

```bash
pnpm build
pnpm start
```

## 🔧 技术栈

- **Framework**: Next.js 16 (App Router + Turbopack)
- **Language**: TypeScript 5
- **UI Components**: shadcn/ui (基于 Radix UI)
- **Styling**: Tailwind CSS 4
- **Charts**: Recharts
- **Icons**: Lucide React
- **HTTP Client**: Fetch API

## 📊 功能模块

### 首页 /dashboard
- ✅ 资产总览（净资产、现金、仓位、年化收益率）
- ✅ 核心指标（夏普比率、最大回撤、卡玛比率）
- ✅ 资产曲线图表
- ✅ 持仓概览
- ✅ 对账状态提示
- ✅ 手动触发引擎

### 持仓详情 /positions
- ✅ 持仓列表（代码、股数、成本价、现价）
- ✅ 实时盈亏计算
- ✅ 买入日期与原因
- ✅ 最高价（防守线）

### 交易记录 /trades
- ✅ 交易流水表格
- ✅ 买入/卖出标识
- ✅ 交易状态追踪
- ✅ 核心逻辑展示

### 策略配置 /settings
- ✅ 资金与风控参数配置
- ✅ 技术指标参数调整
- ✅ 信号过滤参数设置
- 🔄 参数保存功能（待实现）

### 实时日志 /logs
- ✅ 系统日志流展示
- ✅ 日志级别分类（INFO、WARNING、ERROR、SUCCESS）
- ✅ 实时状态监控

## 🔌 API 集成

前端通过 `src/lib/api.ts` 与后端 FastAPI 服务通信：

```typescript
import { apiClient } from '@/lib/api'

// 获取资产数据
const portfolio = await apiClient.getPortfolioAssets()

// 获取交易记录
const trades = await apiClient.getTrades(100)

// 触发引擎运行
await apiClient.runEngine()
```

默认后端地址：`http://127.0.0.1:8000`

可通过环境变量修改：

```bash
NEXT_PUBLIC_API_URL=http://your-api-server:8000
```

## 🎨 主题定制

在 `src/app/globals.css` 中自定义颜色主题：

```css
:root {
  --primary: 221.2 83.2% 53.3%;
  --success: 142.1 76.2% 36.3%;
  --warning: 32.6 95.7% 44.3%;
  /* ... */
}
```

## 📝 待优化功能

- [ ] 策略参数实时保存与生效
- [ ] WebSocket 实时数据推送
- [ ] 资产曲线历史数据获取
- [ ] 持仓盈亏分布图
- [ ] 交易频次统计图表
- [ ] 风险预警系统
- [ ] 回测结果对比
- [ ] 多策略切换

## 🤝 贡献指南

1. 所有代码位于 `webui/nextjs/` 目录下
2. 使用 TypeScript 开发
3. 遵循 shadcn/ui 组件规范
4. 提交前运行 `pnpm lint` 检查代码

## 📄 许可证

与主项目保持一致
