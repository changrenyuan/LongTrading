'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
  Legend,
  AreaChart,
  Area,
  ReferenceLine,
} from 'recharts'
import { ArrowUpCircle, ArrowDownCircle, RefreshCw, CandlestickChart, TrendingUp, Wallet } from 'lucide-react'
import { apiClient } from '@/lib/api'

interface KlineSignalChartProps {
  strategyId?: string
}

export function KlineSignalChart({ strategyId }: KlineSignalChartProps) {
  const [stocks, setStocks] = useState<any[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState('300308')
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  // 获取回测股票列表
  useEffect(() => {
    const fetchStocks = async () => {
      try {
        const stocksData = await apiClient.getBacktestStocks()
        if (stocksData) {
          setStocks(stocksData)
          if (stocksData.length > 0) {
            setSelectedSymbol(stocksData[0].symbol)
          }
        }
      } catch (error) {
        console.error('获取股票列表失败:', error)
      }
    }
    fetchStocks()
  }, [])

  // 获取K线数据
  useEffect(() => {
    if (!selectedSymbol) return

    const fetchData = async () => {
      setLoading(true)
      try {
        const result = await apiClient.getKlineSignals(selectedSymbol)
        setData(result)
      } catch (error) {
        console.error('获取K线数据失败:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [selectedSymbol])

  if (loading && !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CandlestickChart className="h-5 w-5 text-primary" />
            K线信号可视化
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-64">
            <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!data) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center py-8 text-muted-foreground">暂无数据</div>
        </CardContent>
      </Card>
    )
  }

  const { kline, signals, name, pnlRatioData, capitalUsageData } = data

  // 将信号合并到K线数据中
  const klineWithSignals = kline.map((item: any) => {
    const signal = signals.find((s: any) => s.date === item.date)
    return {
      ...item,
      signal: signal || null,
    }
  })

  // 计算Y轴范围
  const prices = kline.map((d: any) => [d.high, d.low]).flat()
  const minPrice = Math.min(...prices) * 0.95
  const maxPrice = Math.max(...prices) * 1.05

  // 计算选中股票的统计
  const stockInfo = stocks.find(s => s.symbol === selectedSymbol)

  return (
    <div className="space-y-4">
      {/* 主卡片：股票选择和基本信息 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <CandlestickChart className="h-5 w-5 text-primary" />
                K线信号可视化
              </CardTitle>
              <CardDescription>
                查看K线图、买卖信号及资金分析
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">选择股票:</span>
              <Select value={selectedSymbol} onValueChange={setSelectedSymbol}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="选择股票" />
                </SelectTrigger>
                <SelectContent>
                  {stocks.map((stock) => (
                    <SelectItem key={stock.symbol} value={stock.symbol}>
                      <div className="flex items-center justify-between w-full gap-4">
                        <span>{stock.symbol}</span>
                        <span className="text-xs text-muted-foreground">{stock.name}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* 股票信息 */}
          <div className="flex items-center justify-between mb-4">
            <div>
              <span className="text-lg font-bold">{data.symbol}</span>
              <span className="ml-2 text-muted-foreground">{name}</span>
            </div>
            <div className="flex items-center gap-4 text-sm">
              {stockInfo && (
                <>
                  <div>
                    <span className="text-muted-foreground">收益率: </span>
                    <span className={`font-bold ${stockInfo.return_pct >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                      {stockInfo.return_pct >= 0 ? '+' : ''}{stockInfo.return_pct.toFixed(2)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">交易次数: </span>
                    <span className="font-medium">{stockInfo.trades} 笔</span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* 主图：K线图 */}
          <div className="mb-2">
            <h4 className="text-sm font-medium text-muted-foreground mb-2">价格走势与信号</h4>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={klineWithSignals}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="date"
                className="text-xs"
                interval="preserveStartEnd"
                tickFormatter={(v) => v.slice(5)}
              />
              <YAxis
                domain={[minPrice, maxPrice]}
                className="text-xs"
                tickFormatter={(v) => `¥${v.toFixed(0)}`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--popover))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                }}
                formatter={(value, name, props: any) => {
                  if (name === 'close' && props.payload) {
                    const p = props.payload
                    return [
                      <div key="tooltip" className="text-xs space-y-1">
                        <div>开: ¥{p.open?.toFixed(2)}</div>
                        <div>高: ¥{p.high?.toFixed(2)}</div>
                        <div>低: ¥{p.low?.toFixed(2)}</div>
                        <div>收: ¥{p.close?.toFixed(2)}</div>
                      </div>,
                      'K线'
                    ]
                  }
                  if (value === undefined || value === null) return ['-', name]
                  return [`¥${(value as number).toFixed(2)}`, name]
                }}
                labelFormatter={(label) => `日期: ${label}`}
              />
              <Legend />

              {/* 最高价线 */}
              <Line
                type="monotone"
                dataKey="high"
                stroke="#6b7280"
                strokeWidth={1}
                dot={false}
                name="最高价"
                strokeDasharray="2 2"
              />

              {/* 最低价线 */}
              <Line
                type="monotone"
                dataKey="low"
                stroke="#6b7280"
                strokeWidth={1}
                dot={false}
                name="最低价"
                strokeDasharray="2 2"
              />

              {/* 收盘价线（主价格线） */}
              <Line
                type="monotone"
                dataKey="close"
                stroke="#1f2937"
                strokeWidth={2}
                dot={false}
                name="收盘价"
              />

              {/* MA5 */}
              <Line
                type="monotone"
                dataKey="ma5"
                stroke="#f59e0b"
                strokeWidth={1.5}
                dot={false}
                name="MA5"
                connectNulls
              />

              {/* MA20 */}
              <Line
                type="monotone"
                dataKey="ma20"
                stroke="#3b82f6"
                strokeWidth={1.5}
                dot={false}
                name="MA20"
                connectNulls
              />

              {/* 买入信号 */}
              {signals
                .filter((s: any) => s.action === 'BUY')
                .map((signal: any, index: number) => {
                  const klineItem = kline.find((k: any) => k.date === signal.date)
                  if (!klineItem) return null
                  return (
                    <ReferenceDot
                      key={`buy-${index}`}
                      x={signal.date}
                      y={klineItem.low * 0.98}
                      r={8}
                      fill="#10b981"
                      stroke="white"
                    />
                  )
                })}

              {/* 卖出信号 */}
              {signals
                .filter((s: any) => s.action === 'SELL')
                .map((signal: any, index: number) => {
                  const klineItem = kline.find((k: any) => k.date === signal.date)
                  if (!klineItem) return null
                  return (
                    <ReferenceDot
                      key={`sell-${index}`}
                      x={signal.date}
                      y={klineItem.high * 1.02}
                      r={8}
                      fill="#ef4444"
                      stroke="white"
                    />
                  )
                })}
            </ComposedChart>
          </ResponsiveContainer>

          {/* 信号列表 */}
          <div className="space-y-2 mt-4">
            <h4 className="text-sm font-medium">交易信号</h4>
            <div className="space-y-2 max-h-[150px] overflow-y-auto">
              {signals.map((signal: any, index: number) => (
                <div
                  key={index}
                  className="flex items-start gap-2 p-2 bg-muted/50 rounded-lg"
                >
                  {signal.action === 'BUY' ? (
                    <ArrowUpCircle className="h-5 w-5 text-green-500 mt-0.5 shrink-0" />
                  ) : (
                    <ArrowDownCircle className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium">
                        {signal.action === 'BUY' ? '买入' : '卖出'}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        ¥{(signal.price ?? 0).toFixed(2)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {signal.date}
                      </span>
                      {signal.shares && (
                        <span className="text-xs text-muted-foreground">
                          {signal.shares}股
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground truncate">{signal.reason || '-'}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 副图1：盈亏占比时间曲线 */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <TrendingUp className="h-4 w-4 text-primary" />
                盈亏金额占总资金比例
              </CardTitle>
              <CardDescription className="text-xs">
                红色盈利，绿色亏损
              </CardDescription>
            </div>
            {pnlRatioData && pnlRatioData.length > 0 && (
              <div className="text-right">
                <div className={`text-lg font-bold ${pnlRatioData[pnlRatioData.length - 1].pnlRatio >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                  {pnlRatioData[pnlRatioData.length - 1].pnlRatio >= 0 ? '+' : ''}{pnlRatioData[pnlRatioData.length - 1].pnlRatio.toFixed(2)}%
                </div>
                <div className="text-xs text-muted-foreground">当前占比</div>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={pnlRatioData}>
              <defs>
                <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="date"
                className="text-xs"
                interval="preserveStartEnd"
                tickFormatter={(v) => v.slice(5)}
              />
              <YAxis
                className="text-xs"
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--popover))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                }}
                formatter={(value, name) => {
                  if (name === 'pnlRatio') return [`${value}%`, '盈亏占比']
                  return [value, name]
                }}
                labelFormatter={(label) => `日期: ${label}`}
              />
              <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
              <Area
                type="monotone"
                dataKey="pnlRatio"
                stroke="#ef4444"
                fill="url(#pnlGradient)"
                strokeWidth={2}
                name="pnlRatio"
              />
            </AreaChart>
          </ResponsiveContainer>

          {/* 统计数据 */}
          <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t text-sm">
            <div>
              <span className="text-muted-foreground">最大盈利占比</span>
              <div className="font-bold text-red-600">
                +{Math.max(...(pnlRatioData?.map((d: any) => d.pnlRatio) || [0])).toFixed(2)}%
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">最大亏损占比</span>
              <div className="font-bold text-green-600">
                {Math.min(...(pnlRatioData?.map((d: any) => d.pnlRatio) || [0])).toFixed(2)}%
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">当前盈亏</span>
              <div className={`font-bold ${pnlRatioData?.[pnlRatioData.length - 1]?.totalPnl >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                {pnlRatioData?.[pnlRatioData.length - 1]?.totalPnl >= 0 ? '+' : ''}¥{pnlRatioData?.[pnlRatioData.length - 1]?.totalPnl?.toLocaleString() || 0}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 副图2：资金占用占比时间曲线 */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <Wallet className="h-4 w-4 text-primary" />
                资金占用占总资金比例
              </CardTitle>
              <CardDescription className="text-xs">
                显示该股票持仓市值占总资产的比例变化
              </CardDescription>
            </div>
            {capitalUsageData && capitalUsageData.length > 0 && (
              <div className="text-right">
                <div className="text-lg font-bold text-primary">
                  {capitalUsageData[capitalUsageData.length - 1].capitalUsage.toFixed(2)}%
                </div>
                <div className="text-xs text-muted-foreground">当前占比</div>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={capitalUsageData}>
              <defs>
                <linearGradient id="capitalGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="date"
                className="text-xs"
                interval="preserveStartEnd"
                tickFormatter={(v) => v.slice(5)}
              />
              <YAxis
                className="text-xs"
                tickFormatter={(v) => `${v}%`}
                domain={[0, 'auto']}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--popover))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                }}
                formatter={(value, name, props: any) => {
                  if (name === 'capitalUsage') return [`${value}%`, '资金占用占比']
                  return [value, name]
                }}
                labelFormatter={(label) => `日期: ${label}`}
              />
              <Area
                type="monotone"
                dataKey="capitalUsage"
                stroke="hsl(var(--primary))"
                fill="url(#capitalGradient)"
                strokeWidth={2}
                name="capitalUsage"
              />
            </AreaChart>
          </ResponsiveContainer>

          {/* 统计数据 */}
          <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t text-sm">
            <div>
              <span className="text-muted-foreground">最高占用</span>
              <div className="font-bold text-primary">
                {Math.max(...(capitalUsageData?.map((d: any) => d.capitalUsage) || [0])).toFixed(2)}%
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">平均占用</span>
              <div className="font-bold">
                {capitalUsageData ? (capitalUsageData.reduce((sum: number, d: any) => sum + d.capitalUsage, 0) / capitalUsageData.length).toFixed(2) : 0}%
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">当前持仓</span>
              <div className="font-bold">
                {capitalUsageData?.[capitalUsageData.length - 1]?.position?.toLocaleString() || 0} 股
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
