'use client'

interface HeatmapCellProps {
  value: number
  min: number
  max: number
  xLabel: string
  yLabel: string
  onClick?: () => void
}

export function HeatmapCell({ value, min, max, xLabel, yLabel, onClick }: HeatmapCellProps) {
  // 计算颜色插值 (0-1)
  const ratio = (value - min) / (max - min)
  
  // 使用绿色渐变 (从浅绿到深绿)
  const hue = 120
  const saturation = 60 + ratio * 20
  const lightness = 90 - ratio * 40
  const bgColor = `hsl(${hue}, ${saturation}%, ${lightness}%)`
  
  // 文字颜色根据背景亮度决定
  const textColor = ratio > 0.5 ? 'white' : 'black'
  
  return (
    <div
      className="relative flex items-center justify-center cursor-pointer transition-all hover:scale-110 hover:z-10 hover:shadow-lg"
      style={{
        backgroundColor: bgColor,
        width: '100%',
        height: '100%',
        minWidth: '40px',
        minHeight: '40px',
      }}
      onClick={onClick}
      title={`${xLabel} / ${yLabel}: ${value.toFixed(2)}`}
    >
      <span
        className="text-xs font-medium"
        style={{ color: textColor }}
      >
        {value.toFixed(1)}
      </span>
    </div>
  )
}
