export type OrderStatus =
  | 'placed'
  | 'confirmed'
  | 'shipped'
  | 'delivered'
  | 'cancelled'

export interface OrderItem {
  product_id: string
  name: string
  quantity: number
  unit_price: number
}

export interface Order {
  order_id: string
  customer_id: string
  status: OrderStatus
  total_amount: number
  item_count: number
  tracking_number?: string
  placed_at: string
  confirmed_at?: string
  shipped_at?: string
  delivered_at?: string
  cancelled_at?: string
  last_updated: string
}

export interface CustomerStats {
  customer_id: string
  total_orders: number
  total_spent: number
  last_order_at: string
}

export interface DashboardMetrics {
  total_orders: number
  total_revenue: number
  pending_orders: number
  delivered_today: number
  orders_by_status: Record<OrderStatus, number>
  revenue_trend: { date: string; revenue: number }[]
}

export interface User {
  id: string
  email: string
  name: string
  role: 'admin' | 'manager' | 'viewer'
}

export interface AuthSession {
  user: User
  token: string
  expires: string
}

export interface PlaceOrderPayload {
  customer_id: string
  items: OrderItem[]
}
