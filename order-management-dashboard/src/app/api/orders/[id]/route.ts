import { NextRequest, NextResponse } from 'next/server'
import { getSession } from '@/lib/auth'

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000'

export async function GET(req: NextRequest, { params }: { params: { id: string } }) {
  const user = await getSession()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  try {
    const res = await fetch(`${API_BASE}/orders/${params.id}`)
    return NextResponse.json(await res.json(), { status: res.status })
  } catch {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 })
  }
}
