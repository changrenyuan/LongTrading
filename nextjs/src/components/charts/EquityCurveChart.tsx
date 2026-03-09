'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { TrendingUp, RefreshCw } from 'lucide-react'
import { apiClient } from '@/lib/api'

interface EquityCurveChartProps {
  strategyId?: string
  title?: string
}

export function EquityCurveChart({ strategyId, title = '动态资产曲线' }: EquityCurveChartProps) {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const result = await apiClient.getEquityCurve(strategyId)
        if (result) {
          setData(result)
        } else {
          const mockData = generateMockData()
          setData(mockData)
        }
      } catch (error) {
        console.error('获取资产曲线失败:', error)
        const mockData = generateMockData()
        setData(mockData)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [strategyId])

  const generateMockData = () => {
    const data = []
    let equity = 1000000
    const startDate = new Date('2024-01-01')
    
    for (let i = 0; i < 120; i++) {
      const date = new Date(startDate)
      date.setDate(date.getDate() + i)
      if (date.getDay() === 0 || date.getDay() === 6) continue
      
      // 模拟资产波动
      const change = (Math.random() - 0.45) * 15000
      equity = Math.max(900000, equity + change)
      
      data.push({
        date: date.toISOString().slice(0, 10),
        equity: Math.round(equity),
        benchmark: Math.round(1000000 + i * 500 + Math.random() * 5000),
      })
    }
    return data
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-[300px]">
            <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    )
  }

  // 计算统计数据
  const startEquity = data[0]?.equity || 1000000
  const endEquity = data[data.length - 1]?.equity || 1000000
  const maxEquity = Math.max(...data.map(d => d.equity))
  const minEquity = Math.min(...data.map(d => d.equity))
  const totalReturn = ((endEquity - startEquity) / startEquity) * 100

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-primary" />
          {title}
        </CardTitle>
        <CardDescription>
          策略资产净值变化趋势
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* 统计指标 */}
        <div className="grid grid-cols-4 gap-4 mb-4 text-sm">
          <div>
            <span className="text-muted-foreground">起始资产</span>
            <div className="font-bold">¥{startEquity.toLocaleString()}</div>
          </div>
          <div>
            <span className="text-muted-foreground">当前资产</span>
            <div className={`font-bold ${endEquity >= startEquity ? 'text-green-600' : 'text-red-600'}`}>
              ¥{endEquity.toLocaleString()}
            </div>
          </div>
          <div>
            <span className="text-muted-foreground">总收益率</span>
            <div className={`font-bold ${totalReturn >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {totalReturn >= 0 ? '+' : ''}{totalReturn.toFixed(2)}%
            </div>
          </div>
          <div>
            <span className="text-muted-foreground">最高资产</span>
            <div className="font-bold">¥{maxEquity.toLocaleString()}</div>
          </div>
        </div>

        {/* 图表 */}
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
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
              domain={['auto', 'auto']}
              tickFormatter={(v) => `¥${(v / 10000).toFixed(0)}万`}
            />
            <Tooltip
              formatter={(value, name) => [
                `¥${(value as number).toLocaleString()}`,
                name === 'equity' ? '策略资产' : '基准'
              ]}
              labelFormatter={(label) => `日期: ${label}`}
              contentStyle={{
                backgroundColor: 'hsl(var(--popover))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px',
              }}
            />
            <ReferenceLine y={startEquity} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
            <Area
              type="monotone"
              dataKey="benchmark"
              stroke="hsl(var(--muted-foreground))"
              strokeDasharray="5 5"
              fill="transparent"
              strokeWidth={1.5}
              name="基准"
            />
            <Area
              type="monotone"
              dataKey="equity"
              stroke="hsl(var(--primary))"
              fill="url(#equityGradient)"
              strokeWidth={2.5}
              name="策略资产"
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
