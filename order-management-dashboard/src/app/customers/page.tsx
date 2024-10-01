import { redirect } from 'next/navigation'
import { getSession } from '@/lib/auth'
import Sidebar from '@/components/ui/Sidebar'
import { Users } from 'lucide-react'

export default async function CustomersPage() {
  const user = await getSession()
  if (!user) redirect('/login')

  const DEMO_CUSTOMERS = [
    { id: 'cust-0001', name: 'Acme Corp', orders: 24, spent: 4820.50, last: '2 days ago' },
    { id: 'cust-0002', name: 'Globex Inc', orders: 18, spent: 3201.00, last: '5 days ago' },
    { id: 'cust-0003', name: 'Initech LLC', orders: 9, spent: 1450.75, last: '1 week ago' },
    { id: 'cust-0004', name: 'Umbrella Co', orders: 31, spent: 7890.00, last: 'Today' },
  ]

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar user={user} />
      <main className="flex-1 p-8">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-gray-900">Customers</h1>
          <p className="text-sm text-gray-500 mt-0.5">{DEMO_CUSTOMERS.length} customers</p>
        </div>

        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                {['Customer', 'ID', 'Total orders', 'Total spent', 'Last order'].map(h => (
                  <th key={h} className="text-left px-5 py-3 text-xs font-medium text-gray-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {DEMO_CUSTOMERS.map(c => (
                <tr key={c.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 text-xs font-medium">
                        {c.name[0]}
                      </div>
                      <span className="font-medium text-gray-900">{c.name}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3 font-mono text-xs text-gray-500">{c.id}</td>
                  <td className="px-5 py-3">{c.orders}</td>
                  <td className="px-5 py-3 font-medium">${c.spent.toLocaleString()}</td>
                  <td className="px-5 py-3 text-gray-400 text-xs">{c.last}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  )
}
