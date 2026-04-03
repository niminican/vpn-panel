import { useEffect, useState, FormEvent } from 'react'
import { Plus, Edit2, Trash2, Package as PackageIcon } from 'lucide-react'
import api from '../api/client'
import { formatBytes } from '../lib/utils'
import toast from 'react-hot-toast'

interface Pkg {
  id: number
  name: string
  description: string | null
  bandwidth_limit: number | null
  speed_limit: number | null
  duration_days: number
  max_connections: number
  price: number | null
  currency: string
  enabled: boolean
  destination_vpn_id: number | null
  destination_vpn_name: string | null
}

interface Destination {
  id: number
  name: string
  protocol: string
}

export default function Packages() {
  const [packages, setPackages] = useState<Pkg[]>([])
  const [destinations, setDestinations] = useState<Destination[]>([])
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [form, setForm] = useState({
    name: '',
    description: '',
    bandwidth_limit_value: '',
    bandwidth_unit: 'GB' as 'GB' | 'MB',
    speed_limit_mbps: '',
    duration_days: '30',
    max_connections: '1',
    price: '',
    currency: 'IRR',
    enabled: true,
    destination_vpn_id: '',
  })

  const fetchPackages = async () => {
    const res = await api.get('/packages')
    setPackages(res.data)
  }

  useEffect(() => {
    fetchPackages()
    api.get('/destinations').then((res) => setDestinations(res.data))
  }, [])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const payload: Record<string, unknown> = {
      name: form.name,
      description: form.description || null,
      duration_days: Number(form.duration_days),
      max_connections: Number(form.max_connections),
      currency: form.currency,
      enabled: form.enabled,
      destination_vpn_id: form.destination_vpn_id ? Number(form.destination_vpn_id) : null,
    }
    if (form.bandwidth_limit_value) {
      const multiplier = form.bandwidth_unit === 'GB' ? 1024 * 1024 * 1024 : 1024 * 1024
      payload.bandwidth_limit = Number(form.bandwidth_limit_value) * multiplier
    }
    if (form.speed_limit_mbps) payload.speed_limit = Number(form.speed_limit_mbps) * 1000
    if (form.price) payload.price = Number(form.price)

    try {
      if (editId) {
        await api.put(`/packages/${editId}`, payload)
        toast.success('Package updated')
      } else {
        await api.post('/packages', payload)
        toast.success('Package created')
      }
      setShowForm(false)
      setEditId(null)
      resetForm()
      fetchPackages()
    } catch {
      toast.error('Failed')
    }
  }

  const resetForm = () => setForm({
    name: '', description: '', bandwidth_limit_value: '', bandwidth_unit: 'GB', speed_limit_mbps: '',
    duration_days: '30', max_connections: '1', price: '', currency: 'IRR', enabled: true, destination_vpn_id: '',
  })

  const editPkg = (pkg: Pkg) => {
    const isSmall = pkg.bandwidth_limit && pkg.bandwidth_limit < 1024 * 1024 * 1024
    const bwUnit = isSmall ? 'MB' : 'GB'
    const bwDivisor = isSmall ? 1024 * 1024 : 1024 * 1024 * 1024
    setForm({
      name: pkg.name,
      description: pkg.description || '',
      bandwidth_limit_value: pkg.bandwidth_limit ? String(pkg.bandwidth_limit / bwDivisor) : '',
      bandwidth_unit: bwUnit as 'GB' | 'MB',
      speed_limit_mbps: pkg.speed_limit ? String(pkg.speed_limit / 1000) : '',
      duration_days: String(pkg.duration_days),
      max_connections: String(pkg.max_connections),
      price: pkg.price ? String(pkg.price) : '',
      currency: pkg.currency,
      enabled: pkg.enabled,
      destination_vpn_id: pkg.destination_vpn_id ? String(pkg.destination_vpn_id) : '',
    })
    setEditId(pkg.id)
    setShowForm(true)
  }

  const deletePkg = async (id: number) => {
    if (!confirm('Delete this package?')) return
    await api.delete(`/packages/${id}`)
    toast.success('Deleted')
    fetchPackages()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Packages</h1>
        <button
          onClick={() => { setShowForm(!showForm); setEditId(null); resetForm() }}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" /> Add Package
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="rounded-xl bg-white p-6 shadow-sm border border-gray-100 space-y-4">
          <h3 className="text-lg font-medium">{editId ? 'Edit' : 'New'} Package</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
              <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <input type="text" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Destination VPN</label>
              <select value={form.destination_vpn_id} onChange={(e) => setForm({ ...form, destination_vpn_id: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500">
                <option value="">-- None --</option>
                {destinations.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.protocol})</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Bandwidth</label>
              <div className="flex gap-2">
                <input type="number" value={form.bandwidth_limit_value} onChange={(e) => setForm({ ...form, bandwidth_limit_value: e.target.value })}
                  className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="Unlimited" step="any" />
                <select value={form.bandwidth_unit} onChange={(e) => setForm({ ...form, bandwidth_unit: e.target.value as 'GB' | 'MB' })}
                  className="w-20 rounded-lg border border-gray-300 px-2 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500">
                  <option value="GB">GB</option>
                  <option value="MB">MB</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Speed (Mbps)</label>
              <input type="number" value={form.speed_limit_mbps} onChange={(e) => setForm({ ...form, speed_limit_mbps: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="Unlimited" step="any" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Duration (days) *</label>
              <input type="number" value={form.duration_days} onChange={(e) => setForm({ ...form, duration_days: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" required min="1" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Max Connections</label>
              <input type="number" value={form.max_connections} onChange={(e) => setForm({ ...form, max_connections: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" min="1" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Price</label>
              <input type="number" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="Free" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Currency</label>
              <select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500">
                <option value="IRR">IRR (Rial)</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="CAD">CAD</option>
              </select>
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button type="submit" className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700">
              {editId ? 'Update' : 'Create'}
            </button>
            <button type="button" onClick={() => { setShowForm(false); setEditId(null) }}
              className="rounded-lg border border-gray-300 px-6 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50">Cancel</button>
          </div>
        </form>
      )}

      {/* Package Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {packages.length === 0 ? (
          <div className="col-span-3 rounded-xl bg-white p-12 shadow-sm border border-gray-100 text-center">
            <PackageIcon className="h-12 w-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No packages defined yet.</p>
          </div>
        ) : packages.map((pkg) => (
          <div key={pkg.id} className={`rounded-xl bg-white p-5 shadow-sm border ${pkg.enabled ? 'border-gray-100' : 'border-red-100 bg-red-50/30'}`}>
            <div className="flex items-start justify-between mb-3">
              <h3 className="font-medium text-gray-900">{pkg.name}</h3>
              <div className="flex gap-1">
                <button onClick={() => editPkg(pkg)} className="rounded p-1.5 text-gray-400 hover:bg-gray-50">
                  <Edit2 className="h-4 w-4" />
                </button>
                <button onClick={() => deletePkg(pkg.id)} className="rounded p-1.5 text-red-400 hover:bg-red-50">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
            {pkg.description && <p className="text-sm text-gray-500 mb-3">{pkg.description}</p>}
            <div className="space-y-1 text-sm">
              {pkg.destination_vpn_name && (
                <div className="flex justify-between">
                  <span className="text-gray-400">Destination</span>
                  <span className="inline-flex items-center rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700">{pkg.destination_vpn_name}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-gray-400">Traffic</span>
                <span>{pkg.bandwidth_limit ? formatBytes(pkg.bandwidth_limit) : 'Unlimited'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Speed</span>
                <span>{pkg.speed_limit ? `${pkg.speed_limit / 1000} Mbps` : 'Unlimited'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Duration</span>
                <span>{pkg.duration_days} days</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Connections</span>
                <span>{pkg.max_connections}</span>
              </div>
              {pkg.price && (
                <div className="flex justify-between font-medium pt-2 border-t mt-2">
                  <span>Price</span>
                  <span>{pkg.price.toLocaleString()} {pkg.currency}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
