'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import { TrendingUp, Info } from 'lucide-react'
import { apiClient } from '@/lib/api'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']

interface RiskAttributionProps {
  title?: string
}

export function RiskAttribution({ title = '风险归因分析' }: RiskAttributionProps) {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const result = await apiClient.getRiskAttribution()
        setData(result)
      } catch (error) {
        console.error('获取风险归因数据失败:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  if (loading) {
    return <div className="text-center py-8 text-muted-foreground">加载中...</div>
  }

  if (!data) {
    return <div className="text-center py-8 text-muted-foreground">暂无数据</div>
  }

  const { alpha, beta, tracking_error, information_ratio, sector_exposure, factor_exposure } = data

  return (
    <div className="space-y-4">
      {/* Alpha/Beta 指标 */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Alpha (超额收益)</p>
                <p className="text-2xl font-bold text-green-600">+{alpha}%</p>
              </div>
              <TrendingUp className="h-8 w-8 text-green-500/50" />
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              相对基准的超额收益能力
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Beta</p>
                <p className="text-2xl font-bold">{beta}</p>
              </div>
              <Info className="h-8 w-8 text-muted-foreground/50" />
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              相对市场的敏感度
            </p>
          </CardContent>
        </Card>
      </div>

      {/* 其他风险指标 */}
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="p-3 bg-muted/50 rounded-lg">
          <span className="text-muted-foreground">跟踪误差:</span>
          <span className="ml-2 font-medium">{tracking_error}%</span>
        </div>
        <div className="p-3 bg-muted/50 rounded-lg">
          <span className="text-muted-foreground">信息比率:</span>
          <span className="ml-2 font-medium">{information_ratio}</span>
        </div>
      </div>

      {/* 行业分布 */}
      <div>
        <h4 className="text-sm font-medium mb-2">行业分布</h4>
        <ResponsiveContainer width="100%" height={200}>
          <PieChart>
            <Pie
              data={sector_exposure}
              dataKey="weight"
              nameKey="sector"
              cx="50%"
              cy="50%"
              outerRadius={70}
              label={(props: any) => `${props.sector} ${props.weight.toFixed(0)}%`}
            >
              {sector_exposure.map((entry: any, index: number) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value, name, props: any) => [
                `${(value as number).toFixed(1)}%`,
                props.payload.sector
              ]}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* 因子暴露 */}
      <div>
        <h4 className="text-sm font-medium mb-2">因子暴露</h4>
        <ResponsiveContainer width="100%" height={150}>
          <BarChart
            data={factor_exposure}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 60, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis type="number" className="text-xs" />
            <YAxis
              type="category"
              dataKey="factor"
              className="text-xs"
              width={50}
            />
            <Tooltip
              formatter={(value) => [typeof value === 'number' ? value.toFixed(3) : value, '暴露度']}
              contentStyle={{
                backgroundColor: 'hsl(var(--popover))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px',
              }}
            />
            <Bar
              dataKey="exposure"
              fill="hsl(var(--primary))"
              radius={[0, 4, 4, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
