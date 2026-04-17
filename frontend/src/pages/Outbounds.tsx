import { useEffect, useState } from 'react'
import { Plus, Trash2, Power, X } from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../api/client'

interface Outbound {
  id: number; tag: string; protocol: string; server: string | null
  server_port: number | null; transport: string; security: string
  engine: string; enabled: boolean; created_at: string
}

const PROTOCOLS = ['direct', 'blackhole', 'vless', 'trojan', 'shadowsocks', 'wireguard', 'http', 'socks']

export default function Outbounds() {
  const [outbounds, setOutbounds] = useState<Outbound[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({
    tag: '', protocol: 'direct', server: '', server_port: '',
    uuid: '', password: '', engine: 'xray',
  })

  const fetchOutbounds = async () => {
    try {
      const res = await api.get('/outbounds')
      setOutbounds(res.data)
    } catch { toast.error('Failed to load outbounds') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchOutbounds() }, [])

  const handleCreate = async () => {
    if (!form.tag) { toast.error('Tag is required'); return }
    try {
      const data: any = { tag: form.tag, protocol: form.protocol, engine: form.engine }
      if (form.server) data.server = form.server
      if (form.server_port) data.server_port = parseInt(form.server_port)
      if (form.uuid) data.uuid = form.uuid
      if (form.password) data.password = form.password
      await api.post('/outbounds', data)
      toast.success('Outbound created')
      setShowCreate(false)
      setForm({ tag: '', protocol: 'direct', server: '', server_port: '', uuid: '', password: '', engine: 'xray' })
      fetchOutbounds()
    } catch (err: any) { toast.error(err.response?.data?.detail || 'Failed to create') }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this outbound?')) return
    try { await api.delete(`/outbounds/${id}`); toast.success('Deleted'); fetchOutbounds() }
    catch { toast.error('Failed to delete') }
  }

  const handleToggle = async (id: number) => {
    try { await api.post(`/outbounds/${id}/toggle`); fetchOutbounds() }
    catch { toast.error('Failed to toggle') }
  }

  const protocolColor: Record<string, string> = {
    direct: 'bg-green-100 text-green-700', blackhole: 'bg-gray-100 text-gray-700',
    vless: 'bg-blue-100 text-blue-700', trojan: 'bg-purple-100 text-purple-700',
    shadowsocks: 'bg-yellow-100 text-yellow-700', wireguard: 'bg-cyan-100 text-cyan-700',
    http: 'bg-emerald-100 text-emerald-700', socks: 'bg-orange-100 text-orange-700',
  }

  const needsServer = !['direct', 'blackhole'].includes(form.protocol)

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" /></div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Outbounds</h1>
        <button onClick={() => setShowCreate(true)} className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
          <Plus className="h-4 w-4" /> New Outbound
        </button>
      </div>

      {showCreate && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl p-6 w-full max-w-md space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">New Outbound</h2>
              <button onClick={() => setShowCreate(false)}><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Tag</label>
                <input value={form.tag} onChange={e => setForm({ ...form, tag: e.target.value })} placeholder="wg-germany" className="w-full border rounded-lg px-3 py-2 text-sm" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Protocol</label>
                  <select value={form.protocol} onChange={e => setForm({ ...form, protocol: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm">
                    {PROTOCOLS.map(p => <option key={p} value={p}>{p.toUpperCase()}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Engine</label>
                  <select value={form.engine} onChange={e => setForm({ ...form, engine: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm">
                    <option value="xray">xray</option>
                    <option value="singbox">singbox</option>
                  </select>
                </div>
              </div>
              {needsServer && (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Server</label>
                      <input value={form.server} onChange={e => setForm({ ...form, server: e.target.value })} placeholder="1.2.3.4" className="w-full border rounded-lg px-3 py-2 text-sm" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Port</label>
                      <input type="number" value={form.server_port} onChange={e => setForm({ ...form, server_port: e.target.value })} placeholder="443" className="w-full border rounded-lg px-3 py-2 text-sm" />
                    </div>
                  </div>
                  {['vless'].includes(form.protocol) && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">UUID</label>
                      <input value={form.uuid} onChange={e => setForm({ ...form, uuid: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm" />
                    </div>
                  )}
                  {['trojan', 'shadowsocks', 'http', 'socks'].includes(form.protocol) && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                      <input value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm" />
                    </div>
                  )}
                </>
              )}
            </div>
            <button onClick={handleCreate} className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 text-sm font-medium">Create Outbound</button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Tag</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Protocol</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Server</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Engine</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
              <th className="text-right px-4 py-3 font-medium text-gray-600">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {outbounds.map(ob => (
              <tr key={ob.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{ob.tag}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${protocolColor[ob.protocol] || 'bg-gray-100'}`}>
                    {ob.protocol.toUpperCase()}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-xs">{ob.server ? `${ob.server}:${ob.server_port}` : '-'}</td>
                <td className="px-4 py-3">{ob.engine}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs ${ob.enabled ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {ob.enabled ? 'Active' : 'Disabled'}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <button onClick={() => handleToggle(ob.id)} className="p-1.5 rounded hover:bg-gray-200">
                      <Power className={`h-4 w-4 ${ob.enabled ? 'text-green-600' : 'text-gray-400'}`} />
                    </button>
                    <button onClick={() => handleDelete(ob.id)} className="p-1.5 rounded hover:bg-red-50">
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {outbounds.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-12 text-center text-gray-400">No outbounds configured. Default is "direct" (traffic goes straight to internet).</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
