import { NextRequest, NextResponse } from 'next/server'
import { getSession } from '@/lib/auth'

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000'

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string; action: string } }
) {
  const user = await getSession()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  if (user.role === 'viewer') return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const body = await req.json().catch(() => ({}))
  try {
    const res = await fetch(`${API_BASE}/orders/${params.id}/${params.action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return NextResponse.json(await res.json(), { status: res.status })
  } catch {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 })
  }
}
