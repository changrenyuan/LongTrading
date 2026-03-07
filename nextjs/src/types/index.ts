// API 响应类型定义
export interface LedgerStatus {
  is_match: boolean
  message: string
}

export interface Position {
  symbol: string
  name?: string
  shares: number
  cost_price: number
  current_price: number
  pnl?: number
  pnl_pct?: number
  highest_price?: number
  buy_date?: string
  buy_reason?: string
}

export interface PortfolioMetrics {
  total_pnl: number
  annualized_return: number
  sharpe_ratio: number
  max_drawdown: number
  calmar_ratio: number
}

export interface PnlSummary {
  position_pnl: number      // 持仓盈亏（未实现盈亏）
  daily_pnl: number          // 当日盈亏
  daily_pnl_pct: number      // 当日盈亏率
}

export interface PortfolioData {
  available_cash: number
  positions: Position[]
  metrics: PortfolioMetrics
  pnl_summary?: PnlSummary
}

export interface Trade {
  Date: string
  Symbol: string
  Name: string
  Action: string
  Shares: number
  Price: number
  Reason: string
  Status: string
}

export interface UniversePoolItem {
  symbol: string
  name: string
  reason: string
}
