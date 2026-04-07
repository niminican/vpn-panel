import toast from 'react-hot-toast'
import api from '../../api/client'

interface ProxyAccount {
  id: number; user_id: number; inbound_id: number; uuid: string | null; password: string | null
  email: string; enabled: boolean; inbound_tag: string | null; inbound_protocol: string | null; inbound_port: number | null
  outbound_id: number | null; outbound_tag: string | null; outbound_protocol: string | null
}

interface Props {
  userId: string
  proxyAccounts: ProxyAccount[]
  inbounds: any[]
  showAddProxy: boolean
  setShowAddProxy: (v: boolean) => void
  selectedInbound: string
  setSelectedInbound: (v: string) => void
  addProxyAccount: () => void
  deleteProxyAccount: (id: number) => void
  copyShareLink: (id: number) => void
  fetchProxyAccounts: () => void
  proxyLoaded: boolean
}

const protocolColor: Record<string, string> = {
  vless: 'bg-blue-100 text-blue-700',
  trojan: 'bg-purple-100 text-purple-700',
  shadowsocks: 'bg-yellow-100 text-yellow-700',
  http: 'bg-green-100 text-green-700',
  socks: 'bg-orange-100 text-orange-700',
}

export default function ProxyTab({
  proxyAccounts, inbounds, showAddProxy, setShowAddProxy, selectedInbound,
  setSelectedInbound, addProxyAccount, deleteProxyAccount, copyShareLink, fetchProxyAccounts, proxyLoaded,
}: Props) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Proxy Accounts</h3>
        <button onClick={() => { setShowAddProxy(true); if (!proxyLoaded) fetchProxyAccounts() }}
          className="flex items-center gap-1 bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-blue-700">+ Add</button>
      </div>

      {showAddProxy && (
        <div className="bg-gray-50 rounded-lg p-4 flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">Inbound</label>
            <select value={selectedInbound} onChange={e => setSelectedInbound(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm">
              <option value="">Select inbound...</option>
              {inbounds.filter((i: any) => i.enabled).map((i: any) => (
                <option key={i.id} value={i.id}>{i.tag} ({i.protocol.toUpperCase()} :{i.port})</option>
              ))}
            </select>
          </div>
          <button onClick={addProxyAccount} className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700">Create</button>
          <button onClick={() => setShowAddProxy(false)} className="text-gray-500 px-3 py-2 text-sm">Cancel</button>
        </div>
      )}

      {proxyAccounts.length === 0 && !showAddProxy && (
        <p className="text-gray-400 text-center py-8">No proxy accounts</p>
      )}

      <div className="space-y-3">
        {proxyAccounts.map((pa) => (
          <div key={pa.id} className="bg-white rounded-lg border p-4 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${protocolColor[pa.inbound_protocol || ''] || 'bg-gray-100 text-gray-700'}`}>
                  {(pa.inbound_protocol || '').toUpperCase()}
                </span>
                <span className="text-sm font-medium">{pa.inbound_tag}</span>
                <span className="text-xs text-gray-400">:{pa.inbound_port}</span>
                <span className={`px-1.5 py-0.5 rounded text-xs ${pa.enabled ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                  {pa.enabled ? 'Active' : 'Disabled'}
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-1 font-mono">{pa.uuid || pa.email}</p>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={() => copyShareLink(pa.id)} title="Copy share link" className="p-2 rounded hover:bg-gray-100 text-blue-600">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" /></svg>
              </button>
              <button onClick={() => deleteProxyAccount(pa.id)} title="Delete" className="p-2 rounded hover:bg-red-50 text-red-500">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" /></svg>
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
