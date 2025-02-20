import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'
import { getSession } from '@/lib/auth'
import { logger } from '@/lib/logger'
import { API_BASE_URL } from '@/lib/env'

const ALLOWED_ACTIONS = new Set(['confirm', 'ship', 'deliver', 'cancel'])

const ORDER_ID_RE = /^[\w-]{1,50}$/

const shipSchema = z.object({
  tracking_number: z.string().min(1).max(100),
  carrier: z.enum(['FedEx', 'UPS', 'DHL', 'USPS']),
})

const cancelSchema = z.object({
  reason: z.string().min(1).max(500),
})

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string; action: string } }
) {
  const user = await getSession()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  if (user.role === 'viewer') return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  if (!ALLOWED_ACTIONS.has(params.action)) {
    return NextResponse.json({ error: 'Invalid action' }, { status: 400 })
  }

  if (!ORDER_ID_RE.test(params.id)) {
    return NextResponse.json({ error: 'Invalid order ID' }, { status: 400 })
  }

  let body: Record<string, unknown> = {}
  try { body = await req.json() } catch { /* empty body is fine for confirm/deliver */ }

  if (params.action === 'ship') {
    const parsed = shipSchema.safeParse(body)
    if (!parsed.success) {
      return NextResponse.json({ error: 'tracking_number and carrier are required' }, { status: 400 })
    }
    body = parsed.data
  } else if (params.action === 'cancel') {
    const parsed = cancelSchema.safeParse(body)
    if (!parsed.success) {
      return NextResponse.json({ error: 'A cancellation reason is required' }, { status: 400 })
    }
    body = parsed.data
  }

  logger.info('order_action', { userId: user.id, role: user.role, orderId: params.id, action: params.action })

  try {
    const res = await fetch(`${API_BASE_URL}/orders/${params.id}/${params.action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json().catch(() => ({}))
    return NextResponse.json(data, { status: res.status })
  } catch {
    logger.error('backend_unavailable', { path: `/orders/${params.id}/${params.action}` })
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 })
  }
}
