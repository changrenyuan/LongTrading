'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutDashboard, PieChart, List, Settings, Activity, TrendingUp, Star } from 'lucide-react'
import { cn } from '@/lib/utils'

const navigation = [
  { name: '总览', href: '/dashboard', icon: LayoutDashboard },
  { name: '持仓', href: '/positions', icon: PieChart },
  { name: '交易', href: '/trades', icon: List },
  { name: '关注', href: '/watchlist', icon: Star },
  { name: '策略', href: '/settings', icon: Settings },
  { name: '日志', href: '/logs', icon: Activity },
]

export function DashboardSidebar() {
  const pathname = usePathname()

  return (
    <div className="flex h-screen w-64 flex-col border-r bg-card">
      <div className="flex items-center gap-3 border-b px-6 py-4">
        <TrendingUp className="h-6 w-6 text-primary" />
        <div>
          <h1 className="font-bold text-lg">MT_Alpha</h1>
          <p className="text-xs text-muted-foreground">量化交易指挥中心</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 p-4">
        {navigation.map((item) => {
          const Icon = item.icon
          const isActive = pathname === item.href

          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )}
            >
              <Icon className="h-4 w-4" />
              {item.name}
            </Link>
          )
        })}
      </nav>

      <div className="border-t p-4">
        <div className="text-xs text-muted-foreground">
          <p>版本 v1.0.0</p>
          <p className="mt-1">系统状态: 运行中</p>
        </div>
      </div>
    </div>
  )
}
