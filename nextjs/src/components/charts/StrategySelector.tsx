'use client'

import { useState } from 'react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'

interface Strategy {
  id: string
  name: string
  type: string
  status: 'running' | 'paused' | 'stopped'
  return_pct: number
}

interface StrategySelectorProps {
  strategies: Strategy[]
  selectedId: string
  onSelect: (id: string) => void
}

export function StrategySelector({ strategies, selectedId, onSelect }: StrategySelectorProps) {
  const selectedStrategy = strategies.find(s => s.id === selectedId)

  return (
    <div className="flex items-center gap-4">
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">当前策略:</span>
        <Select value={selectedId} onValueChange={onSelect}>
          <SelectTrigger className="w-[280px]">
            <SelectValue placeholder="选择策略" />
          </SelectTrigger>
          <SelectContent>
            {strategies.map((strategy) => (
              <SelectItem key={strategy.id} value={strategy.id}>
                <div className="flex items-center justify-between w-full gap-4">
                  <span>{strategy.name}</span>
                  <div className="flex items-center gap-2">
                    <Badge 
                      variant={strategy.status === 'running' ? 'default' : strategy.status === 'paused' ? 'secondary' : 'outline'}
                      className="text-xs"
                    >
                      {strategy.status === 'running' ? '运行中' : strategy.status === 'paused' ? '已暂停' : '已停止'}
                    </Badge>
                    <span className={`text-xs font-medium ${strategy.return_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {strategy.return_pct >= 0 ? '+' : ''}{strategy.return_pct.toFixed(1)}%
                    </span>
                  </div>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      
      {selectedStrategy && (
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs">
            {selectedStrategy.type}
          </Badge>
        </div>
      )}
    </div>
  )
}
