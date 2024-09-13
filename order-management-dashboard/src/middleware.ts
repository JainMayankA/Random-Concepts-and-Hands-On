import { NextRequest, NextResponse } from 'next/server'
import { verifyToken } from '@/lib/auth'

const PUBLIC_PATHS = ['/login', '/api/auth/login']

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl

  if (PUBLIC_PATHS.some(p => pathname.startsWith(p))) {
    return NextResponse.next()
  }

  const token = req.cookies.get('omd_session')?.value
  if (!token) {
    return NextResponse.redirect(new URL('/login', req.url))
  }

  const user = await verifyToken(token)
  if (!user) {
    const response = NextResponse.redirect(new URL('/login', req.url))
    response.cookies.delete('omd_session')
    return response
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
