'use client'
import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import { ArrowLeft, Truck, XCircle, CheckCircle, Package, AlertTriangle } from 'lucide-react'
import StatusBadge from '@/components/ui/StatusBadge'
import ErrorBoundary from '@/components/ErrorBoundary'
import type { Order, OrderStatus } from '@/types'
import { format } from 'date-fns'
import toast from 'react-hot-toast'
import Link from 'next/link'

const TIMELINE: { status: OrderStatus; label: string; icon: React.ElementType }[] = [
  { status: 'placed',    label: 'Order placed', icon: Package },
  { status: 'confirmed', label: 'Confirmed',    icon: CheckCircle },
  { status: 'shipped',   label: 'Shipped',      icon: Truck },
  { status: 'delivered', label: 'Delivered',    icon: CheckCircle },
]

const STATUS_ORDER: OrderStatus[] = ['placed', 'confirmed', 'shipped', 'delivered']

async function extractError(res: Response, fallback: string): Promise<string> {
  try {
    const data = await res.json()
    return typeof data.error === 'string' ? data.error : fallback
  } catch {
    return fallback
  }
}

function OrderDetail() {
  const { id } = useParams<{ id: string }>()
  const [order, setOrder]             = useState<Order | null>(null)
  const [loadError, setLoadError]     = useState(false)
  const [loading, setLoading]         = useState(true)
  const [actionLoading, setActLoad]   = useState(false)
  const [tracking, setTracking]       = useState('')
  const [carrier, setCarrier]         = useState('FedEx')
  const [cancelReason, setCancelR]    = useState('')
  const [showShipForm, setShipForm]   = useState(false)
  const [showCancelForm, setCancF]    = useState(false)

  useEffect(() => {
    fetch(`/api/orders/${id}`)
      .then(r => {
        if (!r.ok) throw new Error('not_found')
        return r.json()
      })
      .then(setOrder)
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }, [id])

  async function doAction(path: string, body: object) {
    setActLoad(true)
    try {
      const res = await fetch(`/api/orders/${id}/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const msg = await extractError(res, 'Action failed')
        toast.error(msg)
        return
      }
      const refreshed = await fetch(`/api/orders/${id}`)
      if (refreshed.ok) setOrder(await refreshed.json())
      toast.success('Order updated')
      setShipForm(false)
      setCancF(false)
    } catch {
      toast.error('Request failed — check your connection')
    } finally {
      setActLoad(false)
    }
  }

  if (loading) return <div className="p-8 text-sm text-gray-400 animate-pulse">Loading order…</div>

  if (loadError || !order) {
    return (
      <div className="p-8">
        <div className="card flex items-center gap-3 text-yellow-700 bg-yellow-50 border-yellow-100 max-w-lg">
          <AlertTriangle size={16} className="shrink-0" />
          <p className="text-sm">Order not found or backend is unavailable.</p>
        </div>
        <Link href="/orders" className="btn-secondary mt-4 inline-flex text-xs py-1.5 px-3">
          <ArrowLeft size={13} /> Back to orders
        </Link>
      </div>
    )
  }

  const currentStep = STATUS_ORDER.indexOf(order.status as OrderStatus)
  const isCancelled = order.status === 'cancelled'

  return (
    <div className="p-8 max-w-4xl">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/orders" className="btn-secondary py-1.5 px-3 text-xs">
          <ArrowLeft size={13} /> Orders
        </Link>
        <span className="text-gray-300">/</span>
        <span className="font-mono text-xs text-gray-500">{order.order_id}</span>
        <StatusBadge status={order.status as OrderStatus} />
      </div>

      <div className="grid grid-cols-3 gap-5">
        <div className="col-span-2 space-y-5">
          <div className="card">
            <h2 className="text-sm font-medium text-gray-700 mb-5">Order timeline</h2>
            {isCancelled ? (
              <div className="flex items-center gap-3 text-red-600 text-sm">
                <XCircle size={18} />
                <span>
                  Order cancelled
                  {order.cancelled_at ? ` — ${format(new Date(order.cancelled_at), 'MMM d, yyyy h:mm a')}` : ''}
                </span>
              </div>
            ) : (
              <div className="flex items-start gap-0">
                {TIMELINE.map(({ status, label, icon: Icon }, i) => {
                  const done    = i <= currentStep
                  const current = i === currentStep
                  const ts      = order[`${status}_at` as keyof Order] as string | undefined
                  return (
                    <div key={status} className="flex-1 flex flex-col items-center relative">
                      {i < TIMELINE.length - 1 && (
                        <div className={`absolute top-4 left-1/2 w-full h-0.5 ${i < currentStep ? 'bg-blue-500' : 'bg-gray-200'}`} />
                      )}
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center z-10 ${done ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-400'} ${current ? 'ring-2 ring-blue-200' : ''}`}>
                        <Icon size={14} />
                      </div>
                      <p className={`text-xs mt-2 font-medium ${done ? 'text-gray-800' : 'text-gray-400'}`}>{label}</p>
                      {ts && <p className="text-xs text-gray-400 mt-0.5">{format(new Date(ts), 'MMM d')}</p>}
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          <div className="card">
            <h2 className="text-sm font-medium text-gray-700 mb-4">Order details</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between text-gray-500">
                <span>Items</span>
                <span className="font-medium text-gray-900">{order.item_count}</span>
              </div>
              <div className="flex justify-between text-gray-500">
                <span>Total</span>
                <span className="font-medium text-gray-900">${order.total_amount.toFixed(2)}</span>
              </div>
              {order.tracking_number && (
                <div className="flex justify-between text-gray-500">
                  <span>Tracking</span>
                  <span className="font-mono text-xs text-blue-600">{order.tracking_number}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="card">
            <h2 className="text-sm font-medium text-gray-700 mb-3">Actions</h2>
            <div className="space-y-2">
              {order.status === 'placed' && (
                <button
                  onClick={() => doAction('confirm', {})}
                  disabled={actionLoading}
                  className="btn-primary w-full justify-center text-xs py-2"
                >
                  Confirm order
                </button>
              )}
              {order.status === 'confirmed' && !showShipForm && (
                <button onClick={() => setShipForm(true)} className="btn-primary w-full justify-center text-xs py-2">
                  <Truck size={13} /> Mark as shipped
                </button>
              )}
              {showShipForm && (
                <div className="space-y-2">
                  <input
                    className="input text-xs"
                    placeholder="Tracking number"
                    value={tracking}
                    onChange={e => setTracking(e.target.value)}
                  />
                  <select className="select text-xs" value={carrier} onChange={e => setCarrier(e.target.value)}>
                    {['FedEx', 'UPS', 'DHL', 'USPS'].map(c => <option key={c}>{c}</option>)}
                  </select>
                  <button
                    onClick={() => doAction('ship', { tracking_number: tracking, carrier })}
                    disabled={!tracking || actionLoading}
                    className="btn-primary w-full justify-center text-xs py-2"
                  >
                    Ship
                  </button>
                </div>
              )}
              {order.status === 'shipped' && (
                <button
                  onClick={() => doAction('deliver', {})}
                  disabled={actionLoading}
                  className="btn-primary w-full justify-center text-xs py-2"
                >
                  <CheckCircle size={13} /> Mark delivered
                </button>
              )}
              {!['delivered', 'cancelled'].includes(order.status) && !showCancelForm && (
                <button onClick={() => setCancF(true)} className="btn-danger w-full justify-center text-xs py-2">
                  <XCircle size={13} /> Cancel order
                </button>
              )}
              {showCancelForm && (
                <div className="space-y-2">
                  <input
                    className="input text-xs"
                    placeholder="Cancellation reason"
                    value={cancelReason}
                    onChange={e => setCancelR(e.target.value)}
                  />
                  <button
                    onClick={() => doAction('cancel', { reason: cancelReason })}
                    disabled={!cancelReason || actionLoading}
                    className="btn-danger w-full justify-center text-xs py-2"
                  >
                    Confirm cancel
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="card text-xs text-gray-500 space-y-2">
            <div className="flex justify-between">
              <span>Customer</span>
              <span className="font-mono text-gray-700">{order.customer_id.slice(0, 8)}…</span>
            </div>
            <div className="flex justify-between">
              <span>Placed</span>
              <span>{format(new Date(order.placed_at), 'MMM d, yyyy')}</span>
            </div>
            <div className="flex justify-between">
              <span>Updated</span>
              <span>{format(new Date(order.last_updated), 'MMM d, h:mm a')}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function OrderDetailPage() {
  return (
    <ErrorBoundary>
      <OrderDetail />
    </ErrorBoundary>
  )
}
