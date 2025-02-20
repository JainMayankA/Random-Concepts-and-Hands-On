import { SignJWT, jwtVerify } from 'jose'
import { cookies } from 'next/headers'
import bcrypt from 'bcryptjs'
import type { User } from '@/types'
import { JWT_SECRET as JWT_SECRET_STRING } from '@/lib/env'

const SECRET = new TextEncoder().encode(JWT_SECRET_STRING)
const COOKIE_NAME = 'omd_session'
const EXPIRY = '8h'

export const DEMO_USERS: (User & { passwordHash: string })[] = [
  {
    id: '1', email: 'admin@demo.com', name: 'Mayank Jain', role: 'admin',
    passwordHash: '$2b$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi',
  },
  {
    id: '2', email: 'manager@demo.com', name: 'Sarah Connor', role: 'manager',
    passwordHash: '$2b$10$RqX9Z1FmvIYcLzGxKJp7OOzmNMFyD5JxJpDYHMEQ4xD6jqCi1QQiK',
  },
  {
    id: '3', email: 'viewer@demo.com', name: 'Bob Smith', role: 'viewer',
    passwordHash: '$2b$10$Wz3kLpN2VtQHmRdX8S5uIekAhJGDVBT9sYqMzKfP0wXnCo6lE4UYa',
  },
]

export async function verifyPassword(plain: string, hash: string): Promise<boolean> {
  return bcrypt.compare(plain, hash)
}

export async function signToken(user: User): Promise<string> {
  return new SignJWT({ sub: user.id, email: user.email, name: user.name, role: user.role })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime(EXPIRY)
    .sign(SECRET)
}

export async function verifyToken(token: string): Promise<User | null> {
  try {
    const { payload } = await jwtVerify(token, SECRET)
    return {
      id:    payload.sub as string,
      email: payload.email as string,
      name:  payload.name  as string,
      role:  payload.role  as User['role'],
    }
  } catch {
    return null
  }
}

export async function getSession(): Promise<User | null> {
  const token = cookies().get(COOKIE_NAME)?.value
  if (!token) return null
  return verifyToken(token)
}

export function setSessionCookie(token: string) {
  cookies().set(COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 60 * 8,
    path: '/',
  })
}

export function clearSessionCookie() {
  cookies().delete(COOKIE_NAME)
}
