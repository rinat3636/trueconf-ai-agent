import React, { useState, useEffect, useRef } from 'react'
import { Upload, BarChart3, Users, ShoppingBag, Lightbulb, Send, Package, Brain, Trash2 } from 'lucide-react'
import { api } from '../services/api'

export default function SalesPage() {
  const [reports, setReports] = useState([])
  const [selectedReport, setSelectedReport] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [managers, setManagers] = useState([])
  const [clients, setClients] = useState([])
  const [products, setProducts] = useState(null)
  const [recommendations, setRecommendations] = useState([])
  const [fullAnalysis, setFullAnalysis] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [uploading, setUploading] = useState(false)
  const [loadingAnalytics, setLoadingAnalytics] = useState(false)
  const [loadingRecs, setLoadingRecs] = useState(false)
  const [loadingFull, setLoadingFull] = useState(false)
  const [loadingProducts, setLoadingProducts] = useState(false)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [askLoading, setAskLoading] = useState(false)
  const [clientsPage, setClientsPage] = useState(1)
  const [productsPage, setProductsPage] = useState(1)
  const fileRef = useRef(null)
  const PAGE_SIZE = 50

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
    } catch (err) { alert('Ошибка загрузки') }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = '' }
  }

  const handleDeleteReport = async (id) => {
    if (!confirm('Удалить этот отчёт?')) return
    try {
      await api.deleteReport(id)
      if (selectedReport?.id === id) {
        setSelectedReport(null)
        setAnalytics(null)
      }
      loadReports()
    } catch (err) { alert('Ошибка удаления') }
  }

  const selectReport = async (report) => {
    setSelectedReport(report)
    setProducts(null)
    setRecommendations([])
    setFullAnalysis(null)
    setActiveTab('overview')
    if (report.status !== 'ready' && report.status !== 'processed') return
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

  const loadProducts = async () => {
    if (!selectedReport) return
    setLoadingProducts(true)
    try {
      const data = await api.getReportProducts(selectedReport.id)
      setProducts(data)
    } catch (err) { console.error(err) }
    finally { setLoadingProducts(false) }
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

  const loadFullAnalysis = async () => {
    if (!selectedReport) return
    setLoadingFull(true)
    try {
      const data = await api.getFullAnalysis(selectedReport.id)
      setFullAnalysis(data)
    } catch (err) { console.error(err) }
    finally { setLoadingFull(false) }
  }

  const handleAsk = async (e) => {
    e.preventDefault()
    if (!question.trim()) return
    setAskLoading(true)
    try {
      const data = await api.askAnalytics({ question, report_id: selectedReport?.id })
      setAnswer(data.answer)
    } catch (err) { setAnswer('Ошибка: ' + err.message) }
    finally { setAskLoading(false) }
  }

  const fmt = (n) => n != null ? n.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) : '-'
  const fmtPct = (n) => n != null ? n.toFixed(1) + '%' : '-'

  const statusLabel = (s) => {
    const map = { ready: 'Готов', processed: 'Обработан', processing: 'Обработка', error: 'Ошибка', pending: 'Ожидание' }
    return map[s] || s
  }

  return (
    <div>
      <div className="page-header">
        <h1>Аналитика продаж</h1>
        <p>Загрузка отчётов и ИИ-анализ данных</p>
      </div>

      <div style={{ display: 'flex', gap: '1.5rem' }}>
        <div style={{ width: '300px', flexShrink: 0 }}>
          <div className="card">
            <div className="card-header">
              <span className="card-title">Отчёты</span>
              <button className="btn btn-primary btn-sm" onClick={() => fileRef.current?.click()} disabled={uploading}>
                <Upload size={14} /> {uploading ? '...' : ''}
              </button>
              <input ref={fileRef} type="file" style={{ display: 'none' }} accept=".xlsx,.xls,.csv" onChange={handleUpload} />
            </div>
            {reports.map(r => (
              <div key={r.id} style={{
                padding: '0.75rem',
                cursor: 'pointer',
                borderBottom: '1px solid #e5e7eb',
                background: selectedReport?.id === r.id ? '#dbeafe' : 'white',
                display: 'flex', justifyContent: 'space-between', alignItems: 'start',
              }}>
                <div onClick={() => selectReport(r)} style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500, fontSize: '0.85rem' }}>{r.original_filename}</div>
                  <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                    {r.period_start} {r.period_end ? `- ${r.period_end}` : ''}
                  </div>
                  <span className={`badge badge-${r.status === 'ready' || r.status === 'processed' ? 'success' : r.status === 'error' ? 'danger' : 'warning'}`}>
                    {statusLabel(r.status)}
                  </span>
                </div>
                <button className="btn btn-danger btn-sm" onClick={(e) => { e.stopPropagation(); handleDeleteReport(r.id) }}
                  style={{ padding: '0.125rem 0.375rem' }}>
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
            {reports.length === 0 && <div className="empty-state"><p>Нет отчётов</p></div>}
          </div>
        </div>

        <div style={{ flex: 1 }}>
          {!selectedReport ? (
            <div className="card">
              <div className="empty-state">
                <BarChart3 size={48} color="#d1d5db" />
                <p>Выберите отчёт или загрузите новый</p>
              </div>
            </div>
          ) : loadingAnalytics ? (
            <div className="card"><div className="loading"><div className="spinner" /> Загрузка аналитики...</div></div>
          ) : analytics ? (
            <>
              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-label">Выручка</div>
                  <div className="stat-value">{fmt(analytics.total_revenue)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Прибыль</div>
                  <div className="stat-value">{fmt(analytics.total_profit)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Ср. маржа</div>
                  <div className="stat-value">{fmtPct(analytics.avg_margin)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">ТП</div>
                  <div className="stat-value">{analytics.manager_count}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Клиенты</div>
                  <div className="stat-value">{analytics.client_count}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Продукты</div>
                  <div className="stat-value">{analytics.product_count}</div>
                </div>
              </div>

              <div className="card">
                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                  {[
                    { key: 'overview', icon: BarChart3, label: 'Обзор' },
                    { key: 'managers', icon: Users, label: 'ТП' },
                    { key: 'clients', icon: ShoppingBag, label: 'Клиенты' },
                    { key: 'products', icon: Package, label: 'Продукты' },
                    { key: 'recommendations', icon: Lightbulb, label: 'Рекомендации' },
                    { key: 'full', icon: Brain, label: 'Полный анализ' },
                    { key: 'ask', icon: Send, label: 'Вопрос ИИ' },
                  ].map(tab => (
                    <button key={tab.key}
                      className={`btn ${activeTab === tab.key ? 'btn-primary' : 'btn-outline'} btn-sm`}
                      onClick={() => {
                        setActiveTab(tab.key)
                        if (tab.key === 'products' && !products) loadProducts()
                        if (tab.key === 'recommendations' && recommendations.length === 0) loadRecommendations()
                        if (tab.key === 'full' && !fullAnalysis) loadFullAnalysis()
                      }}>
                      <tab.icon size={14} /> {tab.label}
                    </button>
                  ))}
                </div>

                {activeTab === 'overview' && (
                  <div className="grid-2">
                    <div>
                      <h4 style={{ marginBottom: '0.5rem' }}>Лучшие ТП по прибыли</h4>
                      <table>
                        <thead><tr><th>Имя</th><th>Прибыль</th><th>Маржа</th></tr></thead>
                        <tbody>
                          {(analytics.top_managers || []).map((m, i) => (
                            <tr key={i}><td>{m.name}</td><td>{fmt(m.profit)}</td><td>{fmtPct(m.margin)}</td></tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div>
                      <h4 style={{ marginBottom: '0.5rem' }}>Слабые ТП (низкая маржа)</h4>
                      <table>
                        <thead><tr><th>Имя</th><th>Прибыль</th><th>Маржа</th></tr></thead>
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
                      <thead><tr><th>ТП</th><th>Выручка</th><th>Прибыль</th><th>Маржа</th><th>Клиенты</th><th>SKU</th></tr></thead>
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
                      <thead><tr><th>Клиент</th><th>ТП</th><th>Выручка</th><th>Прибыль</th><th>Маржа</th><th>SKU</th></tr></thead>
                      <tbody>
                        {clients.slice((clientsPage - 1) * PAGE_SIZE, clientsPage * PAGE_SIZE).map((c, i) => (
                          <tr key={i}>
                            <td>{c.name}</td><td>{c.manager}</td><td>{fmt(c.revenue)}</td>
                            <td>{fmt(c.profit)}</td><td>{fmtPct(c.margin)}</td><td>{c.sku_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {clients.length > PAGE_SIZE && (
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.75rem', fontSize: '0.85rem' }}>
                        <span style={{ color: '#6b7280' }}>
                          Показаны {(clientsPage - 1) * PAGE_SIZE + 1}–{Math.min(clientsPage * PAGE_SIZE, clients.length)} из {clients.length}
                        </span>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button
                            onClick={() => setClientsPage(p => Math.max(1, p - 1))}
                            disabled={clientsPage === 1}
                            style={{ padding: '0.25rem 0.75rem', borderRadius: '0.375rem', border: '1px solid #d1d5db', background: clientsPage === 1 ? '#f3f4f6' : '#fff', cursor: clientsPage === 1 ? 'not-allowed' : 'pointer' }}
                          >
                            ← Назад
                          </button>
                          <span style={{ padding: '0.25rem 0.5rem', color: '#374151' }}>
                            {clientsPage} / {Math.ceil(clients.length / PAGE_SIZE)}
                          </span>
                          <button
                            onClick={() => setClientsPage(p => Math.min(Math.ceil(clients.length / PAGE_SIZE), p + 1))}
                            disabled={clientsPage >= Math.ceil(clients.length / PAGE_SIZE)}
                            style={{ padding: '0.25rem 0.75rem', borderRadius: '0.375rem', border: '1px solid #d1d5db', background: clientsPage >= Math.ceil(clients.length / PAGE_SIZE) ? '#f3f4f6' : '#fff', cursor: clientsPage >= Math.ceil(clients.length / PAGE_SIZE) ? 'not-allowed' : 'pointer' }}
                          >
                            Вперёд →
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'products' && (
                  <div>
                    {loadingProducts ? (
                      <div className="loading"><div className="spinner" /> Загрузка продуктов...</div>
                    ) : !products ? (
                      <div className="empty-state"><p>Нажмите для загрузки анализа продуктов</p></div>
                    ) : (
                      <>
                        {products.sku_dependencies && products.sku_dependencies.length > 0 && (
                          <div style={{ marginBottom: '1rem', padding: '0.75rem', background: '#fef9c3', borderRadius: '0.5rem' }}>
                            <strong style={{ color: '#854d0e' }}>Зависимость от SKU:</strong>
                            <ul style={{ paddingLeft: '1.25rem', marginTop: '0.25rem' }}>
                              {products.sku_dependencies.map((d, i) => (
                                <li key={i} style={{ fontSize: '0.85rem' }}>
                                  {d.name} — {fmtPct(d.revenue_share_pct)} выручки
                                  <span className={`badge badge-${d.risk === 'high' ? 'danger' : 'warning'}`} style={{ marginLeft: '0.5rem' }}>
                                    {d.risk === 'high' ? 'Высокий риск' : 'Средний риск'}
                                  </span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {products.low_margin_products && products.low_margin_products.length > 0 && (
                          <div style={{ marginBottom: '1rem', padding: '0.75rem', background: '#fee2e2', borderRadius: '0.5rem' }}>
                            <strong style={{ color: '#991b1b' }}>Низкомаржинальные продукты:</strong>
                            <ul style={{ paddingLeft: '1.25rem', marginTop: '0.25rem' }}>
                              {products.low_margin_products.map((p, i) => (
                                <li key={i} style={{ fontSize: '0.85rem' }}>
                                  {p.name} — маржа {fmtPct(p.avg_margin)}, выручка {fmt(p.total_revenue)}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        <div className="table-wrapper">
                          <table>
                            <thead><tr><th>Продукт</th><th>Выручка</th><th>Прибыль</th><th>Тоннаж</th><th>Маржа</th><th>Доля</th></tr></thead>
                            <tbody>
                              {(products.products || []).slice((productsPage - 1) * PAGE_SIZE, productsPage * PAGE_SIZE).map((p, i) => (
                                <tr key={i}>
                                  <td>{p.name}</td><td>{fmt(p.total_revenue)}</td><td>{fmt(p.total_profit)}</td>
                                  <td>{p.total_tonnage?.toFixed(2) || '-'}</td><td>{fmtPct(p.avg_margin)}</td>
                                  <td>{fmtPct(p.revenue_share_pct)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        {(products.products || []).length > PAGE_SIZE && (
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.75rem', fontSize: '0.85rem' }}>
                            <span style={{ color: '#6b7280' }}>
                              Показаны {(productsPage - 1) * PAGE_SIZE + 1}–{Math.min(productsPage * PAGE_SIZE, (products.products || []).length)} из {(products.products || []).length}
                            </span>
                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                              <button
                                onClick={() => setProductsPage(p => Math.max(1, p - 1))}
                                disabled={productsPage === 1}
                                style={{ padding: '0.25rem 0.75rem', borderRadius: '0.375rem', border: '1px solid #d1d5db', background: productsPage === 1 ? '#f3f4f6' : '#fff', cursor: productsPage === 1 ? 'not-allowed' : 'pointer' }}
                              >
                                ← Назад
                              </button>
                              <span style={{ padding: '0.25rem 0.5rem', color: '#374151' }}>
                                {productsPage} / {Math.ceil((products.products || []).length / PAGE_SIZE)}
                              </span>
                              <button
                                onClick={() => setProductsPage(p => Math.min(Math.ceil((products.products || []).length / PAGE_SIZE), p + 1))}
                                disabled={productsPage >= Math.ceil((products.products || []).length / PAGE_SIZE)}
                                style={{ padding: '0.25rem 0.75rem', borderRadius: '0.375rem', border: '1px solid #d1d5db', background: productsPage >= Math.ceil((products.products || []).length / PAGE_SIZE) ? '#f3f4f6' : '#fff', cursor: productsPage >= Math.ceil((products.products || []).length / PAGE_SIZE) ? 'not-allowed' : 'pointer' }}
                              >
                                Вперёд →
                              </button>
                            </div>
                          </div>
                        )}
                        <p style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.5rem' }}>
                          Всего уникальных SKU: {products.total_unique_skus || 0}
                        </p>
                      </>
                    )}
                  </div>
                )}

                {activeTab === 'recommendations' && (
                  <div>
                    {loadingRecs ? (
                      <div className="loading"><div className="spinner" /> Генерация рекомендаций...</div>
                    ) : recommendations.length === 0 ? (
                      <div className="empty-state"><p>Нажмите для генерации рекомендаций ИИ</p></div>
                    ) : (
                      <ul style={{ paddingLeft: '1.5rem' }}>
                        {recommendations.map((r, i) => (
                          <li key={i} style={{ marginBottom: '0.75rem', lineHeight: '1.6' }}>{r}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                {activeTab === 'full' && (
                  <div>
                    {loadingFull ? (
                      <div className="loading"><div className="spinner" /> Генерация полного анализа...</div>
                    ) : !fullAnalysis ? (
                      <div className="empty-state"><p>Нажмите для генерации полного AI-анализа</p></div>
                    ) : (
                      <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.7', fontSize: '0.9rem' }}>
                        {fullAnalysis.detailed_analysis || fullAnalysis.overview || JSON.stringify(fullAnalysis, null, 2)}
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'ask' && (
                  <div>
                    <form onSubmit={handleAsk} style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem' }}>
                      <input className="form-control" value={question} onChange={e => setQuestion(e.target.value)}
                        placeholder="Задайте вопрос по данным продаж..." />
                      <button className="btn btn-primary" type="submit" disabled={askLoading}>
                        {askLoading ? '...' : 'Спросить'}
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
              <div className="empty-state"><p>Отчёт обрабатывается...</p></div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
