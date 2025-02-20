'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowLeft, Plus, Trash2 } from 'lucide-react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import ErrorBoundary from '@/components/ErrorBoundary'
import type { OrderItem } from '@/types'

const PRODUCTS = [
  { id: 'prod-001', name: 'Widget Pro',  price: 29.99 },
  { id: 'prod-002', name: 'Gadget Plus', price: 49.99 },
  { id: 'prod-003', name: 'Super Tool',  price: 89.99 },
  { id: 'prod-004', name: 'Mega Device', price: 199.99 },
]

async function extractError(res: Response, fallback: string): Promise<string> {
  try {
    const data = await res.json()
    return typeof data.error === 'string' ? data.error : fallback
  } catch {
    return fallback
  }
}

function NewOrderForm() {
  const router = useRouter()
  const [customerId, setCustomerId] = useState('')
  const [items, setItems] = useState<(OrderItem & { key: number })[]>([
    { key: 0, product_id: PRODUCTS[0].id, name: PRODUCTS[0].name, quantity: 1, unit_price: PRODUCTS[0].price },
  ])
  const [loading, setLoading]   = useState(false)
  const [keyCounter, setKeyCounter] = useState(1)

  function addItem() {
    setItems(prev => [
      ...prev,
      { key: keyCounter, product_id: PRODUCTS[0].id, name: PRODUCTS[0].name, quantity: 1, unit_price: PRODUCTS[0].price },
    ])
    setKeyCounter(k => k + 1)
  }

  function removeItem(key: number) {
    setItems(prev => prev.filter(i => i.key !== key))
  }

  function updateItem(key: number, field: string, value: string | number) {
    setItems(prev => prev.map(item => {
      if (item.key !== key) return item
      if (field === 'product_id') {
        const product = PRODUCTS.find(p => p.id === value)
        return product ? { ...item, product_id: product.id, name: product.name, unit_price: product.price } : item
      }
      return { ...item, [field]: field === 'quantity' ? Number(value) : value }
    }))
  }

  const total = items.reduce((s, i) => s + i.quantity * i.unit_price, 0)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!customerId.trim()) { toast.error('Customer ID is required'); return }
    if (items.length === 0) { toast.error('Add at least one item'); return }

    setLoading(true)
    try {
      const res = await fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_id: customerId.trim(),
          items: items.map(({ key, ...rest }) => rest),
        }),
      })
      if (!res.ok) {
        const msg = await extractError(res, 'Failed to place order')
        toast.error(msg)
        return
      }
      const { order_id } = await res.json()
      toast.success('Order placed!')
      router.push(`/orders/${order_id}`)
    } catch {
      toast.error('Request failed — check your connection')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8 max-w-2xl">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/orders" className="btn-secondary py-1.5 px-3 text-xs">
          <ArrowLeft size={13} /> Orders
        </Link>
        <h1 className="text-xl font-semibold text-gray-900">New order</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="card">
          <h2 className="text-sm font-medium text-gray-700 mb-3">Customer</h2>
          <input
            className="input"
            placeholder="Customer ID (e.g. cust-0001)"
            value={customerId}
            onChange={e => setCustomerId(e.target.value)}
            required
          />
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-gray-700">Items</h2>
            <button type="button" onClick={addItem} className="btn-secondary text-xs py-1.5 px-3">
              <Plus size={13} /> Add item
            </button>
          </div>

          <div className="space-y-3">
            {items.map(item => (
              <div key={item.key} className="flex gap-3 items-center">
                <select
                  className="select flex-1"
                  value={item.product_id}
                  onChange={e => updateItem(item.key, 'product_id', e.target.value)}
                >
                  {PRODUCTS.map(p => (
                    <option key={p.id} value={p.id}>{p.name} — ${p.price}</option>
                  ))}
                </select>
                <input
                  type="number"
                  min="1"
                  max="99"
                  className="input w-20 text-center"
                  value={item.quantity}
                  onChange={e => updateItem(item.key, 'quantity', e.target.value)}
                />
                <span className="text-sm text-gray-500 w-20 text-right">
                  ${(item.quantity * item.unit_price).toFixed(2)}
                </span>
                <button
                  type="button"
                  onClick={() => removeItem(item.key)}
                  className="text-gray-300 hover:text-red-500 transition-colors"
                  disabled={items.length === 1}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>

          <div className="border-t border-gray-100 mt-4 pt-3 flex justify-between text-sm font-medium">
            <span>Total</span>
            <span>${total.toFixed(2)}</span>
          </div>
        </div>

        <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
          {loading ? 'Placing order…' : `Place order — $${total.toFixed(2)}`}
        </button>
      </form>
    </div>
  )
}

export default function NewOrderPage() {
  return (
    <ErrorBoundary>
      <NewOrderForm />
    </ErrorBoundary>
  )
}
