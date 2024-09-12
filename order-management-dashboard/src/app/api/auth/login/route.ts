import { NextRequest, NextResponse } from 'next/server'
import { DEMO_USERS, signToken, verifyPassword } from '@/lib/auth'

export async function POST(req: NextRequest) {
  const { email, password } = await req.json()

  const user = DEMO_USERS.find(u => u.email === email)
  if (!user) {
    return NextResponse.json({ error: 'Invalid email or password' }, { status: 401 })
  }

  const valid = await verifyPassword(password, user.passwordHash)
  if (!valid) {
    return NextResponse.json({ error: 'Invalid email or password' }, { status: 401 })
  }

  const { passwordHash: _, ...safeUser } = user
  const token = await signToken(safeUser)

  const response = NextResponse.json({ user: safeUser })
  response.cookies.set('omd_session', token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 60 * 8,
    path: '/',
  })
  return response
}
