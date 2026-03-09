/**
 * MT_Alpha API 客户端
 *
 * 模块划分：
 * 1. 类型定义 - 所有接口类型统一定义
 * 2. API客户端 - 按功能模块组织接口方法
 */

import { LedgerStatus, PortfolioData, Trade, UniversePoolItem } from '@/types'

// ============================================================================
//                              类型定义区
// ============================================================================

// -----------------------------------
//         策略相关类型
// -----------------------------------

/** 策略配置 */
export interface StrategyConfig {
  /** 硬止损比例 */
  stop_loss_pct: number
  /** 移动止盈比例 */
  trailing_stop_pct: number
  /** 短期均线周期 */
  ma_short: number
  /** 中期均线周期 */
  ma_mid: number
  /** 长期均线周期 */
  ma_long: number
  /** 首次建仓偏离限制 */
  bias_entry_limit: number
  /** 加仓最低浮盈 */
  add_pos_min_profit: number
  /** 单票最大仓位比例 */
  max_position_pct: number
}

/** 策略运行状态 */
export interface StrategyStatus {
  /** 是否运行中 */
  is_running: boolean
  /** 启动时间 */
  started_at: string | null
  /** 最后信号时间 */
  last_signal_time: string | null
  /** 总交易次数 */
  total_trades: number
  /** 今日交易次数 */
  today_trades: number
}

// -----------------------------------
//         回测相关类型
// -----------------------------------

/** 回测参数 */
export interface BacktestParams {
  /** 开始日期 */
  start_date: string
  /** 结束日期 */
  end_date: string
  /** 初始资金 */
  initial_capital: number
}

/** 回测结果 */
export interface BacktestResult {
  /** 总收益率 */
  total_return: number
  /** 年化收益率 */
  annualized_return: number
  /** 最大回撤 */
  max_drawdown: number
  /** 夏普比率 */
  sharpe_ratio: number
  /** 卡玛比率 */
  calmar_ratio: number
  /** 胜率 */
  win_rate: number
  /** 总交易次数 */
  total_trades: number
  /** 盈利次数 */
  profit_trades: number
  /** 亏损次数 */
  loss_trades: number
  /** 平均盈利 */
  avg_profit: number
  /** 平均亏损 */
  avg_loss: number
  /** 盈亏比 */
  profit_factor: number
  /** 权益曲线 */
  equity_curve: { date: string; equity: number; benchmark: number }[]
  /** 月度收益 */
  monthly_returns: { month: string; return: number }[]
}

// -----------------------------------
//         风控相关类型
// -----------------------------------

/** 风控指标 */
export interface RiskMetrics {
  /** 仓位使用率 */
  position_usage: number
  /** 最大敞口 */
  max_exposure: number
  /** 日亏损限额 */
  daily_pnl_limit: number
  /** 当前回撤 */
  current_drawdown: number
  /** 风险等级 */
  risk_level: 'low' | 'medium' | 'high'
}

// -----------------------------------
//         行情相关类型
// -----------------------------------

/** 实时行情 */
export interface Quote {
  /** 股票代码 */
  symbol: string
  /** 股票名称 */
  name: string
  /** 当前价格 */
  price: number
  /** 涨跌额 */
  change: number
  /** 涨跌幅 */
  change_pct: number
  /** 成交量 */
  volume: number
  /** 成交额 */
  turnover: number
  /** 最高价 */
  high: number
  /** 最低价 */
  low: number
  /** 开盘价 */
  open: number
  /** 昨收价 */
  prev_close: number
  /** 时间戳 */
  timestamp: string
}

/** K线数据 */
export interface KlineData {
  /** 日期 */
  date: string
  /** 开盘价 */
  open: number
  /** 最高价 */
  high: number
  /** 最低价 */
  low: number
  /** 收盘价 */
  close: number
  /** 成交量 */
  volume: number
}

// -----------------------------------
//         日志相关类型
// -----------------------------------

/** 日志条目 */
export interface LogEntry {
  /** 时间 */
  time: string
  /** 日志级别 */
  level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG'
  /** 模块名 */
  module: string
  /** 消息内容 */
  message: string
}

// -----------------------------------
//         订单相关类型
// -----------------------------------

/** 创建订单参数 */
export interface CreateOrderParams {
  /** 股票代码 */
  symbol: string
  /** 交易方向 */
  action: 'BUY' | 'SELL'
  /** 数量 */
  shares: number
  /** 价格（可选，不填为市价单） */
  price?: number
  /** 交易原因 */
  reason?: string
}

// ============================================================================
//                              API 客户端
// ============================================================================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  // -----------------------------------
  //         核心请求方法
  // -----------------------------------

  /**
   * 通用请求方法
   * @param endpoint 接口路径
   * @param options 请求选项
   * @returns 响应数据或null
   */
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T | null> {
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      })

      if (!response.ok) {
        if (process.env.NODE_ENV === 'development') {
          console.warn(`API ${endpoint} returned ${response.status}`)
        }
        return null
      }

      return await response.json()
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.warn(`API ${endpoint} request failed:`, error)
      }
      return null
    }
  }

  // ============================================================================
  //                              账本模块
  // ============================================================================

  /**
   * 获取账本状态
   */
  async getLedgerStatus(): Promise<LedgerStatus | null> {
    return this.request<LedgerStatus>('/api/v1/ledger/status')
  }

  /**
   * 获取持仓资产
   */
  async getPortfolioAssets(): Promise<PortfolioData | null> {
    return this.request<PortfolioData>('/api/v1/ledger/assets')
  }

  /**
   * 获取净值历史
   */
  async getNavHistory(): Promise<{ date: string; equity: number }[] | null> {
    return this.request<{ date: string; equity: number }[]>('/api/v1/ledger/nav_history')
  }

  /**
   * 手动同步账本
   */
  async syncLedger(): Promise<{ status: string; message: string } | null> {
    return this.request('/api/v1/ledger/manual_sync', { method: 'POST' })
  }

  // ============================================================================
  //                              订单模块
  // ============================================================================

  /**
   * 获取今日成交
   * @param limit 返回条数限制
   */
  async getTrades(limit: number = 50): Promise<Trade[] | null> {
    return this.request<Trade[]>(`/api/v1/orders/today?limit=${limit}`)
  }

  /**
   * 获取待成交订单
   */
  async getPendingOrders(): Promise<Trade[] | null> {
    return this.request<Trade[]>('/api/v1/orders/pending')
  }

  /**
   * 创建订单
   * @param order 订单参数
   */
  async createOrder(order: CreateOrderParams): Promise<{ status: string; order_id: string } | null> {
    return this.request('/api/v1/orders/create', {
      method: 'POST',
      body: JSON.stringify(order),
    })
  }

  /**
   * 撤销订单
   * @param orderId 订单ID
   */
  async cancelOrder(orderId: string): Promise<{ status: string } | null> {
    return this.request(`/api/v1/orders/cancel/${orderId}`, { method: 'POST' })
  }

  // ============================================================================
  //                              股票池模块
  // ============================================================================

  /**
   * 获取股票池
   */
  async getUniversePool(): Promise<UniversePoolItem[] | null> {
    return this.request<UniversePoolItem[]>('/api/v1/universe/pool')
  }

  // ============================================================================
  //                              策略模块
  // ============================================================================

  /**
   * 获取策略配置
   */
  async getStrategyConfig(): Promise<StrategyConfig | null> {
    return this.request<StrategyConfig>('/api/v1/strategy/config')
  }

  /**
   * 保存策略配置
   * @param config 策略配置
   */
  async saveStrategyConfig(config: StrategyConfig): Promise<{ status: string } | null> {
    return this.request('/api/v1/strategy/config', {
      method: 'POST',
      body: JSON.stringify(config),
    })
  }

  /**
   * 获取策略状态
   */
  async getStrategyStatus(): Promise<StrategyStatus | null> {
    return this.request<StrategyStatus>('/api/v1/strategy/status')
  }

  /**
   * 启动策略
   */
  async startStrategy(): Promise<{ status: string } | null> {
    return this.request('/api/v1/strategy/start', { method: 'POST' })
  }

  /**
   * 停止策略
   */
  async stopStrategy(): Promise<{ status: string } | null> {
    return this.request('/api/v1/strategy/stop', { method: 'POST' })
  }

  // ============================================================================
  //                              回测模块
  // ============================================================================

  /**
   * 运行回测
   * @param params 回测参数
   */
  async runBacktest(params: BacktestParams): Promise<{ backtest_id: string } | null> {
    return this.request('/api/v1/backtest/run', {
      method: 'POST',
      body: JSON.stringify(params),
    })
  }

  /**
   * 获取回测结果
   * @param backtestId 回测ID
   */
  async getBacktestResult(backtestId: string): Promise<BacktestResult | null> {
    return this.request<BacktestResult>(`/api/v1/backtest/result/${backtestId}`)
  }

  /**
   * 获取回测历史列表
   */
  async getBacktestHistory(): Promise<{ id: string; date: string; return: number }[] | null> {
    return this.request('/api/v1/backtest/history')
  }

  // ============================================================================
  //                              引擎模块
  // ============================================================================

  /**
   * 手动触发引擎运行一次
   */
  async runEngine(): Promise<{ status: string } | null> {
    return this.request('/api/v1/engine/run_once', { method: 'POST' })
  }

  // ============================================================================
  //                              行情模块
  // ============================================================================

  /**
   * 获取实时行情
   * @param symbol 股票代码
   */
  async getQuote(symbol: string): Promise<Quote | null> {
    return this.request<Quote>(`/api/v1/quote/realtime/${symbol}`)
  }

  /**
   * 获取K线数据
   * @param symbol 股票代码
   * @param period 周期 (daily, weekly, monthly)
   */
  async getKline(symbol: string, period: string = 'daily'): Promise<KlineData[] | null> {
    return this.request(`/api/v1/quote/kline/${symbol}?period=${period}`)
  }

  // ============================================================================
  //                              风控模块
  // ============================================================================

  /**
   * 获取风控指标
   */
  async getRiskMetrics(): Promise<RiskMetrics | null> {
    return this.request<RiskMetrics>('/api/v1/risk/metrics')
  }

  // ============================================================================
  //                              日志模块
  // ============================================================================

  /**
   * 获取交易日志
   * @param limit 返回条数限制
   */
  async getTradeLogs(limit: number = 100): Promise<LogEntry[] | null> {
    return this.request<LogEntry[]>(`/api/v1/logs/trade?limit=${limit}`)
  }

  // ============================================================================
  //                              回测扩展模块
  // ============================================================================

  /**
   * 获取资产曲线
   * @param strategyId 策略ID（可选）
   */
  async getEquityCurve(strategyId?: string): Promise<{ date: string; equity: number; benchmark: number }[] | null> {
    const endpoint = strategyId
      ? `/api/v1/backtest/equity_curve?strategy_id=${strategyId}`
      : '/api/v1/backtest/equity_curve'
    return this.request(endpoint)
  }

  /**
   * 获取回撤曲线
   * @param strategyId 策略ID（可选）
   */
  async getDrawdown(strategyId?: string): Promise<{ date: string; drawdown: number; equity: number; peak: number }[] | null> {
    const endpoint = strategyId
      ? `/api/v1/backtest/drawdown?strategy_id=${strategyId}`
      : '/api/v1/backtest/drawdown'
    return this.request(endpoint)
  }

  /**
   * 获取回测股票列表
   */
  async getBacktestStocks(): Promise<{ symbol: string; name: string; return_pct: number; trades: number }[] | null> {
    return this.request('/api/v1/backtest/backtest_stocks')
  }

  /**
   * 获取K线信号数据
   * @param symbol 股票代码
   */
  async getKlineSignals(symbol: string): Promise<{
    symbol: string
    name: string
    kline: {
      date: string
      open: number
      high: number
      low: number
      close: number
      ma5: number
      ma20: number
    }[]
    signals: {
      date: string
      symbol: string
      name: string
      action: 'BUY' | 'SELL'
      shares: number
      price: number
      pnl: number
      reason: string
      status: string
    }[]
  } | null> {
    return this.request(`/api/v1/backtest/kline_signals?symbol=${symbol}`)
  }

  /**
   * 获取回测交易记录
   */
  async getBacktestTrades(): Promise<{
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
  }[] | null> {
    return this.request('/api/v1/backtest/trades')
  }

  /**
   * 获取参数敏感度分析
   * @param params 参数配置
   */
  async getParamSensitivity(params?: {
    stop_loss_range?: number[]
    trailing_stop_range?: number[]
  }): Promise<{
    heatmap: { stop_loss: number; trailing_stop: number; return: number }[]
    best_params: { stop_loss: number; trailing_stop: number; return: number }
  } | null> {
    const queryParams = params
      ? `?stop_loss_range=${params.stop_loss_range?.join(',')}&trailing_stop_range=${params.trailing_stop_range?.join(',')}`
      : ''
    return this.request(`/api/v1/backtest/param_sensitivity${queryParams}`)
  }

  /**
   * 获取风险归因分析
   */
  async getRiskAttribution(): Promise<{
    factors: { name: string; contribution: number; weight: number }[]
    total_risk: number
    residual_risk: number
  } | null> {
    return this.request('/api/v1/backtest/risk_attribution')
  }
}

// 导出单例实例
export const apiClient = new ApiClient()
