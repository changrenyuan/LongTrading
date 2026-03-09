'use client'

import { useState, useEffect } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'
import { Fragment } from 'react'
import { apiClient } from '@/lib/api'

interface Trade {
  id: string
  date: string
  symbol: string
  name: string
  action: 'BUY' | 'SELL'
  shares: number
  price: number
  amount: number
  reason: string
  pnl: number
  pnl_pct: number
  holding_days: number
  signal_type: string
}

interface TradeLogTableProps {
  title?: string
}

export function TradeLogTable({ title = '交易记录' }: TradeLogTableProps) {
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)
  const [sortField, setSortField] = useState<keyof Trade>('date')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    const fetchTrades = async () => {
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
    fetchTrades()
  }, [])

  const handleSort = (field: keyof Trade) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortOrder('desc')
    }
  }

  const sortedTrades = [...trades].sort((a, b) => {
    const aValue = a[sortField]
    const bValue = b[sortField]
    if (typeof aValue === 'number' && typeof bValue === 'number') {
      return sortOrder === 'asc' ? aValue - bValue : bValue - aValue
    }
    if (typeof aValue === 'string' && typeof bValue === 'string') {
      return sortOrder === 'asc' 
        ? aValue.localeCompare(bValue) 
        : bValue.localeCompare(aValue)
    }
    return 0
  })

  if (loading) {
    return <div className="text-center py-8 text-muted-foreground">加载中...</div>
  }

  return (
    <div className="space-y-4">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[100px]">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('date')}
                  className="h-auto p-0 font-medium"
                >
                  日期
                  {sortField === 'date' && (
                    sortOrder === 'asc' ? <ChevronUp className="ml-1 h-3 w-3" /> : <ChevronDown className="ml-1 h-3 w-3" />
                  )}
                </Button>
              </TableHead>
              <TableHead>股票</TableHead>
              <TableHead className="w-[60px]">操作</TableHead>
              <TableHead className="text-right">数量</TableHead>
              <TableHead className="text-right">价格</TableHead>
              <TableHead className="text-right">金额</TableHead>
              <TableHead className="text-right">盈亏</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedTrades.map((trade) => {
              const shares = trade.shares ?? 0
              const price = trade.price ?? 0
              const amount = trade.amount ?? (shares * price)
              const pnl = trade.pnl ?? 0
              const pnlPct = trade.pnl_pct ?? 0
              const holdingDays = trade.holding_days ?? 0

              return (
                <Fragment key={trade.id}>
                  <TableRow
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => setExpandedId(expandedId === trade.id ? null : trade.id)}
                  >
                    <TableCell className="text-xs">{trade.date}</TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-medium">{trade.symbol}</span>
                        <span className="text-xs text-muted-foreground">{trade.name}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={trade.action === 'BUY' ? 'default' : 'destructive'}
                        className="text-xs"
                      >
                        {trade.action === 'BUY' ? '买入' : '卖出'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">{shares.toLocaleString()}</TableCell>
                    <TableCell className="text-right">¥{price.toFixed(2)}</TableCell>
                    <TableCell className="text-right">
                      ¥{amount.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      {pnl > 0 ? (
                        <span className="text-green-600 font-medium">
                          +¥{pnl.toLocaleString()}
                          <br />
                          <span className="text-xs">(+{pnlPct.toFixed(1)}%)</span>
                        </span>
                      ) : pnl < 0 ? (
                        <span className="text-red-600 font-medium">
                          ¥{pnl.toLocaleString()}
                          <br />
                          <span className="text-xs">({pnlPct.toFixed(1)}%)</span>
                        </span>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {expandedId === trade.id ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </TableCell>
                  </TableRow>
                  {expandedId === trade.id && (
                    <TableRow className="bg-muted/30">
                      <TableCell colSpan={8} className="p-4">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                          <div>
                            <span className="text-muted-foreground">信号类型:</span>
                            <Badge variant="outline" className="ml-2">{trade.signal_type || '-'}</Badge>
                          </div>
                          <div>
                            <span className="text-muted-foreground">持仓天数:</span>
                            <span className="ml-2 font-medium">{holdingDays} 天</span>
                          </div>
                          <div className="col-span-2">
                            <span className="text-muted-foreground">交易原因:</span>
                            <span className="ml-2">{trade.reason || '-'}</span>
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
