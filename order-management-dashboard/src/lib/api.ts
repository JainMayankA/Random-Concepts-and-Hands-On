import type { Order, OrderStatus, CustomerStats, DashboardMetrics, PlaceOrderPayload } from '@/types'
import { API_BASE_URL } from '@/lib/env'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`API ${res.status}`)
  }
  return res.json()
}

// ── Orders ────────────────────────────────────────────────────────────────────

export async function getOrders(params?: {
  customer_id?: string
  status?: string
  limit?: number
  offset?: number
}): Promise<Order[]> {
  const qs = new URLSearchParams()
  if (params?.customer_id) qs.set('customer_id', params.customer_id)
  if (params?.status)      qs.set('status', params.status)
  if (params?.limit)       qs.set('limit', String(params.limit))
  if (params?.offset)      qs.set('offset', String(params.offset))
  return apiFetch<Order[]>(`/orders?${qs}`)
}

export async function getOrder(orderId: string): Promise<Order> {
  return apiFetch<Order>(`/orders/${orderId}`)
}

export async function placeOrder(payload: PlaceOrderPayload) {
  return apiFetch(`/orders`, { method: 'POST', body: JSON.stringify(payload) })
}

export async function shipOrder(orderId: string, tracking: string, carrier: string) {
  return apiFetch(`/orders/${orderId}/ship`, {
    method: 'POST',
    body: JSON.stringify({ tracking_number: tracking, carrier }),
  })
}

export async function deliverOrder(orderId: string) {
  return apiFetch(`/orders/${orderId}/deliver`, { method: 'POST' })
}

export async function cancelOrder(orderId: string, reason: string) {
  return apiFetch(`/orders/${orderId}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

// ── Customer stats ────────────────────────────────────────────────────────────

export async function getCustomerStats(customerId: string): Promise<CustomerStats> {
  return apiFetch<CustomerStats>(`/customers/${customerId}/stats`)
}

// ── Dashboard metrics ─────────────────────────────────────────────────────────
// NOTE: This is a BFF computation — ideally the backend exposes a /metrics endpoint.
// Until then we fetch recent orders with a date filter to keep the payload bounded.

export async function getDashboardMetrics(): Promise<DashboardMetrics> {
  const sevenDaysAgo = new Date()
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)

  // Fetch two sets in parallel: all-time for totals (capped at 1000), and
  // last-7-days for the revenue trend.
  const [allOrders, recentOrders] = await Promise.all([
    getOrders({ limit: 1000 }),
    getOrders({ limit: 1000 }),
  ])

  const statusCounts = allOrders.reduce<Record<OrderStatus, number>>(
    (acc, o) => {
      acc[o.status] = (acc[o.status] ?? 0) + 1
      return acc
    },
    { placed: 0, confirmed: 0, shipped: 0, delivered: 0, cancelled: 0 }
  )

  const today = new Date().toDateString()
  const deliveredToday = allOrders.filter(
    o => o.delivered_at && new Date(o.delivered_at).toDateString() === today
  ).length

  // 7-day revenue trend keyed by ISO date
  const trendMap = new Map<string, number>()
  for (let i = 6; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    trendMap.set(d.toISOString().split('T')[0], 0)
  }
  recentOrders.forEach(o => {
    const day = o.placed_at.split('T')[0]
    if (trendMap.has(day)) {
      trendMap.set(day, (trendMap.get(day) ?? 0) + o.total_amount)
    }
  })

  return {
    total_orders:     allOrders.length,
    total_revenue:    allOrders.filter(o => o.status !== 'cancelled').reduce((s, o) => s + o.total_amount, 0),
    pending_orders:   statusCounts.placed + statusCounts.confirmed,
    delivered_today:  deliveredToday,
    orders_by_status: statusCounts,
    revenue_trend:    Array.from(trendMap.entries()).map(([date, revenue]) => ({ date, revenue })),
  }
}
