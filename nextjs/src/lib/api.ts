import { LedgerStatus, PortfolioData, Trade, UniversePoolItem } from '@/types'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

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
        // 静默处理错误，返回 null 让调用方处理
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

  // 获取对账状态
  async getLedgerStatus(): Promise<LedgerStatus | null> {
    return this.request<LedgerStatus>('/api/v1/ledger/status')
  }

  // 获取资产数据
  async getPortfolioAssets(): Promise<PortfolioData | null> {
    return this.request<PortfolioData>('/api/v1/ledger/assets')
  }

  // 获取交易记录
  async getTrades(limit: number = 50): Promise<Trade[] | null> {
    return this.request<Trade[]>(`/api/v1/orders/today?limit=${limit}`)
  }

  // 获取股票池
  async getUniversePool(): Promise<UniversePoolItem[] | null> {
    return this.request<UniversePoolItem[]>('/api/v1/universe/pool')
  }

  // 手动同步账本
  async syncLedger(): Promise<{ status: string; message: string } | null> {
    return this.request('/api/v1/ledger/manual_sync', {
      method: 'POST',
    })
  }

  // 触发交易引擎运行一次
  async runEngine(): Promise<{ status: string } | null> {
    return this.request('/api/v1/engine/run-once', {
      method: 'POST',
    })
  }

  // 获取历史净值曲线数据
  async getNavHistory(): Promise<{ date: string; equity: number }[] | null> {
    return this.request<{ date: string; equity: number }[]>('/api/v1/ledger/nav_history')
  }
}

export const apiClient = new ApiClient()
