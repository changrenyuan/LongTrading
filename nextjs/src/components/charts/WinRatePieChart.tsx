'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from 'recharts'
import { Target } from 'lucide-react'
import { apiClient } from '@/lib/api'

interface WinRatePieChartProps {
  trades?: any[]
}

export function WinRatePieChart({ trades: propTrades }: WinRatePieChartProps) {
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

  // 只统计已平仓的交易（有盈亏的交易）
  const closedTrades = trades.filter(t => t.pnl !== 0)
  const winTrades = closedTrades.filter(t => t.pnl > 0)
  const lossTrades = closedTrades.filter(t => t.pnl < 0)
  
  const winRate = closedTrades.length > 0 
    ? (winTrades.length / closedTrades.length) * 100 
    : 0

  const pieData = [
    { name: '盈利', value: winTrades.length, color: '#ef4444' },
    { name: '亏损', value: lossTrades.length, color: '#22c55e' },
  ]

  // 计算平均盈利和亏损
  const avgWin = winTrades.length > 0 
    ? winTrades.reduce((sum, t) => sum + t.pnl, 0) / winTrades.length 
    : 0
  const avgLoss = lossTrades.length > 0 
    ? Math.abs(lossTrades.reduce((sum, t) => sum + t.pnl, 0) / lossTrades.length) 
    : 0
  
  // 盈亏比
  const profitLossRatio = avgLoss > 0 ? avgWin / avgLoss : 0

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Target className="h-5 w-5 text-primary" />
          实际平仓胜率
        </CardTitle>
        <CardDescription>
          已平仓交易的胜负统计
        </CardDescription>
      </CardHeader>
      <CardContent>
        {closedTrades.length > 0 ? (
          <>
            {/* 胜率大数字 */}
            <div className="text-center mb-4">
              <div className="text-4xl font-bold text-primary">
                {winRate.toFixed(1)}%
              </div>
              <div className="text-sm text-muted-foreground">胜率</div>
            </div>

            {/* 饼图 */}
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip 
                  formatter={(value, name) => [`${value} 笔`, name]}
                />
              </PieChart>
            </ResponsiveContainer>

            {/* 图例 */}
            <div className="flex justify-center gap-6 mt-2">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-500 rounded" />
                <span className="text-sm">盈利 {winTrades.length} 笔</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded" />
                <span className="text-sm">亏损 {lossTrades.length} 笔</span>
              </div>
            </div>

            {/* 详细统计 */}
            <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t">
              <div className="text-center">
                <div className="text-xs text-muted-foreground">总平仓</div>
                <div className="text-lg font-bold">{closedTrades.length}</div>
                <div className="text-xs text-muted-foreground">笔</div>
              </div>
              <div className="text-center">
                <div className="text-xs text-muted-foreground">平均盈利</div>
                <div className="text-lg font-bold text-red-600">
                  +¥{avgWin.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-muted-foreground">平均亏损</div>
                <div className="text-lg font-bold text-green-600">
                  -¥{avgLoss.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </div>
              </div>
            </div>

            {/* 盈亏比 */}
            <div className="mt-4 p-3 bg-muted rounded-lg">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">盈亏比</span>
                <span className={`font-bold ${profitLossRatio >= 2 ? 'text-green-600' : profitLossRatio >= 1 ? 'text-yellow-600' : 'text-red-600'}`}>
                  {profitLossRatio.toFixed(2)}
                </span>
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {profitLossRatio >= 2 ? '优秀 (≥2)' : profitLossRatio >= 1 ? '良好 (1-2)' : '需改进 (<1)'}
              </div>
            </div>
          </>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            暂无已平仓交易
          </div>
        )}
      </CardContent>
    </Card>
  )
}
