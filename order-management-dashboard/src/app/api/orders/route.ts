import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'
import { getSession } from '@/lib/auth'
import { logger } from '@/lib/logger'
import { API_BASE_URL } from '@/lib/env'

const placeOrderSchema = z.object({
  customer_id: z.string().min(1).max(100),
  items: z.array(
    z.object({
      product_id:  z.string().min(1).max(100),
      name:        z.string().min(1).max(200),
      quantity:    z.number().int().min(1).max(9999),
      unit_price:  z.number().positive(),
    })
  ).min(1),
})

export async function GET(req: NextRequest) {
  const user = await getSession()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { searchParams } = new URL(req.url)
  const qs = searchParams.toString()
  try {
    const res = await fetch(`${API_BASE_URL}/orders${qs ? `?${qs}` : ''}`)
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    logger.error('backend_unavailable', { path: '/orders', method: 'GET' })
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 })
  }
}

export async function POST(req: NextRequest) {
  const user = await getSession()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  if (user.role === 'viewer') return NextResponse.json({ error: 'Insufficient permissions' }, { status: 403 })

  const raw = await req.json().catch(() => null)
  const parsed = placeOrderSchema.safeParse(raw)
  if (!parsed.success) {
    return NextResponse.json({ error: 'Invalid order payload', details: parsed.error.flatten() }, { status: 400 })
  }

  logger.info('order_create', { userId: user.id, customerId: parsed.data.customer_id, itemCount: parsed.data.items.length })

  try {
    const res = await fetch(`${API_BASE_URL}/orders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parsed.data),
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    logger.error('backend_unavailable', { path: '/orders', method: 'POST' })
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 })
  }
}
