import { NextRequest, NextResponse } from 'next/server'
import { getSession } from '@/lib/auth'
import { logger } from '@/lib/logger'
import { API_BASE_URL } from '@/lib/env'

const ORDER_ID_RE = /^[\w-]{1,50}$/

export async function GET(req: NextRequest, { params }: { params: { id: string } }) {
  const user = await getSession()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  if (!ORDER_ID_RE.test(params.id)) {
    return NextResponse.json({ error: 'Invalid order ID' }, { status: 400 })
  }

  try {
    const res = await fetch(`${API_BASE_URL}/orders/${params.id}`)
    return NextResponse.json(await res.json(), { status: res.status })
  } catch {
    logger.error('backend_unavailable', { path: `/orders/${params.id}`, method: 'GET' })
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 })
  }
}
