import { formatBytes, formatDate } from '../../lib/utils'

interface SessionEntry {
  id: number; user_id: number; endpoint: string | null; client_ip: string | null
  connected_at: string; disconnected_at: string | null; bytes_sent: number; bytes_received: number
  duration_seconds: number | null; country: string | null; country_code: string | null
  city: string | null; isp: string | null; asn: number | null; os_hint: string | null; ttl: number | null
}

interface VisitedEntry { dest_ip: string; dest_hostname: string | null; count: number; last_seen?: string }

interface Props {
  sessions: SessionEntry[]
  sessionsTotal: number
  sessionsPage: number
  setSessionsPage: (p: number) => void
  fetchSessions: (page?: number) => void
  expandedSession: number | null
  toggleSessionDetail: (id: number) => void
  sessionDetailLoading: boolean
  sessionVisited: VisitedEntry[]
  sessionBlocked: VisitedEntry[]
}

function getFlagEmoji(countryCode: string): string {
  const codePoints = countryCode.toUpperCase().split('').map(c => 0x1F1E6 + c.charCodeAt(0) - 65)
  return String.fromCodePoint(...codePoints)
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  const rm = m % 60
  if (h < 24) return `${h}h ${rm}m`
  const d = Math.floor(h / 24)
  const rh = h % 24
  return `${d}d ${rh}h`
}

export default function SessionsTab({
  sessions, sessionsTotal, sessionsPage, setSessionsPage, fetchSessions,
  expandedSession, toggleSessionDetail, sessionDetailLoading, sessionVisited, sessionBlocked,
}: Props) {
  if (sessions.length === 0) {
    return <div className="rounded-xl bg-white p-8 shadow-sm border border-gray-100 text-center text-gray-400">No sessions recorded yet.</div>
  }

  return (
    <div className="space-y-3">
      {sessions.map((s) => (
        <div key={s.id} className="rounded-xl bg-white shadow-sm border border-gray-100 p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              {!s.disconnected_at ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 text-green-700 px-2.5 py-0.5 text-xs font-medium">
                  <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" /> Active
                </span>
              ) : (
                <span className="rounded-full bg-gray-100 text-gray-500 px-2.5 py-0.5 text-xs font-medium">
                  {s.duration_seconds != null ? formatDuration(s.duration_seconds) : 'Ended'}
                </span>
              )}
              {s.os_hint && (
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  s.os_hint.includes('Windows') ? 'bg-blue-100 text-blue-700' :
                  s.os_hint.includes('Linux') || s.os_hint.includes('Android') ? 'bg-green-100 text-green-700' :
                  'bg-purple-100 text-purple-700'
                }`}>
                  {s.os_hint === 'Linux/Android/macOS' ? 'Linux/Android/Mac' : s.os_hint}
                </span>
              )}
            </div>
            <span className="text-xs text-gray-400">{formatDate(s.connected_at)}</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-x-4 gap-y-2 text-sm">
            {(s.country || s.city) && (
              <div>
                <p className="text-xs text-gray-400">Location</p>
                <p className="font-medium text-gray-700">
                  {s.country_code && <span className="mr-1">{getFlagEmoji(s.country_code)}</span>}
                  {[s.city, s.country].filter(Boolean).join(', ')}
                </p>
              </div>
            )}
            {s.isp && (
              <div>
                <p className="text-xs text-gray-400">ISP</p>
                <p className="font-medium text-gray-700 truncate" title={s.isp}>{s.isp}</p>
              </div>
            )}
            <div>
              <p className="text-xs text-gray-400">Client IP</p>
              <p className="font-mono text-xs text-gray-600">{s.client_ip || '-'}</p>
            </div>
            <div className="hidden sm:block">
              <p className="text-xs text-gray-400">Endpoint</p>
              <p className="font-mono text-xs text-gray-600 truncate" title={s.endpoint || ''}>{s.endpoint || '-'}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Download</p>
              <p className="font-medium text-green-600">{formatBytes(s.bytes_sent)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Upload</p>
              <p className="font-medium text-blue-600">{formatBytes(s.bytes_received)}</p>
            </div>
          </div>

          <div className="mt-3 pt-3 border-t border-gray-100">
            <button onClick={() => toggleSessionDetail(s.id)}
              className={`text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
                expandedSession === s.id ? 'bg-blue-100 text-blue-700' : 'bg-gray-50 text-gray-500 hover:bg-gray-100'
              }`}>
              {expandedSession === s.id ? 'Hide Details' : 'View Visited / Blocked'}
            </button>
          </div>

          {expandedSession === s.id && (
            <div className="mt-3 space-y-3">
              {sessionDetailLoading ? (
                <p className="text-sm text-gray-400 text-center py-4">Loading...</p>
              ) : (
                <>
                  <DetailTable title="Visited Destinations" items={sessionVisited} color="green" />
                  <DetailTable title="Blocked Requests" items={sessionBlocked} color="orange" />
                </>
              )}
            </div>
          )}
        </div>
      ))}

      {sessionsTotal > 50 && (
        <div className="flex items-center justify-between border-t px-4 py-3">
          <span className="text-sm text-gray-500">
            Showing {sessionsPage * 50 + 1}-{Math.min((sessionsPage + 1) * 50, sessionsTotal)} of {sessionsTotal}
          </span>
          <div className="flex gap-2">
            <button onClick={() => { setSessionsPage(Math.max(0, sessionsPage - 1)); fetchSessions(Math.max(0, sessionsPage - 1)) }}
              disabled={sessionsPage === 0} className="rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50 hover:bg-gray-50">Previous</button>
            <button onClick={() => { setSessionsPage(sessionsPage + 1); fetchSessions(sessionsPage + 1) }}
              disabled={(sessionsPage + 1) * 50 >= sessionsTotal} className="rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50 hover:bg-gray-50">Next</button>
          </div>
        </div>
      )}
    </div>
  )
}

function DetailTable({ title, items, color }: { title: string; items: VisitedEntry[]; color: 'green' | 'orange' }) {
  const bg = color === 'green' ? 'bg-green-50' : 'bg-orange-50'
  const border = color === 'green' ? 'border-green-200' : 'border-orange-200'
  const textColor = color === 'green' ? 'text-green-700' : 'text-orange-700'
  const emptyColor = color === 'green' ? 'text-green-600/60' : 'text-orange-600/60'

  return (
    <div className={`rounded-lg ${bg} p-3`}>
      <h4 className={`text-xs font-medium ${textColor} mb-2`}>{title} ({items.length})</h4>
      {items.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className={`border-b ${border} text-left ${textColor.replace('700', '600')}`}><th className="px-2 py-1">IP</th><th className="px-2 py-1">Hostname</th><th className="px-2 py-1">Count</th></tr></thead>
            <tbody>
              {items.map((v) => (
                <tr key={v.dest_hostname || v.dest_ip} className={`border-b ${border.replace('200', '100')} last:border-0`}>
                  <td className="px-2 py-1 font-mono">{v.dest_ip}</td>
                  <td className="px-2 py-1 text-gray-600 truncate max-w-[120px]" title={v.dest_hostname || ''}>{v.dest_hostname || '-'}</td>
                  <td className={`px-2 py-1 font-medium ${textColor}`}>{v.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className={`text-xs ${emptyColor}`}>No {title.toLowerCase()} in this session.</p>
      )}
    </div>
  )
}
