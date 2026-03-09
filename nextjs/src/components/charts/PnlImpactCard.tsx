'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { TrendingUp, TrendingDown } from 'lucide-react'
import { apiClient } from '@/lib/api'

interface PnlImpactCardProps {
  trades?: any[]
  totalEquity?: number
}

export function PnlImpactCard({ trades: propTrades, totalEquity = 1000000 }: PnlImpactCardProps) {
  const [trades, setTrades] = useState<any[]>(propTrades || [])
  const [loading, setLoading] = useState(!propTrades)

  useEffect(() => {
    if (propTrades) {
      setTrades(propTrades)
      return
    }
    
    const fetchData = async () => {
      try {
        const data = await apiClient.getBacktestTrades()
        if (data) {
          setTrades(data)
        }
      } catch (error) {
        console.error('获取交易记录失败:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [propTrades])

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center text-muted-foreground">加载中...</div>
        </CardContent>
      </Card>
    )
  }

  // 按股票统计盈亏
  const stockPnlMap = new Map<string, { symbol: string; name: string; pnl: number; trades: number }>()
  
  trades.forEach(trade => {
    if (trade.pnl !== 0) {
      const existing = stockPnlMap.get(trade.symbol) || { 
        symbol: trade.symbol, 
        name: trade.name, 
        pnl: 0, 
        trades: 0 
      }
      existing.pnl += trade.pnl
      existing.trades += 1
      stockPnlMap.set(trade.symbol, existing)
    }
  })

  const stockPnlData = Array.from(stockPnlMap.values())
    .sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl))
    .slice(0, 8) // 最多显示8只股票

  // 计算总盈亏
  const totalPnl = trades.reduce((sum, t) => sum + (t.pnl || 0), 0)
  const profitTotal = trades.filter(t => t.pnl > 0).reduce((sum, t) => sum + t.pnl, 0)
  const lossTotal = trades.filter(t => t.pnl < 0).reduce((sum, t) => sum + t.pnl, 0)

  // 计算盈亏占比
  const profitPct = totalEquity > 0 ? (profitTotal / totalEquity) * 100 : 0
  const lossPct = totalEquity > 0 ? (lossTotal / totalEquity) * 100 : 0
  const netPct = totalEquity > 0 ? (totalPnl / totalEquity) * 100 : 0

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5" />
          盈亏对总资产影响占比
        </CardTitle>
        <CardDescription>
          各股票盈亏占总资产的百分比（红色盈利，绿色亏损）
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* 总览数据 */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="p-3 bg-red-50 dark:bg-red-950/30 rounded-lg">
            <div className="text-xs text-muted-foreground mb-1">总盈利</div>
            <div className="text-lg font-bold text-red-600">
              +¥{profitTotal.toLocaleString()}
            </div>
            <div className="text-xs text-red-600">+{profitPct.toFixed(2)}%</div>
          </div>
          <div className="p-3 bg-green-50 dark:bg-green-950/30 rounded-lg">
            <div className="text-xs text-muted-foreground mb-1">总亏损</div>
            <div className="text-lg font-bold text-green-600">
              ¥{lossTotal.toLocaleString()}
            </div>
            <div className="text-xs text-green-600">{lossPct.toFixed(2)}%</div>
          </div>
          <div className={`p-3 rounded-lg ${netPct >= 0 ? 'bg-red-50 dark:bg-red-950/30' : 'bg-green-50 dark:bg-green-950/30'}`}>
            <div className="text-xs text-muted-foreground mb-1">净盈亏</div>
            <div className={`text-lg font-bold ${netPct >= 0 ? 'text-red-600' : 'text-green-600'}`}>
              {netPct >= 0 ? '+' : ''}¥{totalPnl.toLocaleString()}
            </div>
            <div className={`text-xs ${netPct >= 0 ? 'text-red-600' : 'text-green-600'}`}>
              {netPct >= 0 ? '+' : ''}{netPct.toFixed(2)}%
            </div>
          </div>
        </div>

        {/* 柱状图 */}
        {stockPnlData.length > 0 && (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={stockPnlData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis 
                type="number" 
                className="text-xs"
                tickFormatter={(v) => `${(v / totalEquity * 100).toFixed(1)}%`}
              />
              <YAxis 
                type="category" 
                dataKey="symbol" 
                className="text-xs"
                width={60}
              />
              <Tooltip
                formatter={(value, name, props: any) => {
                  const pct = ((value as number) / totalEquity) * 100
                  return [
                    <>
                      <div>¥{(value as number).toLocaleString()}</div>
                      <div className="text-xs">{pct.toFixed(2)}% 占总资产</div>
                    </>,
                    props.payload.name
                  ]
                }}
                contentStyle={{
                  backgroundColor: 'hsl(var(--popover))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                }}
              />
              <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
                {stockPnlData.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={entry.pnl >= 0 ? '#ef4444' : '#22c55e'} 
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}

        {/* 说明 */}
        <div className="mt-4 pt-4 border-t text-xs text-muted-foreground">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 bg-red-500 rounded" />
              <span>盈利（红色）</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 bg-green-500 rounded" />
              <span>亏损（绿色）</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
