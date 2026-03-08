'use client'

import { useState } from 'react'
import { DashboardSidebar } from '@/components/layout/DashboardSidebar'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Slider } from '@/components/ui/slider'
import {
  Play,
  Pause,
  Settings,
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart3,
  Calendar,
  DollarSign,
  Target,
  AlertTriangle,
  ChevronRight,
  RefreshCw,
  Download,
  Zap,
  Grid3X3,
  PieChart,
  CandlestickChart,
  FileText,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  ReferenceLine,
} from 'recharts'

// 导入新组件
import { StrategySelector } from '@/components/charts/StrategySelector'
import { EquityCurveChart } from '@/components/charts/EquityCurveChart'
import { DrawdownChart } from '@/components/charts/DrawdownChart'
import { PnlImpactCard } from '@/components/charts/PnlImpactCard'
import { CapitalUsageCard } from '@/components/charts/CapitalUsageCard'
import { WinRatePieChart } from '@/components/charts/WinRatePieChart'
import { KlineSignalChart } from '@/components/charts/KlineSignalChart'
import { TradeLogTable } from '@/components/charts/TradeLogTable'
import { ParameterHeatmap } from '@/components/charts/ParameterHeatmap'
import { RiskAttribution } from '@/components/charts/RiskAttribution'

// 模拟回测结果数据
const mockBacktestResult = {
  total_return: 25.49,
  annualized_return: 25.49,
  max_drawdown: -8.32,
  sharpe_ratio: 1.85,
  calmar_ratio: 3.06,
  win_rate: 62.5,
  total_trades: 48,
  profit_trades: 30,
  loss_trades: 18,
  avg_profit: 3520.5,
  avg_loss: -1820.3,
  profit_factor: 1.93,
  equity_curve: [
    { date: '2024-01', equity: 1000000, benchmark: 1000000 },
    { date: '2024-02', equity: 1020000, benchmark: 1015000 },
    { date: '2024-03', equity: 1015000, benchmark: 1020000 },
    { date: '2024-04', equity: 1050000, benchmark: 1030000 },
    { date: '2024-05', equity: 1075000, benchmark: 1045000 },
    { date: '2024-06', equity: 1065000, benchmark: 1040000 },
  ],
  monthly_returns: [
    { month: '1月', return: 2.0 },
    { month: '2月', return: -0.5 },
    { month: '3月', return: 3.4 },
    { month: '4月', return: 2.4 },
    { month: '5月', return: -0.9 },
    { month: '6月', return: 1.2 },
  ],
}

// 策略列表
const strategies = [
  { id: 'strategy-1', name: '趋势跟踪策略 v2.0', type: '趋势跟踪', status: 'running' as const, return_pct: 25.49 },
  { id: 'strategy-2', name: '均值回归策略', type: '均值回归', status: 'paused' as const, return_pct: 12.35 },
  { id: 'strategy-3', name: '动量策略', type: '动量策略', status: 'stopped' as const, return_pct: -3.21 },
]

// 回测股票列表
const backtestStocks = [
  { symbol: '300308', name: '中际旭创', return_pct: 14.94, trades: 3 },
  { symbol: '600519', name: '贵州茅台', return_pct: 29.82, trades: 2 },
  { symbol: '300502', name: '新易盛', return_pct: 8.5, trades: 1 },
  { symbol: '601606', name: '长城军工', return_pct: 2.3, trades: 1 },
]

// 策略配置类型
interface StrategyConfig {
  stop_loss_pct: number
  trailing_stop_pct: number
  ma_short: number
  ma_mid: number
  ma_long: number
  bias_entry_limit: number
  add_pos_min_profit: number
  max_position_pct: number
}

export default function StrategyPage() {
  const [selectedStrategy, setSelectedStrategy] = useState(strategies[0].id)
  const [isRunning, setIsRunning] = useState(true)
  const [isBacktesting, setIsBacktesting] = useState(false)
  const [showBacktestResult, setShowBacktestResult] = useState(false)
  const [activeTab, setActiveTab] = useState('overview')

  // 策略配置状态
  const [config, setConfig] = useState<StrategyConfig>({
    stop_loss_pct: 0.10,
    trailing_stop_pct: 0.25,
    ma_short: 5,
    ma_mid: 20,
    ma_long: 60,
    bias_entry_limit: 1.08,
    add_pos_min_profit: 0.08,
    max_position_pct: 0.30,
  })

  // 回测参数
  const [backtestParams, setBacktestParams] = useState({
    startDate: '2024-01-01',
    endDate: '2024-06-30',
    initialCapital: 1000000,
  })

  // 运行回测
  const runBacktest = async () => {
    setIsBacktesting(true)
    await new Promise(resolve => setTimeout(resolve, 2000))
    setIsBacktesting(false)
    setShowBacktestResult(true)
  }

  const currentStrategy = strategies.find(s => s.id === selectedStrategy)

  return (
    <div className="flex h-screen bg-background">
      <DashboardSidebar />

      <main className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-6">
          {/* 页面标题 */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold">策略中心</h1>
              <p className="text-muted-foreground">策略配置、回测与实时监控</p>
            </div>
            <div className="flex items-center gap-4">
              {/* 策略选择器 */}
              <StrategySelector
                strategies={strategies}
                selectedId={selectedStrategy}
                onSelect={setSelectedStrategy}
              />
              <Badge variant={isRunning ? 'default' : 'secondary'} className="px-3 py-1">
                <Activity className={`h-3 w-3 mr-1 ${isRunning ? 'animate-pulse' : ''}`} />
                {isRunning ? '运行中' : '已暂停'}
              </Badge>
              <Button
                variant={isRunning ? 'destructive' : 'default'}
                onClick={() => setIsRunning(!isRunning)}
              >
                {isRunning ? (
                  <>
                    <Pause className="h-4 w-4 mr-2" />
                    暂停策略
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    启动策略
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* 策略概览卡片 */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card className="bg-gradient-to-br from-green-50 to-green-100/50 dark:from-green-950/30 dark:to-green-900/20">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-green-700 dark:text-green-400">
                  策略收益
                </CardTitle>
                <TrendingUp className="h-4 w-4 text-green-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-700 dark:text-green-400">
                  +{currentStrategy?.return_pct || 0}%
                </div>
                <p className="text-xs text-green-600/70 dark:text-green-400/70">
                  年化收益率
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">胜率</CardTitle>
                <Target className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{mockBacktestResult.win_rate}%</div>
                <p className="text-xs text-muted-foreground">
                  {mockBacktestResult.profit_trades}胜 / {mockBacktestResult.loss_trades}负
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">最大回撤</CardTitle>
                <TrendingDown className="h-4 w-4 text-red-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-500">{mockBacktestResult.max_drawdown}%</div>
                <p className="text-xs text-muted-foreground">
                  风险控制良好
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">夏普比率</CardTitle>
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{mockBacktestResult.sharpe_ratio}</div>
                <Badge variant="success" className="mt-1">优秀</Badge>
              </CardContent>
            </Card>
          </div>

          {/* 主内容区域 - Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
            <TabsList className="grid w-full grid-cols-3 lg:w-auto lg:inline-grid">
              <TabsTrigger value="overview">策略概览</TabsTrigger>
              <TabsTrigger value="config">参数配置</TabsTrigger>
              <TabsTrigger value="analysis">高级分析</TabsTrigger>
            </TabsList>

            {/* 策略概览 */}
            <TabsContent value="overview" className="space-y-4">
              {/* 当前策略信息 */}
              <Card>
                <CardHeader>
                  <CardTitle>当前策略: {currentStrategy?.name}</CardTitle>
                  <CardDescription>
                    {currentStrategy?.type} - 基于均线系统的趋势跟踪策略
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div className="space-y-1">
                      <p className="text-muted-foreground">策略类型</p>
                      <p className="font-medium">{currentStrategy?.type}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-muted-foreground">交易标的</p>
                      <p className="font-medium">A股主板/创业板</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-muted-foreground">持仓周期</p>
                      <p className="font-medium">中短线 (5-30天)</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-muted-foreground">最大持仓</p>
                      <p className="font-medium">5 只股票</p>
                    </div>
                  </div>

                  <div className="mt-4 pt-4 border-t">
                    <h4 className="text-sm font-medium mb-2">策略逻辑</h4>
                    <ul className="text-sm text-muted-foreground space-y-1">
                      <li className="flex items-start gap-2">
                        <ChevronRight className="h-4 w-4 mt-0.5 text-primary" />
                        <span>买入信号：股价突破中期均线且成交量放大</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <ChevronRight className="h-4 w-4 mt-0.5 text-primary" />
                        <span>加仓条件：底仓浮盈超过8%且回踩支撑确认</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <ChevronRight className="h-4 w-4 mt-0.5 text-primary" />
                        <span>止盈止损：硬止损10%，移动止盈25%</span>
                      </li>
                    </ul>
                  </div>
                </CardContent>
              </Card>

              {/* 回测股票列表 */}
              <Card>
                <CardHeader>
                  <CardTitle>回测股票列表</CardTitle>
                  <CardDescription>本策略基于以下股票进行回测</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {backtestStocks.map((stock) => (
                      <div key={stock.symbol} className="p-3 border rounded-lg hover:bg-muted/50 transition-colors">
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-bold">{stock.symbol}</span>
                          <Badge variant="outline" className="text-xs">{stock.trades} 笔</Badge>
                        </div>
                        <div className="text-sm text-muted-foreground">{stock.name}</div>
                        <div className={`text-sm font-medium mt-1 ${stock.return_pct >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                          {stock.return_pct >= 0 ? '+' : ''}{stock.return_pct.toFixed(2)}%
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* 动态资产曲线和回撤曲线 */}
              <div className="grid gap-4 lg:grid-cols-2">
                <EquityCurveChart strategyId={selectedStrategy} />
                <DrawdownChart strategyId={selectedStrategy} />
              </div>

              {/* K线信号可视化 */}
              <KlineSignalChart strategyId={selectedStrategy} />

              {/* 盈亏占比、资金占比、胜率饼图 */}
              <div className="grid gap-4 lg:grid-cols-3">
                <PnlImpactCard totalEquity={1000000} />
                <CapitalUsageCard totalEquity={1000000} availableCash={300000} />
                <WinRatePieChart />
              </div>

              {/* 交易日志 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5 text-primary" />
                    详细交易日志
                  </CardTitle>
                  <CardDescription>
                    查看策略历史交易记录和信号详情
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <TradeLogTable />
                </CardContent>
              </Card>
            </TabsContent>

            {/* 参数配置 */}
            <TabsContent value="config" className="space-y-4">
              <div className="grid gap-4 lg:grid-cols-2">
                {/* 风控参数 */}
                <Card>
                  <CardHeader>
                    <CardTitle>风控参数</CardTitle>
                    <CardDescription>设置止损止盈和仓位管理参数</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <Label>硬止损比例</Label>
                          <span className="text-sm font-medium text-red-500">
                            {(config.stop_loss_pct * 100).toFixed(0)}%
                          </span>
                        </div>
                        <Slider
                          value={[config.stop_loss_pct * 100]}
                          onValueChange={(v: number[]) => setConfig({ ...config, stop_loss_pct: v[0] / 100 })}
                          min={5}
                          max={20}
                          step={1}
                        />
                        <p className="text-xs text-muted-foreground">
                          亏损达到该比例无条件止损
                        </p>
                      </div>

                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <Label>移动止盈比例</Label>
                          <span className="text-sm font-medium text-green-500">
                            {(config.trailing_stop_pct * 100).toFixed(0)}%
                          </span>
                        </div>
                        <Slider
                          value={[config.trailing_stop_pct * 100]}
                          onValueChange={(v: number[]) => setConfig({ ...config, trailing_stop_pct: v[0] / 100 })}
                          min={10}
                          max={50}
                          step={5}
                        />
                        <p className="text-xs text-muted-foreground">
                          最高点回撤达到该比例止盈
                        </p>
                      </div>

                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <Label>单票最大仓位</Label>
                          <span className="text-sm font-medium">
                            {(config.max_position_pct * 100).toFixed(0)}%
                          </span>
                        </div>
                        <Slider
                          value={[config.max_position_pct * 100]}
                          onValueChange={(v: number[]) => setConfig({ ...config, max_position_pct: v[0] / 100 })}
                          min={10}
                          max={50}
                          step={5}
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* 技术指标参数 */}
                <Card>
                  <CardHeader>
                    <CardTitle>技术指标参数</CardTitle>
                    <CardDescription>设置均线系统和信号过滤参数</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="ma_short">短期均线</Label>
                        <Input
                          id="ma_short"
                          type="number"
                          value={config.ma_short}
                          onChange={(e) => setConfig({ ...config, ma_short: parseInt(e.target.value) })}
                        />
                        <p className="text-xs text-muted-foreground">日线</p>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="ma_mid">中期均线</Label>
                        <Input
                          id="ma_mid"
                          type="number"
                          value={config.ma_mid}
                          onChange={(e) => setConfig({ ...config, ma_mid: parseInt(e.target.value) })}
                        />
                        <p className="text-xs text-muted-foreground">日线</p>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="ma_long">长期均线</Label>
                        <Input
                          id="ma_long"
                          type="number"
                          value={config.ma_long}
                          onChange={(e) => setConfig({ ...config, ma_long: parseInt(e.target.value) })}
                        />
                        <p className="text-xs text-muted-foreground">日线</p>
                      </div>
                    </div>

                    <div className="pt-4 border-t space-y-4">
                      <div className="space-y-2">
                        <Label htmlFor="bias_entry_limit">首次建仓偏离限制</Label>
                        <Input
                          id="bias_entry_limit"
                          type="number"
                          step="0.01"
                          value={config.bias_entry_limit}
                          onChange={(e) => setConfig({ ...config, bias_entry_limit: parseFloat(e.target.value) })}
                        />
                        <p className="text-xs text-muted-foreground">
                          收盘价/中期均线 &lt; 该值才允许建仓
                        </p>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="add_pos_min_profit">加仓最低浮盈</Label>
                        <Input
                          id="add_pos_min_profit"
                          type="number"
                          step="0.01"
                          value={config.add_pos_min_profit}
                          onChange={(e) => setConfig({ ...config, add_pos_min_profit: parseFloat(e.target.value) })}
                        />
                        <p className="text-xs text-muted-foreground">
                          底仓必须浮盈该比例以上才允许加仓
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* 操作按钮 */}
              <div className="flex gap-3">
                <Button size="lg">
                  <Settings className="mr-2 h-4 w-4" />
                  保存配置
                </Button>
                <Button variant="outline" size="lg">
                  <RefreshCw className="mr-2 h-4 w-4" />
                  重置默认
                </Button>
              </div>
            </TabsContent>

            {/* 高级分析 */}
            <TabsContent value="analysis" className="space-y-4">
              <div className="grid gap-4">
                {/* 参数敏感度热力图 */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Grid3X3 className="h-5 w-5 text-primary" />
                      参数敏感度分析
                    </CardTitle>
                    <CardDescription>
                      扫描不同参数组合的历史表现，寻找最优参数
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ParameterHeatmap />
                  </CardContent>
                </Card>

                {/* 风险归因分析 */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <PieChart className="h-5 w-5 text-primary" />
                      风险归因分析
                    </CardTitle>
                    <CardDescription>
                      分析收益来源和风险暴露
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <RiskAttribution />
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  )
}
