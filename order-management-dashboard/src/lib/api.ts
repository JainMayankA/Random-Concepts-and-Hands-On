import type { Order, CustomerStats, DashboardMetrics, PlaceOrderPayload } from '@/types'

const BASE = process.env.API_BASE_URL || 'http://localhost:8000'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`API ${res.status}: ${err}`)
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

// ── Dashboard metrics (computed client-side from orders) ──────────────────────

export async function getDashboardMetrics(): Promise<DashboardMetrics> {
  const orders = await getOrders({ limit: 200 })

  const statusCounts = orders.reduce((acc, o) => {
    acc[o.status] = (acc[o.status] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  const today = new Date().toDateString()
  const deliveredToday = orders.filter(
    o => o.delivered_at && new Date(o.delivered_at).toDateString() === today
  ).length

  // Build 7-day revenue trend
  const trendMap = new Map<string, number>()
  for (let i = 6; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    trendMap.set(d.toISOString().split('T')[0], 0)
  }
  orders.forEach(o => {
    const day = o.placed_at.split('T')[0]
    if (trendMap.has(day)) trendMap.set(day, (trendMap.get(day) || 0) + o.total_amount)
  })

  return {
    total_orders:    orders.length,
    total_revenue:   orders.filter(o => o.status !== 'cancelled').reduce((s, o) => s + o.total_amount, 0),
    pending_orders:  (statusCounts['placed'] || 0) + (statusCounts['confirmed'] || 0),
    delivered_today: deliveredToday,
    orders_by_status: statusCounts as any,
    revenue_trend: Array.from(trendMap.entries()).map(([date, revenue]) => ({ date, revenue })),
  }
}
