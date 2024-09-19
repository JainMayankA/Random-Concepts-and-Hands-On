'use client'
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { OrderStatus } from '@/types'

const COLORS: Record<string, string> = {
  placed:    '#3b82f6',
  confirmed: '#eab308',
  shipped:   '#8b5cf6',
  delivered: '#22c55e',
  cancelled: '#ef4444',
}

interface Props {
  data: Record<string, number>
}

export default function StatusPieChart({ data }: Props) {
  const chartData = Object.entries(data)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name: name.charAt(0).toUpperCase() + name.slice(1), value }))

  if (chartData.length === 0) return (
    <div className="flex items-center justify-center h-48 text-sm text-gray-400">No data yet</div>
  )

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie data={chartData} cx="50%" cy="45%" innerRadius={55} outerRadius={85}
          paddingAngle={3} dataKey="value">
          {chartData.map((entry, i) => (
            <Cell key={i} fill={COLORS[entry.name.toLowerCase()] ?? '#94a3b8'} />
          ))}
        </Pie>
        <Tooltip
          formatter={(v: number, name: string) => [v, name]}
          contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
        />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
      </PieChart>
    </ResponsiveContainer>
  )
}
