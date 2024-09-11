'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!res.ok) {
        const { error } = await res.json()
        throw new Error(error || 'Login failed')
      }
      toast.success('Welcome back!')
      router.push('/dashboard')
      router.refresh()
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-blue-600 text-white text-xl font-bold mb-4">O</div>
          <h1 className="text-2xl font-semibold text-gray-900">Order Management</h1>
          <p className="text-sm text-gray-500 mt-1">Sign in to your dashboard</p>
        </div>

        <div className="card">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email" required value={email}
                onChange={e => setEmail(e.target.value)}
                className="input" placeholder="admin@demo.com"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input
                type="password" required value={password}
                onChange={e => setPassword(e.target.value)}
                className="input" placeholder="••••••••"
              />
            </div>
            <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

        <div className="mt-4 card bg-blue-50 border-blue-100">
          <p className="text-xs font-medium text-blue-800 mb-2">Demo credentials</p>
          <div className="space-y-1 text-xs text-blue-700">
            <div><span className="font-mono">admin@demo.com</span> / admin123</div>
            <div><span className="font-mono">manager@demo.com</span> / manager123</div>
          </div>
        </div>
      </div>
    </div>
  )
}
