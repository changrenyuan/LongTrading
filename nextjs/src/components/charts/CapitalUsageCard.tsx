'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Wallet, TrendingUp, TrendingDown } from 'lucide-react'
import { apiClient } from '@/lib/api'

interface CapitalUsageCardProps {
  positions?: any[]
  totalEquity?: number
  availableCash?: number
}

export function CapitalUsageCard({ 
  positions: propPositions, 
  totalEquity = 1000000,
  availableCash: propAvailableCash 
}: CapitalUsageCardProps) {
  const [positions, setPositions] = useState<any[]>(propPositions || [])
  const [availableCash, setAvailableCash] = useState(propAvailableCash || 0)
  const [loading, setLoading] = useState(!propPositions)

  useEffect(() => {
    if (propPositions && propAvailableCash !== undefined) {
      setPositions(propPositions)
      setAvailableCash(propAvailableCash)
      return
    }
    
    const fetchData = async () => {
      try {
        const data = await apiClient.getPortfolioAssets()
        if (data) {
          setPositions(data.positions || [])
          setAvailableCash(data.available_cash || 0)
        }
      } catch (error) {
        console.error('获取持仓数据失败:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [propPositions, propAvailableCash])

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center text-muted-foreground">加载中...</div>
        </CardContent>
      </Card>
    )
  }

  // 计算各股票资金占用
  const stockCapitalMap = new Map<string, { 
    symbol: string; 
    name: string; 
    marketValue: number;
    pnl: number;
    pnlPct: number;
  }>()
  
  positions.forEach((pos: any) => {
    const marketValue = (Number(pos.current_price) || 0) * (Number(pos.shares) || 0)
    const pnl = Number(pos.pnl) || 0
    stockCapitalMap.set(pos.symbol, {
      symbol: pos.symbol,
      name: pos.name || pos.symbol,
      marketValue,
      pnl,
      pnlPct: Number(pos.pnl_pct) || 0,
    })
  })

  const stockCapitalData = Array.from(stockCapitalMap.values())
    .sort((a, b) => b.marketValue - a.marketValue)

  // 计算总持仓市值
  const totalMarketValue = stockCapitalData.reduce((sum, s) => sum + s.marketValue, 0)
  const usedPct = totalEquity > 0 ? (totalMarketValue / totalEquity) * 100 : 0
  const cashPct = totalEquity > 0 ? (availableCash / totalEquity) * 100 : 0

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wallet className="h-5 w-5 text-primary" />
          资金使用占比
        </CardTitle>
        <CardDescription>
          各股票占用资金占总资产的比例
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* 总览 */}
        <div className="space-y-4 mb-4">
          {/* 资金使用进度条 */}
          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="text-muted-foreground">资金使用率</span>
              <span className="font-bold">{usedPct.toFixed(1)}%</span>
            </div>
            <Progress value={usedPct} className="h-3" />
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>持仓: ¥{totalMarketValue.toLocaleString()}</span>
              <span>现金: ¥{availableCash.toLocaleString()}</span>
            </div>
          </div>

          {/* 资金分布 */}
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-primary/10 rounded-lg">
              <div className="text-xs text-muted-foreground mb-1">已使用资金</div>
              <div className="text-lg font-bold text-primary">
                ¥{totalMarketValue.toLocaleString()}
              </div>
              <div className="text-xs text-primary">{usedPct.toFixed(1)}%</div>
            </div>
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-xs text-muted-foreground mb-1">可用现金</div>
              <div className="text-lg font-bold">
                ¥{availableCash.toLocaleString()}
              </div>
              <div className="text-xs text-muted-foreground">{cashPct.toFixed(1)}%</div>
            </div>
          </div>
        </div>

        {/* 各股票资金占比 */}
        {stockCapitalData.length > 0 && (
          <div className="space-y-3">
            <div className="text-sm font-medium text-muted-foreground">个股资金占比</div>
            {stockCapitalData.map((stock) => {
              const capitalPct = (stock.marketValue / totalEquity) * 100
              return (
                <div key={stock.symbol} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{stock.symbol}</span>
                      <span className="text-xs text-muted-foreground">{stock.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">
                        ¥{stock.marketValue.toLocaleString()}
                      </span>
                      <span className={`text-xs ${stock.pnl >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {stock.pnl >= 0 ? '+' : ''}{stock.pnlPct.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <Progress 
                    value={Math.min(capitalPct, 100)} 
                    className="h-2"
                  />
                  <div className="text-xs text-muted-foreground text-right">
                    {capitalPct.toFixed(1)}% 占总资产
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {stockCapitalData.length === 0 && (
          <div className="text-center py-8 text-muted-foreground">
            当前空仓
          </div>
        )}
      </CardContent>
    </Card>
  )
}
