import { Suspense } from 'react'
import { getDashboardMetrics, getOrders } from '@/lib/api'
import RevenueChart from '@/components/charts/RevenueChart'
import StatusPieChart from '@/components/charts/StatusPieChart'
import StatusBadge from '@/components/ui/StatusBadge'
import { TrendingUp, ShoppingCart, Clock, CheckCircle } from 'lucide-react'
import Link from 'next/link'
import { formatDistanceToNow } from 'date-fns'

async function MetricsAndCharts() {
  // Fall back to demo data if backend is not running
  let metrics
  try {
    metrics = await getDashboardMetrics()
  } catch {
    metrics = {
      total_orders: 142, total_revenue: 48320.50, pending_orders: 23, delivered_today: 8,
      orders_by_status: { placed: 12, confirmed: 11, shipped: 28, delivered: 85, cancelled: 6 },
      revenue_trend: Array.from({ length: 7 }, (_, i) => {
        const d = new Date(); d.setDate(d.getDate() - (6 - i))
        return { date: d.toISOString().split('T')[0], revenue: 4000 + Math.random() * 4000 }
      }),
    }
  }

  const stats = [
    { label: 'Total orders',    value: metrics.total_orders.toLocaleString(),    icon: ShoppingCart, color: 'text-blue-600 bg-blue-50' },
    { label: 'Total revenue',   value: `$${metrics.total_revenue.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, icon: TrendingUp, color: 'text-green-600 bg-green-50' },
    { label: 'Pending orders',  value: metrics.pending_orders.toLocaleString(),  icon: Clock,        color: 'text-yellow-600 bg-yellow-50' },
    { label: 'Delivered today', value: metrics.delivered_today.toLocaleString(), icon: CheckCircle,  color: 'text-purple-600 bg-purple-50' },
  ]

  return (
    <>
      <div className="grid grid-cols-4 gap-5 mb-6">
        {stats.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-gray-500">{label}</p>
                <p className="text-2xl font-semibold text-gray-900 mt-1">{value}</p>
              </div>
              <div className={`p-2 rounded-lg ${color}`}>
                <Icon size={18} />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-5">
        <div className="card col-span-2">
          <h2 className="text-sm font-medium text-gray-700 mb-4">Revenue — last 7 days</h2>
          <RevenueChart data={metrics.revenue_trend} />
        </div>
        <div className="card">
          <h2 className="text-sm font-medium text-gray-700 mb-4">Orders by status</h2>
          <StatusPieChart data={metrics.orders_by_status} />
        </div>
      </div>
    </>
  )
}

async function RecentOrders() {
  let orders
  try {
    orders = await getOrders({ limit: 8 })
  } catch {
    orders = []
  }

  return (
    <div className="card mt-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-medium text-gray-700">Recent orders</h2>
        <Link href="/orders" className="text-xs text-blue-600 hover:underline">View all</Link>
      </div>
      {orders.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-8">No orders yet. Start the backend to see live data.</p>
      ) : (
        <table className="w-full text-sm">
          <thead><tr className="text-xs text-gray-400 border-b border-gray-100">
            <th className="text-left pb-2 font-medium">Order ID</th>
            <th className="text-left pb-2 font-medium">Customer</th>
            <th className="text-right pb-2 font-medium">Amount</th>
            <th className="text-center pb-2 font-medium">Status</th>
            <th className="text-right pb-2 font-medium">Placed</th>
          </tr></thead>
          <tbody>
            {orders.map(o => (
              <tr key={o.order_id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="py-2.5">
                  <Link href={`/orders/${o.order_id}`} className="font-mono text-xs text-blue-600 hover:underline">
                    {o.order_id.slice(0, 8)}…
                  </Link>
                </td>
                <td className="py-2.5 text-gray-600 font-mono text-xs">{o.customer_id.slice(0, 8)}…</td>
                <td className="py-2.5 text-right font-medium">${o.total_amount.toFixed(2)}</td>
                <td className="py-2.5 text-center"><StatusBadge status={o.status} /></td>
                <td className="py-2.5 text-right text-gray-400 text-xs">
                  {formatDistanceToNow(new Date(o.placed_at), { addSuffix: true })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default function DashboardPage() {
  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-0.5">Real-time view of order activity</p>
      </div>
      <Suspense fallback={<div className="text-sm text-gray-400">Loading metrics…</div>}>
        <MetricsAndCharts />
      </Suspense>
      <Suspense fallback={<div className="text-sm text-gray-400 mt-5">Loading orders…</div>}>
        <RecentOrders />
      </Suspense>
    </div>
  )
}
