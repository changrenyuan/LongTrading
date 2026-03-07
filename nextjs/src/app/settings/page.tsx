'use client'

import { DashboardSidebar } from '@/components/layout/DashboardSidebar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Settings, Save, RefreshCw } from 'lucide-react'

export default function SettingsPage() {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // TODO: 实现参数保存逻辑
    console.log('Settings saved')
  }

  return (
    <div className="flex h-screen bg-background">
      <DashboardSidebar />

      <main className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold">策略配置</h1>
              <p className="text-muted-foreground">调整策略参数与风控阈值</p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* 资金与基础风控 */}
            <Card>
              <CardHeader>
                <CardTitle>资金与基础风控</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="stop_loss_pct">硬止损比例</Label>
                    <Input
                      id="stop_loss_pct"
                      type="number"
                      step="0.01"
                      defaultValue="0.10"
                      placeholder="0.10"
                    />
                    <p className="text-xs text-muted-foreground">亏损达到该比例无条件止损</p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="trailing_stop_pct">移动止盈比例</Label>
                    <Input
                      id="trailing_stop_pct"
                      type="number"
                      step="0.01"
                      defaultValue="0.25"
                      placeholder="0.25"
                    />
                    <p className="text-xs text-muted-foreground">最高点回撤达到该比例止盈</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* 技术指标参数 */}
            <Card>
              <CardHeader>
                <CardTitle>技术指标参数</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="ma_short">短期均线周期</Label>
                    <Input
                      id="ma_short"
                      type="number"
                      defaultValue="5"
                      placeholder="5"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="ma_mid">中期均线周期</Label>
                    <Input
                      id="ma_mid"
                      type="number"
                      defaultValue="20"
                      placeholder="20"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="ma_long">长期均线周期</Label>
                    <Input
                      id="ma_long"
                      type="number"
                      defaultValue="60"
                      placeholder="60"
                    />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* 信号过滤参数 */}
            <Card>
              <CardHeader>
                <CardTitle>信号过滤参数</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="bias_entry_limit">首次建仓偏离限制</Label>
                    <Input
                      id="bias_entry_limit"
                      type="number"
                      step="0.01"
                      defaultValue="1.08"
                      placeholder="1.08"
                    />
                    <p className="text-xs text-muted-foreground">收盘价/中期均线</p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="add_pos_min_profit">加仓最低浮盈</Label>
                    <Input
                      id="add_pos_min_profit"
                      type="number"
                      step="0.01"
                      defaultValue="0.08"
                      placeholder="0.08"
                    />
                    <p className="text-xs text-muted-foreground">底仓必须浮盈 8% 以上才允许加仓</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* 提交按钮 */}
            <div className="flex gap-2">
              <Button type="submit" size="lg">
                <Save className="mr-2 h-4 w-4" />
                保存配置
              </Button>
              <Button type="button" variant="outline" size="lg">
                <RefreshCw className="mr-2 h-4 w-4" />
                重置默认
              </Button>
            </div>
          </form>
        </div>
      </main>
    </div>
  )
}
