'use client'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { LayoutDashboard, ShoppingCart, Users, LogOut, Package } from 'lucide-react'
import toast from 'react-hot-toast'
import type { User } from '@/types'
import clsx from 'clsx'

const NAV = [
  { href: '/dashboard',  label: 'Dashboard',  icon: LayoutDashboard },
  { href: '/orders',     label: 'Orders',     icon: ShoppingCart },
  { href: '/customers',  label: 'Customers',  icon: Users },
]

export default function Sidebar({ user }: { user: User }) {
  const pathname = usePathname()
  const router = useRouter()

  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST' })
    toast.success('Signed out')
    router.push('/login')
    router.refresh()
  }

  return (
    <aside className="w-60 shrink-0 min-h-screen bg-white border-r border-gray-200 flex flex-col">
      <div className="p-5 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <Package size={16} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900">OrderMS</p>
            <p className="text-xs text-gray-400">Management Portal</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href} href={href}
            className={clsx(
              'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
              pathname.startsWith(href)
                ? 'bg-blue-50 text-blue-700 font-medium'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            )}
          >
            <Icon size={16} />
            {label}
          </Link>
        ))}
      </nav>

      <div className="p-4 border-t border-gray-100">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 text-xs font-medium">
            {user.name.split(' ').map(n => n[0]).join('')}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">{user.name}</p>
            <p className="text-xs text-gray-400 capitalize">{user.role}</p>
          </div>
        </div>
        <button onClick={logout} className="flex items-center gap-2 text-xs text-gray-500 hover:text-red-600 transition-colors w-full">
          <LogOut size={14} /> Sign out
        </button>
      </div>
    </aside>
  )
}
