'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { RefreshCw, Play } from 'lucide-react'
import { apiClient } from '@/lib/api'

interface ParameterHeatmapProps {
  title?: string
}

export function ParameterHeatmap({ title = '参数敏感度分析' }: ParameterHeatmapProps) {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const runParamSweep = async () => {
    setLoading(true)
    try {
      const result = await apiClient.getParamSensitivity({
        stop_loss_range: [5, 10, 15, 20],
        trailing_stop_range: [15, 20, 25, 30],
      })
      if (result && result.heatmap) {
        setData(result.heatmap)
      }
    } catch (error) {
      console.error('参数扫描失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // 自动运行一次
  useEffect(() => {
    runParamSweep()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">正在扫描参数...</span>
      </div>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 space-y-4">
        <p className="text-muted-foreground">暂无数据</p>
        <Button onClick={runParamSweep} size="sm">
          <Play className="h-4 w-4 mr-2" />
          运行参数扫描
        </Button>
      </div>
    )
  }

  // 获取参数范围
  const maShortValues = [...new Set(data.map(d => d.ma_short))].sort((a, b) => a - b)
  const maMidValues = [...new Set(data.map(d => d.ma_mid))].sort((a, b) => a - b)

  // 找到最佳参数
  const bestParams = data.reduce((best, current) => 
    current.sharpe > best.sharpe ? current : best
  )

  // 颜色映射函数 (绿-黄-红渐变)
  const getSharpeColor = (sharpe: number) => {
    const minSharpe = Math.min(...data.map(d => d.sharpe))
    const maxSharpe = Math.max(...data.map(d => d.sharpe))
    const ratio = (sharpe - minSharpe) / (maxSharpe - minSharpe)
    
    // 低值为红色，高值为绿色
    if (ratio < 0.5) {
      return `hsl(0, 70%, ${70 - ratio * 40}%)` // 红到黄
    } else {
      return `hsl(${120 * (ratio - 0.5) * 2}, 70%, ${50 + (1 - ratio) * 20}%)` // 黄到绿
    }
  }

  return (
    <div className="space-y-4">
      {/* 控制栏 */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          扫描 MA短周期 ({maShortValues[0]}-{maShortValues[maShortValues.length - 1]}) 
          × MA中周期 ({maMidValues[0]}-{maMidValues[maMidValues.length - 1]}) 共 {data.length} 种组合
        </div>
        <Button onClick={runParamSweep} size="sm" variant="outline" disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          重新扫描
        </Button>
      </div>

      {/* 热力图 */}
      <div className="overflow-x-auto">
        <div className="inline-block">
          {/* Y轴标签 */}
          <div className="flex">
            <div className="w-16" /> {/* 左上角空白 */}
            {/* X轴标签 */}
            <div className="flex">
              {maMidValues.map(maMid => (
                <div
                  key={maMid}
                  className="w-12 text-center text-xs text-muted-foreground"
                >
                  {maMid}
                </div>
              ))}
            </div>
          </div>

          {/* 数据行 */}
          {maShortValues.map(maShort => (
            <div key={maShort} className="flex items-center">
              {/* Y轴标签 */}
              <div className="w-16 h-12 flex items-center justify-end pr-2 text-xs text-muted-foreground">
                {maShort}
              </div>
              {/* 数据单元格 */}
              <div className="flex">
                {maMidValues.map(maMid => {
                  const cell = data.find(d => d.ma_short === maShort && d.ma_mid === maMid)
                  if (!cell) return <div key={maMid} className="w-12 h-12" />
                  
                  const isBest = cell.ma_short === bestParams.ma_short && cell.ma_mid === bestParams.ma_mid
                  
                  return (
                    <div
                      key={maMid}
                      className={`w-12 h-12 flex items-center justify-center text-xs font-medium cursor-pointer transition-all hover:scale-110 hover:z-10 ${
                        isBest ? 'ring-2 ring-primary ring-offset-2' : ''
                      }`}
                      style={{
                        backgroundColor: getSharpeColor(cell.sharpe),
                        color: cell.sharpe > 1.8 ? 'white' : 'black',
                      }}
                      title={`MA${maShort} × MA${maMid}\nSharpe: ${cell.sharpe.toFixed(2)}\n收益: ${cell.return.toFixed(1)}%\n最大回撤: ${cell.max_dd.toFixed(1)}%`}
                    >
                      {cell.sharpe.toFixed(1)}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 最佳参数提示 */}
      <div className="p-4 bg-muted/50 rounded-lg">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm font-medium">🏆 最佳参数:</span>
          <span className="text-sm">
            MA短期 = {bestParams.ma_short}, MA中期 = {bestParams.ma_mid}
          </span>
        </div>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">夏普比率:</span>
            <span className="ml-2 font-bold text-green-600">{bestParams.sharpe.toFixed(2)}</span>
          </div>
          <div>
            <span className="text-muted-foreground">年化收益:</span>
            <span className="ml-2 font-bold">{bestParams.return.toFixed(1)}%</span>
          </div>
          <div>
            <span className="text-muted-foreground">最大回撤:</span>
            <span className="ml-2 font-bold text-red-600">{bestParams.max_dd.toFixed(1)}%</span>
          </div>
        </div>
      </div>

      {/* 底部统计 */}
      <div className="pt-4 border-t grid grid-cols-4 gap-4 text-sm">
        <div>
          <p className="text-muted-foreground">参数组合数</p>
          <p className="font-bold">{data.length}</p>
        </div>
        <div>
          <p className="text-muted-foreground">夏普 &gt; 1.5 占比</p>
          <p className="font-bold text-green-600">
            {((data.filter(d => d.sharpe > 1.5).length / data.length) * 100).toFixed(1)}%
          </p>
        </div>
        <div>
          <p className="text-muted-foreground">夏普 &gt; 2.0 占比</p>
          <p className="font-bold text-green-600">
            {((data.filter(d => d.sharpe > 2.0).length / data.length) * 100).toFixed(1)}%
          </p>
        </div>
        <div>
          <p className="text-muted-foreground">稳健性评分</p>
          <p className="font-bold">
            {data.filter(d => d.sharpe > 1.5).length > data.length * 0.3 ? '良好' : '一般'}
          </p>
        </div>
      </div>
    </div>
  )
}
