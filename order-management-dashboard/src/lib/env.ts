function requireEnv(name: string): string {
  const value = process.env[name]
  if (!value) throw new Error(`[startup] Missing required environment variable: ${name}`)
  return value
}

export const JWT_SECRET = requireEnv('JWT_SECRET')
export const API_BASE_URL = process.env.API_BASE_URL ?? 'http://localhost:8000'
export const NODE_ENV = (process.env.NODE_ENV ?? 'development') as 'development' | 'production' | 'test'
