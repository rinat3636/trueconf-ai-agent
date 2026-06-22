import React, { useState, useEffect, useRef } from 'react'
import { Upload, BarChart3, Users, ShoppingBag, Lightbulb, Send } from 'lucide-react'
import { api } from '../services/api'

export default function SalesPage() {
  const [reports, setReports] = useState([])
  const [selectedReport, setSelectedReport] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [managers, setManagers] = useState([])
  const [clients, setClients] = useState([])
  const [recommendations, setRecommendations] = useState([])
  const [activeTab, setActiveTab] = useState('overview')
  const [uploading, setUploading] = useState(false)
  const [loadingAnalytics, setLoadingAnalytics] = useState(false)
  const [loadingRecs, setLoadingRecs] = useState(false)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [askLoading, setAskLoading] = useState(false)
  const fileRef = useRef(null)

  useEffect(() => { loadReports() }, [])

  const loadReports = async () => {
    try {
      const data = await api.getReports()
      setReports(data)
    } catch (err) { console.error(err) }
  }

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    try {
      await api.uploadReport(file, 'sales')
      loadReports()
    } catch (err) { alert('Upload failed') }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = '' }
  }

  const selectReport = async (report) => {
    setSelectedReport(report)
    if (report.status !== 'ready') return
    setLoadingAnalytics(true)
    try {
      const [a, m, c] = await Promise.all([
        api.getReportAnalytics(report.id),
        api.getReportManagers(report.id),
        api.getReportClients(report.id),
      ])
      setAnalytics(a)
      setManagers(m)
      setClients(c)
    } catch (err) { console.error(err) }
    finally { setLoadingAnalytics(false) }
  }

  const loadRecommendations = async () => {
    if (!selectedReport) return
    setLoadingRecs(true)
    try {
      const data = await api.getReportRecommendations(selectedReport.id)
      setRecommendations(data.recommendations || [])
    } catch (err) { console.error(err) }
    finally { setLoadingRecs(false) }
  }

  const handleAsk = async (e) => {
    e.preventDefault()
    if (!question.trim()) return
    setAskLoading(true)
    try {
      const data = await api.askAnalytics({ question, report_id: selectedReport?.id })
      setAnswer(data.answer)
    } catch (err) { setAnswer('Error: ' + err.message) }
    finally { setAskLoading(false) }
  }

  const fmt = (n) => n != null ? n.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) : '-'
  const fmtPct = (n) => n != null ? n.toFixed(1) + '%' : '-'

  return (
    <div>
      <div className="page-header">
        <h1>Sales Analytics</h1>
        <p>Upload sales reports and get AI-powered analysis</p>
      </div>

      <div style={{ display: 'flex', gap: '1.5rem' }}>
        <div style={{ width: '300px', flexShrink: 0 }}>
          <div className="card">
            <div className="card-header">
              <span className="card-title">Reports</span>
              <button className="btn btn-primary btn-sm" onClick={() => fileRef.current?.click()} disabled={uploading}>
                <Upload size={14} />
              </button>
              <input ref={fileRef} type="file" style={{ display: 'none' }} accept=".xlsx,.xls,.csv" onChange={handleUpload} />
            </div>
            {reports.map(r => (
              <div key={r.id}
                onClick={() => selectReport(r)}
                style={{
                  padding: '0.75rem',
                  cursor: 'pointer',
                  borderBottom: '1px solid #e5e7eb',
                  background: selectedReport?.id === r.id ? '#dbeafe' : 'white',
                }}>
                <div style={{ fontWeight: 500, fontSize: '0.85rem' }}>{r.original_filename}</div>
                <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                  {r.period_start} {r.period_end ? `- ${r.period_end}` : ''}
                </div>
                <span className={`badge badge-${r.status === 'ready' ? 'success' : r.status === 'error' ? 'danger' : 'warning'}`}>
                  {r.status}
                </span>
              </div>
            ))}
            {reports.length === 0 && <div className="empty-state"><p>No reports</p></div>}
          </div>
        </div>

        <div style={{ flex: 1 }}>
          {!selectedReport ? (
            <div className="card">
              <div className="empty-state">
                <BarChart3 size={48} color="#d1d5db" />
                <p>Select a report or upload one to see analytics</p>
              </div>
            </div>
          ) : loadingAnalytics ? (
            <div className="card"><div className="loading"><div className="spinner" /> Loading analytics...</div></div>
          ) : analytics ? (
            <>
              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-label">Revenue</div>
                  <div className="stat-value">{fmt(analytics.total_revenue)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Profit</div>
                  <div className="stat-value">{fmt(analytics.total_profit)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Avg Margin</div>
                  <div className="stat-value">{fmtPct(analytics.avg_margin)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Managers</div>
                  <div className="stat-value">{analytics.manager_count}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Clients</div>
                  <div className="stat-value">{analytics.client_count}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Products</div>
                  <div className="stat-value">{analytics.product_count}</div>
                </div>
              </div>

              <div className="card">
                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                  {[
                    { key: 'overview', icon: BarChart3, label: 'Overview' },
                    { key: 'managers', icon: Users, label: 'Managers' },
                    { key: 'clients', icon: ShoppingBag, label: 'Clients' },
                    { key: 'recommendations', icon: Lightbulb, label: 'AI Recommendations' },
                    { key: 'ask', icon: Send, label: 'Ask AI' },
                  ].map(tab => (
                    <button key={tab.key}
                      className={`btn ${activeTab === tab.key ? 'btn-primary' : 'btn-outline'} btn-sm`}
                      onClick={() => {
                        setActiveTab(tab.key)
                        if (tab.key === 'recommendations' && recommendations.length === 0) loadRecommendations()
                      }}>
                      <tab.icon size={14} /> {tab.label}
                    </button>
                  ))}
                </div>

                {activeTab === 'overview' && (
                  <div className="grid-2">
                    <div>
                      <h4 style={{ marginBottom: '0.5rem' }}>Top Managers by Profit</h4>
                      <table>
                        <thead><tr><th>Name</th><th>Profit</th><th>Margin</th></tr></thead>
                        <tbody>
                          {(analytics.top_managers || []).map((m, i) => (
                            <tr key={i}><td>{m.name}</td><td>{fmt(m.profit)}</td><td>{fmtPct(m.margin)}</td></tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div>
                      <h4 style={{ marginBottom: '0.5rem' }}>Low Margin Managers</h4>
                      <table>
                        <thead><tr><th>Name</th><th>Profit</th><th>Margin</th></tr></thead>
                        <tbody>
                          {(analytics.weak_managers || []).map((m, i) => (
                            <tr key={i}><td>{m.name}</td><td>{fmt(m.profit)}</td><td>{fmtPct(m.margin)}</td></tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {activeTab === 'managers' && (
                  <div className="table-wrapper">
                    <table>
                      <thead><tr><th>Manager</th><th>Revenue</th><th>Profit</th><th>Margin</th><th>Clients</th><th>SKUs</th></tr></thead>
                      <tbody>
                        {managers.map((m, i) => (
                          <tr key={i}>
                            <td>{m.name}</td><td>{fmt(m.revenue)}</td><td>{fmt(m.profit)}</td>
                            <td>{fmtPct(m.margin)}</td><td>{m.client_count}</td><td>{m.sku_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {activeTab === 'clients' && (
                  <div className="table-wrapper">
                    <table>
                      <thead><tr><th>Client</th><th>Manager</th><th>Revenue</th><th>Profit</th><th>Margin</th><th>SKUs</th></tr></thead>
                      <tbody>
                        {clients.slice(0, 50).map((c, i) => (
                          <tr key={i}>
                            <td>{c.name}</td><td>{c.manager}</td><td>{fmt(c.revenue)}</td>
                            <td>{fmt(c.profit)}</td><td>{fmtPct(c.margin)}</td><td>{c.sku_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {activeTab === 'recommendations' && (
                  <div>
                    {loadingRecs ? (
                      <div className="loading"><div className="spinner" /> Generating recommendations...</div>
                    ) : recommendations.length === 0 ? (
                      <div className="empty-state"><p>Click to generate AI recommendations</p></div>
                    ) : (
                      <ul style={{ paddingLeft: '1.5rem' }}>
                        {recommendations.map((r, i) => (
                          <li key={i} style={{ marginBottom: '0.75rem', lineHeight: '1.6' }}>{r}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                {activeTab === 'ask' && (
                  <div>
                    <form onSubmit={handleAsk} style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem' }}>
                      <input className="form-control" value={question} onChange={e => setQuestion(e.target.value)}
                        placeholder="Ask about sales data..." />
                      <button className="btn btn-primary" type="submit" disabled={askLoading}>
                        {askLoading ? '...' : 'Ask'}
                      </button>
                    </form>
                    {answer && (
                      <div style={{ background: '#f9fafb', padding: '1rem', borderRadius: '0.5rem', whiteSpace: 'pre-wrap' }}>
                        {answer}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="card">
              <div className="empty-state"><p>Report is still processing...</p></div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
