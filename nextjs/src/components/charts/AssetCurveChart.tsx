'use client'

import { useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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

interface AssetData {
  date: string
  equity: number
}

interface AssetCurveChartProps {
  data: AssetData[]
  title?: string
}

export function AssetCurveChart({ data, title = '资产净值曲线' }: AssetCurveChartProps) {
  // 计算起始净值用于参考线
  const startEquity = useMemo(() => {
    if (!data || data.length === 0) return 0
    return data[0].equity
  }, [data])

  // 计算最新净值
  const latestEquity = useMemo(() => {
    if (!data || data.length === 0) return 0
    return data[data.length - 1].equity
  }, [data])

  // 计算收益率
  const returnPct = useMemo(() => {
    if (startEquity === 0) return 0
    return ((latestEquity - startEquity) / startEquity) * 100
  }, [startEquity, latestEquity])

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-64 text-muted-foreground">
            暂无数据
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle>{title}</CardTitle>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-muted-foreground">
            最新: <span className="font-semibold text-foreground">¥{latestEquity.toLocaleString('zh-CN')}</span>
          </span>
          <span className={returnPct >= 0 ? 'text-green-600' : 'text-red-600'}>
            收益率: {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(2)}%
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={320}>
          <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" vertical={false} />
            <XAxis
              dataKey="date"
              className="text-xs"
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => {
                const date = new Date(value)
                return `${date.getMonth() + 1}/${date.getDate()}`
              }}
              interval="preserveStartEnd"
              minTickGap={50}
            />
            <YAxis
              className="text-xs"
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => `¥${(value / 10000).toFixed(0)}万`}
              domain={['auto', 'auto']}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--popover))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px',
                boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
              }}
              labelFormatter={(value) => {
                const date = new Date(value as string)
                return date.toLocaleDateString('zh-CN', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric'
                })
              }}
              formatter={(value) => [`¥${(value as number).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`, '净值']}
            />
            <ReferenceLine
              y={startEquity}
              stroke="hsl(var(--muted-foreground))"
              strokeDasharray="5 5"
              strokeOpacity={0.5}
            />
            <Area
              type="monotone"
              dataKey="equity"
              stroke="hsl(var(--primary))"
              strokeWidth={2.5}
              fill="url(#equityGradient)"
              dot={false}
              activeDot={{
                r: 6,
                fill: 'hsl(var(--primary))',
                stroke: 'hsl(var(--background))',
                strokeWidth: 2,
              }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
