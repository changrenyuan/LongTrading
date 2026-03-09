'use client'

import { useEffect, useState } from 'react'
import { DashboardSidebar } from '@/components/layout/DashboardSidebar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AssetCurveChart } from '@/components/charts/AssetCurveChart'
import { apiClient } from '@/lib/api'
import { PortfolioData, LedgerStatus } from '@/types'
import { TrendingUp, DollarSign, Wallet, Target, Activity, RefreshCw, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'

interface NavHistoryItem {
  date: string
  equity: number
}

type SortField = 'symbol' | 'shares' | 'cost_price' | 'current_price' | 'pnl' | 'pnl_pct' | 'market_value'
type SortDirection = 'asc' | 'desc'

export default function DashboardPage() {
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null)
  const [ledgerStatus, setLedgerStatus] = useState<LedgerStatus | null>(null)
  const [navHistory, setNavHistory] = useState<NavHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [engineRunning, setEngineRunning] = useState(false)
  const [sortField, setSortField] = useState<SortField>('pnl_pct')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

  const fetchData = async () => {
    setLoading(true)
    try {
      const [portfolioData, statusData, navData] = await Promise.all([
        apiClient.getPortfolioAssets(),
        apiClient.getLedgerStatus(),
        apiClient.getNavHistory(),
      ])
      setPortfolio(portfolioData)
      setLedgerStatus(statusData)
      setNavHistory(navData || [])
    } catch (error) {
      console.error('Failed to fetch data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRunEngine = async () => {
    setEngineRunning(true)
    const result = await apiClient.runEngine()
    if (result) {
      await fetchData()
    }
    setEngineRunning(false)
  }

  const handleSyncLedger = async () => {
    const result = await apiClient.syncLedger()
    if (result) {
      await fetchData()
    }
  }

  useEffect(() => {
    fetchData()
    // 每30秒自动刷新数据
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  // 排序处理函数
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('desc') // 默认降序
    }
  }

  // 排序后的持仓列表
  const sortedPositions = portfolio?.positions ? [...portfolio.positions].sort((a, b) => {
    let aValue: number, bValue: number

    switch (sortField) {
      case 'symbol':
        return sortDirection === 'asc'
          ? a.symbol.localeCompare(b.symbol)
          : b.symbol.localeCompare(a.symbol)
      case 'shares':
        aValue = Number(a.shares) || 0
        bValue = Number(b.shares) || 0
        break
      case 'cost_price':
        aValue = Number(a.cost_price) || 0
        bValue = Number(b.cost_price) || 0
        break
      case 'current_price':
        aValue = Number(a.current_price) || 0
        bValue = Number(b.current_price) || 0
        break
      case 'pnl':
        aValue = Number(a.pnl) || 0
        bValue = Number(b.pnl) || 0
        break
      case 'pnl_pct':
        aValue = Number(a.pnl_pct) || 0
        bValue = Number(b.pnl_pct) || 0
        break
      case 'market_value':
        aValue = (Number(a.current_price) || 0) * (Number(a.shares) || 0)
        bValue = (Number(b.current_price) || 0) * (Number(b.shares) || 0)
        break
      default:
        return 0
    }

    return sortDirection === 'asc' ? aValue - bValue : bValue - aValue
  }) : []

  // 排序按钮组件
  const SortButton = ({ field, label }: { field: SortField; label: string }) => (
    <button
      onClick={() => handleSort(field)}
      className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
    >
      {label}
      {sortField === field ? (
        sortDirection === 'asc'
          ? <ArrowUp className="h-3 w-3" />
          : <ArrowDown className="h-3 w-3" />
      ) : (
        <ArrowUpDown className="h-3 w-3 opacity-50" />
      )}
    </button>
  )

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  const totalEquity = portfolio
    ? portfolio.available_cash + portfolio.positions.reduce((sum, p) => sum + (p.shares * (Number(p.current_price) || 0)), 0)
    : 0
  const totalCost = portfolio
    ? portfolio.positions.reduce((sum, p) => sum + (p.shares * (Number(p.cost_price) || 0)), 0)
    : 0
  const totalMarketValue = totalEquity - portfolio?.available_cash!
  const exposure = totalEquity > 0 ? (totalMarketValue / totalEquity) * 100 : 0

  return (
    <div className="flex h-screen bg-background">
      <DashboardSidebar />

      <main className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-6">
          {/* 页面标题和操作按钮 */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold">MT_Alpha 量化指挥中心</h1>
              <p className="text-muted-foreground">实时监控策略执行与资产状况</p>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={handleRunEngine}
                disabled={engineRunning}
                variant="default"
              >
                {engineRunning ? (
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Activity className="mr-2 h-4 w-4" />
                )}
                触发引擎
              </Button>
              <Button onClick={fetchData} variant="outline">
                <RefreshCw className="mr-2 h-4 w-4" />
                刷新数据
              </Button>
            </div>
          </div>

          {/* 对账状态提示 */}
          {ledgerStatus && !ledgerStatus.is_match && (
            <Alert variant="destructive">
              <AlertTitle>对账异常</AlertTitle>
              <AlertDescription className="flex items-center justify-between">
                {ledgerStatus.message}
                <Button size="sm" variant="outline" onClick={handleSyncLedger}>
                  强制同步
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {/* 资产总览卡片 */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">预估总净资产</CardTitle>
                <DollarSign className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-xl font-bold truncate" title={`¥${totalEquity.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`}>
                  ¥{totalEquity.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                </div>
                <p className="text-xs text-muted-foreground truncate">
                  总盈亏: ¥{portfolio?.metrics.total_pnl?.toFixed(2)}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">持仓盈亏</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className={`text-xl font-bold truncate ${(portfolio?.pnl_summary?.position_pnl ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {(portfolio?.pnl_summary?.position_pnl ?? 0) >= 0 ? '+' : ''}¥{(portfolio?.pnl_summary?.position_pnl ?? 0).toFixed(2)}
                </div>
                <p className="text-xs text-muted-foreground">未实现盈亏</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">当日盈亏</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className={`text-xl font-bold truncate ${(portfolio?.pnl_summary?.daily_pnl ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {(portfolio?.pnl_summary?.daily_pnl ?? 0) >= 0 ? '+' : ''}¥{(portfolio?.pnl_summary?.daily_pnl ?? 0).toFixed(2)}
                </div>
                <p className={`text-xs ${(portfolio?.pnl_summary?.daily_pnl ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {(portfolio?.pnl_summary?.daily_pnl ?? 0) >= 0 ? '+' : ''}{(portfolio?.pnl_summary?.daily_pnl_pct ?? 0).toFixed(2)}%
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">可用现金</CardTitle>
                <Wallet className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-xl font-bold truncate" title={`¥${portfolio?.available_cash.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`}>
                  ¥{portfolio?.available_cash.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                </div>
                <p className="text-xs text-muted-foreground">即时可用</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">仓位使用率</CardTitle>
                <Target className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-xl font-bold">{exposure.toFixed(1)}%</div>
                <p className="text-xs text-muted-foreground truncate" title={`持仓市值: ¥${totalMarketValue.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`}>
                  持仓市值: ¥{totalMarketValue.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">年化收益率</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-xl font-bold">
                  {portfolio?.metrics.annualized_return?.toFixed(2) ?? '0.00'}%
                </div>
                <Badge variant={(portfolio?.metrics.annualized_return ?? 0) > 0 ? 'success' : 'destructive'}>
                  {(portfolio?.metrics.annualized_return ?? 0) > 0 ? '盈利' : '亏损'}
                </Badge>
              </CardContent>
            </Card>
          </div>

          {/* 核心指标卡片 */}
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">夏普比率 (Sharpe)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{portfolio?.metrics.sharpe_ratio?.toFixed(2) ?? '0.00'}</div>
                <p className="text-xs text-muted-foreground">
                  {(portfolio?.metrics.sharpe_ratio ?? 0) > 1.5 ? '优秀' : (portfolio?.metrics.sharpe_ratio ?? 0) > 1 ? '良好' : '一般'}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">最大回撤 (Max DD)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{portfolio?.metrics.max_drawdown?.toFixed(2)}%</div>
                <p className="text-xs text-muted-foreground">风险指标</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">卡玛比率 (Calmar)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{portfolio?.metrics.calmar_ratio?.toFixed(2)}</div>
                <p className="text-xs text-muted-foreground">收益回撤比</p>
              </CardContent>
            </Card>
          </div>

          {/* 资产曲线图 */}
          <AssetCurveChart data={navHistory} />

          {/* 持仓概览 */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle>持仓概览</CardTitle>
              <span className="text-sm text-muted-foreground">
                共 {portfolio?.positions?.length || 0} 只股票
              </span>
            </CardHeader>
            <CardContent>
              {portfolio?.positions && portfolio.positions.length > 0 ? (
                <>
                  {/* 排序表头 */}
                  <div className="grid grid-cols-12 gap-4 items-center px-4 py-2 mb-2 bg-muted/50 rounded-lg text-sm font-medium">
                    <div className="col-span-3">
                      <SortButton field="symbol" label="股票" />
                    </div>
                    <div className="col-span-2 text-center">
                      <SortButton field="shares" label="持仓" />
                    </div>
                    <div className="col-span-1.5 text-center">
                      <SortButton field="cost_price" label="成本" />
                    </div>
                    <div className="col-span-1.5 text-center">
                      <SortButton field="current_price" label="现价" />
                    </div>
                    <div className="col-span-2 text-center">
                      <SortButton field="pnl_pct" label="盈亏比" />
                    </div>
                    <div className="col-span-2 text-center">
                      <SortButton field="market_value" label="市值" />
                    </div>
                  </div>

                  {/* 持仓列表 */}
                  <div className="space-y-3">
                    {sortedPositions.map((position) => {
                      const costPrice = Number(position.cost_price) || 0
                      const currentPrice = Number(position.current_price) || 0
                      const highestPrice = Number(position.highest_price) || currentPrice
                      const shares = Number(position.shares) || 0
                      const pnl = Number(position.pnl) || 0
                      const pnlPct = Number(position.pnl_pct) || 0

                      // 计算市值和成本
                      const marketValue = currentPrice * shares

                      // 计算从最高价回撤
                      const drawdownFromHigh = highestPrice > 0
                        ? ((currentPrice - highestPrice) / highestPrice) * 100
                        : 0

                      // 盈亏程度（用于颜色深浅）
                      const pnlIntensity = Math.min(Math.abs(pnlPct) / 10, 1)

                      return (
                        <div
                          key={position.symbol}
                          className="group relative overflow-hidden rounded-xl border bg-gradient-to-r from-card to-transparent p-4 hover:shadow-lg transition-all duration-300"
                        >
                          {/* 左侧盈亏指示条 */}
                          <div
                            className={`absolute left-0 top-0 bottom-0 w-1 ${
                              pnlPct >= 0 ? 'bg-green-500' : 'bg-red-500'
                            }`}
                            style={{ opacity: 0.4 + pnlIntensity * 0.6 }}
                          />

                          <div className="grid grid-cols-12 gap-4 items-center pl-2">
                            {/* 股票信息 */}
                            <div className="col-span-3">
                              <div className="flex items-center gap-2">
                                <div>
                                  <div className="font-bold text-lg">{position.symbol}</div>
                                  <div className="text-sm text-muted-foreground">{position.name || '-'}</div>
                                </div>
                              </div>
                              {position.buy_reason && (
                                <div className="mt-1 text-xs text-muted-foreground truncate max-w-[180px]" title={position.buy_reason}>
                                  {position.buy_reason}
                                </div>
                              )}
                            </div>

                            {/* 持仓数量 */}
                            <div className="col-span-2 text-center">
                              <div className="font-semibold">{shares.toLocaleString()} 股</div>
                            </div>

                            {/* 成本价 */}
                            <div className="col-span-1.5 text-center">
                              <div className="font-mono font-medium">¥{costPrice.toFixed(2)}</div>
                            </div>

                            {/* 现价 */}
                            <div className="col-span-1.5 text-center">
                              <div className={`font-mono font-bold ${pnlPct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                ¥{currentPrice.toFixed(2)}
                              </div>
                            </div>

                            {/* 盈亏进度条 */}
                            <div className="col-span-2">
                              <div className="flex items-center justify-between mb-1">
                                <span className={`font-bold ${pnlPct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                  {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                                </span>
                              </div>
                              <div className="h-2 bg-muted rounded-full overflow-hidden">
                                <div
                                  className={`h-full transition-all duration-500 ${
                                    pnlPct >= 0 ? 'bg-gradient-to-r from-green-400 to-green-600' : 'bg-gradient-to-r from-red-400 to-red-600'
                                  }`}
                                  style={{
                                    width: `${Math.min(Math.abs(pnlPct), 20) * 5}%`,
                                    marginLeft: pnlPct >= 0 ? '50%' : 'auto',
                                    marginRight: pnlPct < 0 ? '50%' : 'auto',
                                  }}
                                />
                              </div>
                            </div>

                            {/* 盈亏金额 & 市值 */}
                            <div className="col-span-2 text-right">
                              <div className={`text-lg font-bold ${pnlPct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {pnl >= 0 ? '+' : ''}¥{pnl.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                市值 ¥{marketValue.toLocaleString('zh-CN', { minimumFractionDigits: 0 })}
                              </div>
                              {highestPrice > currentPrice && (
                                <div className="text-xs text-amber-600 mt-0.5">
                                  回撤 {drawdownFromHigh.toFixed(1)}%
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <div className="text-4xl mb-2">📊</div>
                  <p>当前空仓</p>
                  <p className="text-sm mt-1">运行策略引擎后将自动建仓</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  )
}