'use client'
import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Search, Plus, Filter, AlertTriangle } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import StatusBadge from '@/components/ui/StatusBadge'
import ErrorBoundary from '@/components/ErrorBoundary'
import type { Order, OrderStatus } from '@/types'
import toast from 'react-hot-toast'

const STATUSES: { label: string; value: string }[] = [
  { label: 'All statuses', value: '' },
  { label: 'Placed',       value: 'placed' },
  { label: 'Confirmed',    value: 'confirmed' },
  { label: 'Shipped',      value: 'shipped' },
  { label: 'Delivered',    value: 'delivered' },
  { label: 'Cancelled',    value: 'cancelled' },
]

const PAGE_SIZE = 20

function OrdersTable() {
  const router = useRouter()
  const [orders, setOrders]         = useState<Order[]>([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(false)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch]         = useState('')
  const [status, setStatus]         = useState('')
  const [page, setPage]             = useState(0)

  // Debounce the search input so we don't fire a request per keystroke
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setSearch(searchInput)
      setPage(0)
    }, 350)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [searchInput])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(false)

    const qs = new URLSearchParams()
    if (status) qs.set('status', status)
    if (search) qs.set('customer_id', search)
    qs.set('limit', String(PAGE_SIZE))
    qs.set('offset', String(page * PAGE_SIZE))

    fetch(`/api/orders?${qs}`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch')
        return res.json()
      })
      .then((data: Order[]) => { if (!cancelled) setOrders(data) })
      .catch(() => { if (!cancelled) { setError(true); toast.error('Could not load orders') } })
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [status, page, search])

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Orders</h1>
          <p className="text-sm text-gray-500 mt-0.5">{loading ? '—' : `${orders.length} orders`}</p>
        </div>
        <Link href="/orders/new" className="btn-primary">
          <Plus size={15} /> New order
        </Link>
      </div>

      <div className="card mb-5">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              className="input pl-9"
              placeholder="Search by customer ID…"
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter size={14} className="text-gray-400" />
            <select
              className="select w-40"
              value={status}
              onChange={e => { setStatus(e.target.value); setPage(0) }}
            >
              {STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
        </div>
      </div>

      {error ? (
        <div className="card flex items-center gap-3 text-yellow-700 bg-yellow-50 border-yellow-100">
          <AlertTriangle size={16} className="shrink-0" />
          <p className="text-sm">Could not load orders — backend is unavailable.</p>
        </div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                {['Order ID', 'Customer', 'Items', 'Amount', 'Status', 'Placed'].map(h => (
                  <th key={h} className="text-left px-5 py-3 text-xs font-medium text-gray-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i} className="border-b border-gray-50">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} className="px-5 py-3">
                        <div className="h-4 bg-gray-100 rounded animate-pulse w-20" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : orders.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-gray-400 text-sm">
                    No orders found
                  </td>
                </tr>
              ) : (
                orders.map(o => (
                  <tr
                    key={o.order_id}
                    className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                    onClick={() => router.push(`/orders/${o.order_id}`)}
                  >
                    <td className="px-5 py-3 font-mono text-xs text-blue-600">{o.order_id.slice(0, 8)}…</td>
                    <td className="px-5 py-3 font-mono text-xs text-gray-500">{o.customer_id.slice(0, 8)}…</td>
                    <td className="px-5 py-3 text-gray-600">{o.item_count}</td>
                    <td className="px-5 py-3 font-medium">${o.total_amount.toFixed(2)}</td>
                    <td className="px-5 py-3"><StatusBadge status={o.status as OrderStatus} /></td>
                    <td className="px-5 py-3 text-gray-400 text-xs">
                      {formatDistanceToNow(new Date(o.placed_at), { addSuffix: true })}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100">
            <span className="text-xs text-gray-400">Page {page + 1}</span>
            <div className="flex gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage(p => p - 1)}
                className="btn-secondary text-xs py-1 px-3 disabled:opacity-40"
              >
                Previous
              </button>
              <button
                disabled={orders.length < PAGE_SIZE}
                onClick={() => setPage(p => p + 1)}
                className="btn-secondary text-xs py-1 px-3 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function OrdersPage() {
  return (
    <ErrorBoundary>
      <OrdersTable />
    </ErrorBoundary>
  )
}
