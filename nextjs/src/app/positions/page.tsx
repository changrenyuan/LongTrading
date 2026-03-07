'use client'

import { useEffect, useState } from 'react'
import { DashboardSidebar } from '@/components/layout/DashboardSidebar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { apiClient } from '@/lib/api'
import { PortfolioData } from '@/types'
import { TrendingUp, TrendingDown, RefreshCw } from 'lucide-react'

export default function PositionsPage() {
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    setLoading(true)
    try {
      const data = await apiClient.getPortfolioAssets()
      setPortfolio(data)
    } catch (error) {
      console.error('Failed to fetch positions:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

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
              <h1 className="text-3xl font-bold">持仓详情</h1>
              <p className="text-muted-foreground">实时监控持仓盈亏与风险</p>
            </div>
            <Button onClick={fetchData} variant="outline">
              <RefreshCw className="mr-2 h-4 w-4" />
              刷新数据
            </Button>
          </div>

          {portfolio?.positions && portfolio.positions.length > 0 ? (
            <div className="grid gap-4">
              {portfolio.positions.map((position) => {
                const currentPrice = Number(position.current_price) || 0
                const costPrice = Number(position.cost_price) || 0
                const marketValue = position.shares * currentPrice
                const costValue = position.shares * costPrice
                const pnl = position.pnl ? Number(position.pnl) : (marketValue - costValue)
                const pnlPct = position.pnl_pct ? Number(position.pnl_pct) : (costValue > 0 ? ((pnl / costValue) * 100) : 0)
                const highestPrice = Number(position.highest_price) || 0

                return (
                  <Card key={position.symbol}>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div>
                          <CardTitle className="flex items-center gap-2">
                            {position.name || position.symbol}
                            <Badge variant="outline">{position.symbol}</Badge>
                          </CardTitle>
                          <p className="text-sm text-muted-foreground mt-1">
                            {position.buy_date && `买入日期: ${position.buy_date}`}
                            {position.buy_reason && ` | ${position.buy_reason}`}
                          </p>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold">
                            ¥{currentPrice.toFixed(2)}
                          </div>
                          <Badge variant={pnlPct > 0 ? 'success' : 'destructive'}>
                            {pnlPct > 0 ? (
                              <TrendingUp className="mr-1 h-3 w-3 inline" />
                            ) : (
                              <TrendingDown className="mr-1 h-3 w-3 inline" />
                            )}
                            {pnlPct.toFixed(2)}%
                          </Badge>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div>
                          <p className="text-sm text-muted-foreground">持股数量</p>
                          <p className="text-lg font-semibold">{position.shares.toLocaleString()}</p>
                        </div>
                        <div>
                          <p className="text-sm text-muted-foreground">成本价格</p>
                          <p className="text-lg font-semibold">¥{costPrice.toFixed(2)}</p>
                        </div>
                        <div>
                          <p className="text-sm text-muted-foreground">市值</p>
                          <p className="text-lg font-semibold">¥{marketValue.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</p>
                        </div>
                        <div>
                          <p className="text-sm text-muted-foreground">盈亏金额</p>
                          <p className={`text-lg font-semibold ${pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {pnl >= 0 ? '+' : ''}¥{pnl.toFixed(2)}
                          </p>
                        </div>
                      </div>
                      {highestPrice > 0 && (
                        <div className="mt-4 p-3 bg-muted rounded-lg">
                          <p className="text-sm text-muted-foreground">
                            最高价 (防守线): ¥{highestPrice.toFixed(2)}
                          </p>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          ) : (
            <Card>
              <CardContent className="flex items-center justify-center py-16">
                <div className="text-center text-muted-foreground">
                  <TrendingUp className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg">当前空仓</p>
                  <p className="text-sm mt-2">等待策略信号...</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </main>
    </div>
  )
}
