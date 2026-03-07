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
    // 模拟回测延迟
    await new Promise(resolve => setTimeout(resolve, 2000))
    setIsBacktesting(false)
    setShowBacktestResult(true)
  }

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
            <div className="flex items-center gap-3">
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
                  +25.49%
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
                <div className="text-2xl font-bold">62.5%</div>
                <p className="text-xs text-muted-foreground">
                  30胜 / 18负
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">最大回撤</CardTitle>
                <TrendingDown className="h-4 w-4 text-red-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-500">-8.32%</div>
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
                <div className="text-2xl font-bold">1.85</div>
                <Badge variant="success" className="mt-1">优秀</Badge>
              </CardContent>
            </Card>
          </div>

          {/* 主内容区域 - Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
            <TabsList className="grid w-full grid-cols-3 lg:w-auto lg:inline-grid">
              <TabsTrigger value="overview">策略概览</TabsTrigger>
              <TabsTrigger value="config">参数配置</TabsTrigger>
              <TabsTrigger value="backtest">历史回测</TabsTrigger>
            </TabsList>

            {/* 策略概览 */}
            <TabsContent value="overview" className="space-y-4">
              <div className="grid gap-4 lg:grid-cols-3">
                {/* 当前策略信息 */}
                <Card className="lg:col-span-2">
                  <CardHeader>
                    <CardTitle>当前策略: 趋势跟踪策略 v2.0</CardTitle>
                    <CardDescription>
                      基于均线系统的趋势跟踪策略，配合动态仓位管理
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div className="space-y-1">
                        <p className="text-muted-foreground">策略类型</p>
                        <p className="font-medium">趋势跟踪</p>
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
                        <li className="flex items-start gap-2">
                          <ChevronRight className="h-4 w-4 mt-0.5 text-primary" />
                          <span>仓位管理：单只股票最大仓位30%</span>
                        </li>
                      </ul>
                    </div>
                  </CardContent>
                </Card>

                {/* 风控参数 */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-amber-500" />
                      风控参数
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">单票最大仓位</span>
                        <span className="font-medium">30%</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div className="h-full bg-primary w-[30%]" />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">硬止损线</span>
                        <span className="font-medium text-red-500">-10%</span>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">移动止盈</span>
                        <span className="font-medium text-green-500">25%</span>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">最大持仓数</span>
                        <span className="font-medium">5 只</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* 月度收益 */}
              <Card>
                <CardHeader>
                  <CardTitle>月度收益分布</CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={mockBacktestResult.monthly_returns}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis dataKey="month" className="text-xs" />
                      <YAxis className="text-xs" tickFormatter={(v) => `${v}%`} />
                      <Tooltip
                        formatter={(value) => [`${value}%`, '收益率']}
                        contentStyle={{
                          backgroundColor: 'hsl(var(--popover))',
                          border: '1px solid hsl(var(--border))',
                          borderRadius: '8px',
                        }}
                      />
                      <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" />
                      <Bar
                        dataKey="return"
                        fill="hsl(var(--primary))"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
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

            {/* 历史回测 */}
            <TabsContent value="backtest" className="space-y-4">
              {/* 回测参数设置 */}
              <Card>
                <CardHeader>
                  <CardTitle>回测设置</CardTitle>
                  <CardDescription>选择回测时间范围和初始资金</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                    <div className="space-y-2">
                      <Label>开始日期</Label>
                      <Input
                        type="date"
                        value={backtestParams.startDate}
                        onChange={(e) => setBacktestParams({ ...backtestParams, startDate: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>结束日期</Label>
                      <Input
                        type="date"
                        value={backtestParams.endDate}
                        onChange={(e) => setBacktestParams({ ...backtestParams, endDate: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>初始资金</Label>
                      <Input
                        type="number"
                        value={backtestParams.initialCapital}
                        onChange={(e) => setBacktestParams({ ...backtestParams, initialCapital: parseInt(e.target.value) })}
                      />
                    </div>
                    <Button
                      size="lg"
                      onClick={runBacktest}
                      disabled={isBacktesting}
                      className="bg-gradient-to-r from-primary to-primary/80"
                    >
                      {isBacktesting ? (
                        <>
                          <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                          回测中...
                        </>
                      ) : (
                        <>
                          <Play className="mr-2 h-4 w-4" />
                          开始回测
                        </>
                      )}
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* 回测结果 */}
              {showBacktestResult && (
                <>
                  {/* 关键指标 */}
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
                    <Card className="bg-gradient-to-br from-green-50 to-green-100/50 dark:from-green-950/30">
                      <CardContent className="pt-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm text-muted-foreground">总收益</p>
                            <p className="text-2xl font-bold text-green-600">
                              +{mockBacktestResult.total_return}%
                            </p>
                          </div>
                          <TrendingUp className="h-8 w-8 text-green-500/50" />
                        </div>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardContent className="pt-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm text-muted-foreground">年化收益</p>
                            <p className="text-2xl font-bold">{mockBacktestResult.annualized_return}%</p>
                          </div>
                          <DollarSign className="h-8 w-8 text-muted-foreground/50" />
                        </div>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardContent className="pt-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm text-muted-foreground">最大回撤</p>
                            <p className="text-2xl font-bold text-red-500">{mockBacktestResult.max_drawdown}%</p>
                          </div>
                          <TrendingDown className="h-8 w-8 text-red-500/50" />
                        </div>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardContent className="pt-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm text-muted-foreground">夏普比率</p>
                            <p className="text-2xl font-bold">{mockBacktestResult.sharpe_ratio}</p>
                          </div>
                          <Activity className="h-8 w-8 text-muted-foreground/50" />
                        </div>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardContent className="pt-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm text-muted-foreground">胜率</p>
                            <p className="text-2xl font-bold">{mockBacktestResult.win_rate}%</p>
                          </div>
                          <Target className="h-8 w-8 text-muted-foreground/50" />
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  {/* 收益曲线 */}
                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between">
                      <div>
                        <CardTitle>权益曲线</CardTitle>
                        <CardDescription>策略收益 vs 基准收益</CardDescription>
                      </div>
                      <Button variant="outline" size="sm">
                        <Download className="h-4 w-4 mr-2" />
                        导出报告
                      </Button>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={300}>
                        <AreaChart data={mockBacktestResult.equity_curve}>
                          <defs>
                            <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                              <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0.02} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis dataKey="date" className="text-xs" />
                          <YAxis
                            className="text-xs"
                            tickFormatter={(v) => `¥${(v / 10000).toFixed(0)}万`}
                          />
                          <Tooltip
                            formatter={(value, name) => [
                              `¥${(value as number).toLocaleString()}`,
                              name === 'equity' ? '策略' : '基准'
                            ]}
                            contentStyle={{
                              backgroundColor: 'hsl(var(--popover))',
                              border: '1px solid hsl(var(--border))',
                              borderRadius: '8px',
                            }}
                          />
                          <Area
                            type="monotone"
                            dataKey="benchmark"
                            stroke="hsl(var(--muted-foreground))"
                            strokeDasharray="5 5"
                            fill="transparent"
                            strokeWidth={1.5}
                          />
                          <Area
                            type="monotone"
                            dataKey="equity"
                            stroke="hsl(var(--primary))"
                            fill="url(#equityGradient)"
                            strokeWidth={2.5}
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>

                  {/* 详细统计 */}
                  <div className="grid gap-4 lg:grid-cols-2">
                    {/* 交易统计 */}
                    <Card>
                      <CardHeader>
                        <CardTitle>交易统计</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-1">
                            <p className="text-sm text-muted-foreground">总交易次数</p>
                            <p className="text-xl font-bold">{mockBacktestResult.total_trades}</p>
                          </div>
                          <div className="space-y-1">
                            <p className="text-sm text-muted-foreground">盈利次数</p>
                            <p className="text-xl font-bold text-green-600">{mockBacktestResult.profit_trades}</p>
                          </div>
                          <div className="space-y-1">
                            <p className="text-sm text-muted-foreground">亏损次数</p>
                            <p className="text-xl font-bold text-red-600">{mockBacktestResult.loss_trades}</p>
                          </div>
                          <div className="space-y-1">
                            <p className="text-sm text-muted-foreground">盈亏比</p>
                            <p className="text-xl font-bold">{mockBacktestResult.profit_factor}</p>
                          </div>
                          <div className="space-y-1">
                            <p className="text-sm text-muted-foreground">平均盈利</p>
                            <p className="text-xl font-bold text-green-600">
                              +¥{mockBacktestResult.avg_profit.toLocaleString()}
                            </p>
                          </div>
                          <div className="space-y-1">
                            <p className="text-sm text-muted-foreground">平均亏损</p>
                            <p className="text-xl font-bold text-red-600">
                              ¥{mockBacktestResult.avg_loss.toLocaleString()}
                            </p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    {/* 风险指标 */}
                    <Card>
                      <CardHeader>
                        <CardTitle>风险指标</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-1">
                            <p className="text-sm text-muted-foreground">卡玛比率</p>
                            <p className="text-xl font-bold">{mockBacktestResult.calmar_ratio}</p>
                            <p className="text-xs text-muted-foreground">收益/最大回撤</p>
                          </div>
                          <div className="space-y-1">
                            <p className="text-sm text-muted-foreground">夏普比率</p>
                            <p className="text-xl font-bold">{mockBacktestResult.sharpe_ratio}</p>
                            <p className="text-xs text-muted-foreground">风险调整收益</p>
                          </div>
                          <div className="col-span-2 pt-4 border-t">
                            <p className="text-sm text-muted-foreground mb-2">风险评估</p>
                            <div className="flex items-center gap-2">
                              <Badge variant="success" className="px-3 py-1">
                                <Zap className="h-3 w-3 mr-1" />
                                低风险
                              </Badge>
                              <span className="text-sm text-muted-foreground">
                                回撤控制良好，收益稳定性高
                              </span>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  )
}
