'use client'

import { useEffect, useState } from 'react'
import { DashboardSidebar } from '@/components/layout/DashboardSidebar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { apiClient } from '@/lib/api'
import { Trade } from '@/types'
import { RefreshCw, ArrowUpRight, ArrowDownRight } from 'lucide-react'

export default function TradesPage() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    setLoading(true)
    try {
      const data = await apiClient.getTrades(100)
      setTrades(data || [])
    } catch (error) {
      console.error('Failed to fetch trades:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  const getActionColor = (action: string) => {
    switch (action.toUpperCase()) {
      case 'BUY':
        return 'success'
      case 'SELL':
        return 'destructive'
      default:
        return 'default'
    }
  }

  const getStatusColor = (status: string) => {
    if (status.includes('成功') || status.includes('完成')) return 'success'
    if (status.includes('失败') || status.includes('错误')) return 'destructive'
    return 'warning'
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-background">
      <DashboardSidebar />

      <main className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold">交易记录</h1>
              <p className="text-muted-foreground">查看策略执行流水与交易历史</p>
            </div>
            <Button onClick={fetchData} variant="outline">
              <RefreshCw className="mr-2 h-4 w-4" />
              刷新数据
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>交易流水</CardTitle>
            </CardHeader>
            <CardContent>
              {trades.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left p-3 font-medium">日期</th>
                        <th className="text-left p-3 font-medium">代码</th>
                        <th className="text-left p-3 font-medium">名称</th>
                        <th className="text-left p-3 font-medium">操作</th>
                        <th className="text-right p-3 font-medium">数量</th>
                        <th className="text-right p-3 font-medium">价格</th>
                        <th className="text-left p-3 font-medium">逻辑</th>
                        <th className="text-left p-3 font-medium">状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trades.map((trade, index) => {
                        const price = Number(trade.Price) || 0

                        return (
                          <tr key={index} className="border-b hover:bg-muted/50">
                            <td className="p-3 text-sm">{trade.Date}</td>
                            <td className="p-3 font-medium">{trade.Symbol}</td>
                            <td className="p-3 text-sm">{trade.Name}</td>
                            <td className="p-3">
                              <Badge variant={getActionColor(trade.Action)}>
                                {trade.Action.toUpperCase() === 'BUY' ? (
                                  <ArrowDownRight className="mr-1 h-3 w-3 inline" />
                                ) : (
                                  <ArrowUpRight className="mr-1 h-3 w-3 inline" />
                                )}
                                {trade.Action.toUpperCase()}
                              </Badge>
                            </td>
                            <td className="p-3 text-right font-medium">{trade.Shares.toLocaleString()}</td>
                            <td className="p-3 text-right">¥{price.toFixed(2)}</td>
                            <td className="p-3 text-sm text-muted-foreground max-w-xs truncate" title={trade.Reason}>
                              {trade.Reason}
                            </td>
                            <td className="p-3">
                              <Badge variant={getStatusColor(trade.Status)}>
                                {trade.Status}
                              </Badge>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-16 text-muted-foreground">
                  <p>暂无交易记录</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  )
}
