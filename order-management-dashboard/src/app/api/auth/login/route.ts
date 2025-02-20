import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'
import { DEMO_USERS, signToken, verifyPassword } from '@/lib/auth'
import { rateLimit } from '@/lib/ratelimit'
import { logger } from '@/lib/logger'

const schema = z.object({
  email:    z.string().email().max(254),
  password: z.string().min(1).max(128),
})

export async function POST(req: NextRequest) {
  const ip = req.headers.get('x-forwarded-for') ?? req.headers.get('x-real-ip') ?? 'unknown'

  if (!rateLimit(`login:${ip}`, 10, 60_000)) {
    logger.warn('rate_limit_exceeded', { ip, path: '/api/auth/login' })
    return NextResponse.json({ error: 'Too many requests. Try again in a minute.' }, { status: 429 })
  }

  const body = await req.json().catch(() => null)
  const parsed = schema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json({ error: 'Invalid request' }, { status: 400 })
  }

  const { email, password } = parsed.data

  const user = DEMO_USERS.find(u => u.email === email)
  if (!user) {
    // constant-time response to prevent user enumeration via timing
    await new Promise(r => setTimeout(r, 100))
    logger.warn('login_failed', { email, ip, reason: 'user_not_found' })
    return NextResponse.json({ error: 'Invalid email or password' }, { status: 401 })
  }

  const valid = await verifyPassword(password, user.passwordHash)
  if (!valid) {
    logger.warn('login_failed', { email, ip, reason: 'wrong_password' })
    return NextResponse.json({ error: 'Invalid email or password' }, { status: 401 })
  }

  const { passwordHash: _, ...safeUser } = user
  const token = await signToken(safeUser)

  logger.info('login_success', { userId: safeUser.id, email: safeUser.email, role: safeUser.role, ip })

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
