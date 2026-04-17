import { useEffect, useState } from 'react'
import { Plus, Trash2, Power, Copy, Edit2, X } from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../api/client'

interface Inbound {
  id: number
  tag: string
  protocol: string
  port: number
  listen: string
  transport: string
  security: string
  engine: string
  enabled: boolean
  user_count: number
  created_at: string
}

const PROTOCOLS = ['vless', 'trojan', 'shadowsocks', 'http', 'socks']
const TRANSPORTS = ['tcp', 'ws', 'grpc']
const SECURITIES = ['none', 'tls', 'reality']
const ENGINES = ['xray', 'singbox']

export default function Inbounds() {
  const [inbounds, setInbounds] = useState<Inbound[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({
    tag: '', protocol: 'vless', port: '', listen: '0.0.0.0',
    transport: 'tcp', security: 'none', engine: 'xray',
  })

  const fetchInbounds = async () => {
    try {
      const res = await api.get('/inbounds')
      setInbounds(res.data)
    } catch {
      toast.error('Failed to load inbounds')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchInbounds() }, [])

  const handleCreate = async () => {
    if (!form.tag || !form.port) {
      toast.error('Tag and port are required')
      return
    }
    try {
      await api.post('/inbounds', { ...form, port: parseInt(form.port) })
      toast.success('Inbound created')
      setShowCreate(false)
      setForm({ tag: '', protocol: 'vless', port: '', listen: '0.0.0.0', transport: 'tcp', security: 'none', engine: 'xray' })
      fetchInbounds()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create inbound')
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this inbound?')) return
    try {
      await api.delete(`/inbounds/${id}`)
      toast.success('Inbound deleted')
      fetchInbounds()
    } catch { toast.error('Failed to delete') }
  }

  const handleToggle = async (id: number) => {
    try {
      await api.post(`/inbounds/${id}/toggle`)
      fetchInbounds()
    } catch { toast.error('Failed to toggle') }
  }

  const protocolColor: Record<string, string> = {
    vless: 'bg-blue-100 text-blue-700',
    trojan: 'bg-purple-100 text-purple-700',
    shadowsocks: 'bg-yellow-100 text-yellow-700',
    http: 'bg-green-100 text-green-700',
    socks: 'bg-orange-100 text-orange-700',
  }

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" /></div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Inbounds</h1>
        <button onClick={() => setShowCreate(true)} className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
          <Plus className="h-4 w-4" /> New Inbound
        </button>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl p-6 w-full max-w-md space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">New Inbound</h2>
              <button onClick={() => setShowCreate(false)}><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Tag</label>
                <input value={form.tag} onChange={e => setForm({ ...form, tag: e.target.value })} placeholder="vless-tcp-reality" className="w-full border rounded-lg px-3 py-2 text-sm" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Protocol</label>
                  <select value={form.protocol} onChange={e => setForm({ ...form, protocol: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm">
                    {PROTOCOLS.map(p => <option key={p} value={p}>{p.toUpperCase()}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Port</label>
                  <input type="number" value={form.port} onChange={e => setForm({ ...form, port: e.target.value })} placeholder="443" className="w-full border rounded-lg px-3 py-2 text-sm" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Transport</label>
                  <select value={form.transport} onChange={e => setForm({ ...form, transport: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm">
                    {TRANSPORTS.map(t => <option key={t} value={t}>{t.toUpperCase()}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Security</label>
                  <select value={form.security} onChange={e => setForm({ ...form, security: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm">
                    {SECURITIES.map(s => <option key={s} value={s}>{s.toUpperCase()}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Engine</label>
                <select value={form.engine} onChange={e => setForm({ ...form, engine: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm">
                  {ENGINES.map(e => <option key={e} value={e}>{e}</option>)}
                </select>
              </div>
            </div>
            <button onClick={handleCreate} className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 text-sm font-medium">Create Inbound</button>
          </div>
        </div>
      )}

      {/* Inbounds Table */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Tag</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Protocol</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Port</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Transport</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Security</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Engine</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Users</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
              <th className="text-right px-4 py-3 font-medium text-gray-600">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {inbounds.map(inb => (
              <tr key={inb.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{inb.tag}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${protocolColor[inb.protocol] || 'bg-gray-100'}`}>
                    {inb.protocol.toUpperCase()}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono">{inb.port}</td>
                <td className="px-4 py-3">{inb.transport}</td>
                <td className="px-4 py-3">{inb.security}</td>
                <td className="px-4 py-3">{inb.engine}</td>
                <td className="px-4 py-3">{inb.user_count}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs ${inb.enabled ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {inb.enabled ? 'Active' : 'Disabled'}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <button onClick={() => handleToggle(inb.id)} title={inb.enabled ? 'Disable' : 'Enable'} className="p-1.5 rounded hover:bg-gray-200">
                      <Power className={`h-4 w-4 ${inb.enabled ? 'text-green-600' : 'text-gray-400'}`} />
                    </button>
                    <button onClick={() => handleDelete(inb.id)} title="Delete" className="p-1.5 rounded hover:bg-red-50">
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {inbounds.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-12 text-center text-gray-400">No inbounds configured</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
