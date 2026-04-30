import clsx from 'clsx'
import type { OrderStatus } from '@/types'

const CONFIG: Record<OrderStatus, { label: string; classes: string }> = {
  placed:    { label: 'Placed',    classes: 'bg-blue-50 text-blue-700' },
  confirmed: { label: 'Confirmed', classes: 'bg-yellow-50 text-yellow-700' },
  shipped:   { label: 'Shipped',   classes: 'bg-purple-50 text-purple-700' },
  delivered: { label: 'Delivered', classes: 'bg-green-50 text-green-700' },
  cancelled: { label: 'Cancelled', classes: 'bg-red-50 text-red-700' },
}

export default function StatusBadge({ status }: { status: OrderStatus }) {
  const { label, classes } = CONFIG[status] ?? { label: status, classes: 'bg-gray-100 text-gray-600' }
  return <span className={clsx('badge', classes)}>{label}</span>
}
