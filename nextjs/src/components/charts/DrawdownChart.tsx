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
import { TrendingDown, RefreshCw, AlertTriangle } from 'lucide-react'
import { apiClient } from '@/lib/api'

interface DrawdownChartProps {
  strategyId?: string
  title?: string
}

export function DrawdownChart({ strategyId, title = '动态回撤曲线' }: DrawdownChartProps) {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const result = await apiClient.getDrawdown(strategyId)
        if (result) {
          setData(result)
        } else {
          const mockData = generateMockData()
          setData(mockData)
        }
      } catch (error) {
        console.error('获取回撤数据失败:', error)
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
    let peak = 1000000
    let equity = 1000000
    const startDate = new Date('2024-01-01')
    
    for (let i = 0; i < 120; i++) {
      const date = new Date(startDate)
      date.setDate(date.getDate() + i)
      if (date.getDay() === 0 || date.getDay() === 6) continue
      
      const change = (Math.random() - 0.45) * 15000
      equity = Math.max(900000, equity + change)
      peak = Math.max(peak, equity)
      
      const drawdown = ((equity - peak) / peak) * 100
      
      data.push({
        date: date.toISOString().slice(0, 10),
        drawdown: parseFloat(drawdown.toFixed(2)),
        equity: Math.round(equity),
        peak: Math.round(peak),
      })
    }
    return data
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingDown className="h-5 w-5 text-red-500" />
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
  const maxDrawdown = Math.min(...data.map(d => d.drawdown))
  const currentDrawdown = data[data.length - 1]?.drawdown || 0
  const avgDrawdown = data.reduce((sum, d) => sum + d.drawdown, 0) / data.length

  // 风险等级判断
  const getRiskLevel = (dd: number) => {
    if (dd > -5) return { level: '低风险', color: 'text-green-600' }
    if (dd > -10) return { level: '中等风险', color: 'text-yellow-600' }
    if (dd > -20) return { level: '较高风险', color: 'text-orange-600' }
    return { level: '高风险', color: 'text-red-600' }
  }

  const riskInfo = getRiskLevel(maxDrawdown)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingDown className="h-5 w-5 text-red-500" />
          {title}
        </CardTitle>
        <CardDescription>
          资产净值从历史最高点的回撤幅度
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* 统计指标 */}
        <div className="grid grid-cols-4 gap-4 mb-4 text-sm">
          <div>
            <span className="text-muted-foreground">最大回撤</span>
            <div className={`font-bold ${riskInfo.color}`}>
              {maxDrawdown.toFixed(2)}%
            </div>
          </div>
          <div>
            <span className="text-muted-foreground">当前回撤</span>
            <div className={`font-bold ${currentDrawdown >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {currentDrawdown.toFixed(2)}%
            </div>
          </div>
          <div>
            <span className="text-muted-foreground">平均回撤</span>
            <div className="font-bold">{avgDrawdown.toFixed(2)}%</div>
          </div>
          <div>
            <span className="text-muted-foreground">风险等级</span>
            <div className={`font-bold ${riskInfo.color}`}>
              {riskInfo.level}
            </div>
          </div>
        </div>

        {/* 回撤预警 */}
        {currentDrawdown < -10 && (
          <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-950/30 rounded-lg mb-4 text-sm">
            <AlertTriangle className="h-4 w-4 text-red-500" />
            <span className="text-red-600">当前回撤超过10%，请注意风险控制</span>
          </div>
        )}

        {/* 图表 */}
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id="drawdownGradient" x1="0" y1="0" x2="0" y2="1">
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
              domain={['auto', 5]}
            />
            <Tooltip
              formatter={(value, name) => {
                if (name === 'drawdown') return [`${value}%`, '回撤']
                return [value, name]
              }}
              labelFormatter={(label) => `日期: ${label}`}
              contentStyle={{
                backgroundColor: 'hsl(var(--popover))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px',
              }}
            />
            <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
            <ReferenceLine y={-5} stroke="#f59e0b" strokeDasharray="3 3" />
            <ReferenceLine y={-10} stroke="#ef4444" strokeDasharray="3 3" />
            <Area
              type="monotone"
              dataKey="drawdown"
              stroke="#ef4444"
              fill="url(#drawdownGradient)"
              strokeWidth={2}
              name="回撤"
            />
          </AreaChart>
        </ResponsiveContainer>

        {/* 图例 */}
        <div className="flex items-center gap-4 mt-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <div className="w-3 h-0.5 bg-yellow-500" />
            <span>-5% 预警线</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-0.5 bg-red-500" />
            <span>-10% 风险线</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
