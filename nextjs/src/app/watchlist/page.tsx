'use client'

import { useEffect, useState } from 'react'
import { DashboardSidebar } from '@/components/layout/DashboardSidebar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { apiClient } from '@/lib/api'
import { UniversePoolItem } from '@/types'
import { Star, TrendingUp, RefreshCw, ExternalLink } from 'lucide-react'

export default function WatchlistPage() {
  const [watchlist, setWatchlist] = useState<UniversePoolItem[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    setLoading(true)
    try {
      const data = await apiClient.getUniversePool()
      setWatchlist(data || [])
    } catch (error) {
      console.error('Failed to fetch watchlist:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const openStockPage = (symbol: string) => {
    // 打开东方财富股票页面
    window.open(`https://quote.eastmoney.com/${symbol}.html`, '_blank')
  }

  return (
    <div className="flex h-screen">
      <DashboardSidebar />
      <main className="flex-1 overflow-auto bg-background">
        <div className="container mx-auto p-6">
          {/* 页面标题 */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-3xl font-bold">关注列表</h1>
              <p className="text-muted-foreground mt-1">
                监控潜在交易机会的股票池
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchData}
              disabled={loading}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              刷新
            </Button>
          </div>

          {/* 统计卡片 */}
          <div className="grid gap-4 md:grid-cols-3 mb-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">关注股票数</CardTitle>
                <Star className="h-4 w-4 text-yellow-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{watchlist.length}</div>
                <p className="text-xs text-muted-foreground">当前监控中</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">沪深主板</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {watchlist.filter(item => item.symbol.startsWith('6') || item.symbol.startsWith('0')).length}
                </div>
                <p className="text-xs text-muted-foreground">主板股票</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">创业板/科创板</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {watchlist.filter(item => item.symbol.startsWith('3') || item.symbol.startsWith('688')).length}
                </div>
                <p className="text-xs text-muted-foreground">创新板股票</p>
              </CardContent>
            </Card>
          </div>

          {/* 股票列表 */}
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : watchlist.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center h-64">
                <Star className="h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground">暂无关注的股票</p>
                <p className="text-sm text-muted-foreground mt-1">
                  运行策略引擎后将自动添加候选股票
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {watchlist.map((item) => (
                <Card
                  key={item.symbol}
                  className="cursor-pointer hover:shadow-md transition-shadow"
                  onClick={() => openStockPage(item.symbol)}
                >
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                        <CardTitle className="text-lg">{item.name}</CardTitle>
                      </div>
                      <ExternalLink className="h-4 w-4 text-muted-foreground" />
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-2xl font-bold font-mono">{item.symbol}</span>
                      <Badge
                        variant={
                          item.symbol.startsWith('688') ? 'default' :
                          item.symbol.startsWith('3') ? 'secondary' :
                          'outline'
                        }
                      >
                        {item.symbol.startsWith('688') ? '科创板' :
                         item.symbol.startsWith('3') ? '创业板' :
                         item.symbol.startsWith('0') ? '深市' : '沪市'}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {item.reason}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
