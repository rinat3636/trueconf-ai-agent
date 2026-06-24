import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Upload, BarChart3, Users, ShoppingBag, Lightbulb, Send,
  Package, Brain, Trash2, GitCompare, RefreshCw, TrendingUp,
  TrendingDown, DollarSign, Percent, FileSpreadsheet, Clock,
  AlertTriangle, ChevronLeft, ChevronRight, Search, Download,
  ArrowUpRight, ArrowDownRight, Minus, Menu, X
} from 'lucide-react'
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
  const [compareReport, setCompareReport] = useState(null)
  const [comparison, setComparison] = useState(null)
  const [loadingCompare, setLoadingCompare] = useState(false)
  const [reindexing, setReindexing] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [managersSort, setManagersSort] = useState({ key: 'profit', dir: 'desc' })
  const [clientsSort, setClientsSort] = useState({ key: 'revenue', dir: 'desc' })
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const fileRef = useRef(null)
  const PAGE_SIZE = 50

  useEffect(() => { loadReports() }, [])

  const loadReports = async () => {
    try {
      const data = await api.getReports()
      setReports(data)
    } catch (err) { console.error(err) }
  }

  const handleUpload = async (file) => {
    if (!file) return
    const ext = file.name.split('.').pop().toLowerCase()
    if (!['xlsx', 'xls', 'csv'].includes(ext)) {
      alert('Поддерживаются только файлы .xlsx, .xls, .csv')
      return
    }
    setUploading(true)
    try {
      await api.uploadReport(file, 'sales')
      loadReports()
    } catch (err) { alert('Ошибка загрузки: ' + err.message) }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = '' }
  }

  const handleFileInput = (e) => {
    handleUpload(e.target.files[0])
  }

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleUpload(file)
  }, [])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setDragOver(false)
  }, [])

  const handleDeleteReport = async (id) => {
    if (!confirm('Удалить этот отчёт и все связанные данные?')) return
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
    setSidebarOpen(false)
    setProducts(null)
    setRecommendations([])
    setFullAnalysis(null)
    setComparison(null)
    setCompareReport(null)
    setActiveTab('overview')
    setClientsPage(1)
    setProductsPage(1)
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

  const loadComparison = async (prevId) => {
    if (!selectedReport || !prevId) return
    setLoadingCompare(true)
    try {
      const data = await api.compareReports(selectedReport.id, prevId)
      setComparison(data)
    } catch (err) { console.error(err); setComparison(null) }
    finally { setLoadingCompare(false) }
  }

  const handleReindex = async () => {
    if (!selectedReport) return
    setReindexing(true)
    try {
      await api.reindexReport(selectedReport.id)
      alert('Переиндексация запущена. Профили продаж будут обновлены в фоне.')
    } catch (err) { alert('Ошибка: ' + err.message) }
    finally { setReindexing(false) }
  }

  // Formatting helpers
  const fmt = (n) => {
    if (n == null) return '-'
    return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(n)
  }
  const fmtCurrency = (n) => {
    if (n == null) return '-'
    if (Math.abs(n) >= 1_000_000) {
      return (n / 1_000_000).toFixed(1).replace('.', ',') + ' млн'
    }
    if (Math.abs(n) >= 1_000) {
      return (n / 1_000).toFixed(0) + ' тыс'
    }
    return fmt(n)
  }
  const fmtPct = (n) => n != null ? n.toFixed(1) + '%' : '-'

  const statusConfig = {
    ready: { label: 'Готов', cls: 'success', icon: null },
    processed: { label: 'Обработан', cls: 'success', icon: null },
    processing: { label: 'Обработка...', cls: 'warning', icon: Clock },
    error: { label: 'Ошибка', cls: 'danger', icon: AlertTriangle },
    pending: { label: 'Ожидание', cls: 'warning', icon: Clock },
  }

  const getStatusBadge = (status) => {
    const cfg = statusConfig[status] || { label: status, cls: 'info' }
    return (
      <span className={`badge badge-${cfg.cls}`} style={{ fontSize: '0.7rem' }}>
        {cfg.icon && React.createElement(cfg.icon, { size: 10, style: { marginRight: 3 } })}
        {cfg.label}
      </span>
    )
  }

  const ChangeIndicator = ({ value, suffix = '' }) => {
    if (value == null) return <span style={{ color: '#9ca3af' }}>-</span>
    const color = value > 0 ? '#16a34a' : value < 0 ? '#dc2626' : '#6b7280'
    const Icon = value > 0 ? ArrowUpRight : value < 0 ? ArrowDownRight : Minus
    return (
      <span style={{ color, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 2 }}>
        <Icon size={14} />
        {value > 0 ? '+' : ''}{fmt(value)}{suffix}
      </span>
    )
  }

  // Sort helpers
  const sortedManagers = [...managers].sort((a, b) => {
    const v = managersSort.dir === 'asc' ? 1 : -1
    return ((a[managersSort.key] || 0) - (b[managersSort.key] || 0)) * v
  })

  const sortedClients = [...clients].sort((a, b) => {
    const v = clientsSort.dir === 'asc' ? 1 : -1
    return ((a[clientsSort.key] || 0) - (b[clientsSort.key] || 0)) * v
  })

  const SortHeader = ({ label, sortKey, sortState, setSortState }) => (
    <th
      style={{ cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap' }}
      onClick={() => setSortState(prev =>
        prev.key === sortKey
          ? { key: sortKey, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
          : { key: sortKey, dir: 'desc' }
      )}
    >
      {label}
      {sortState.key === sortKey && (
        <span style={{ marginLeft: 4, fontSize: '0.7rem' }}>
          {sortState.dir === 'asc' ? '▲' : '▼'}
        </span>
      )}
    </th>
  )

  const Pagination = ({ page, setPage, total, pageSize }) => {
    const totalPages = Math.ceil(total / pageSize)
    if (totalPages <= 1) return null
    return (
      <div className="sales-pagination">
        <span style={{ color: '#6b7280', fontSize: '0.8rem' }}>
          {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} из {total}
        </span>
        <div style={{ display: 'flex', gap: '0.25rem' }}>
          <button
            className="btn btn-outline btn-sm"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            <ChevronLeft size={14} />
          </button>
          <span style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem', color: '#374151', display: 'flex', alignItems: 'center' }}>
            {page} / {totalPages}
          </span>
          <button
            className="btn btn-outline btn-sm"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    )
  }

  const TABS = [
    { key: 'overview', icon: BarChart3, label: 'Обзор', shortLabel: 'Обзор' },
    { key: 'managers', icon: Users, label: 'ТП', shortLabel: 'ТП' },
    { key: 'clients', icon: ShoppingBag, label: 'Клиенты', shortLabel: 'Клиенты' },
    { key: 'products', icon: Package, label: 'Продукты', shortLabel: 'Продукты' },
    { key: 'compare', icon: GitCompare, label: 'Сравнение', shortLabel: 'Сравн.' },
    { key: 'recommendations', icon: Lightbulb, label: 'Рекомендации', shortLabel: 'Рек.' },
    { key: 'full', icon: Brain, label: 'ИИ-анализ', shortLabel: 'Анализ' },
    { key: 'ask', icon: Send, label: 'Вопрос ИИ', shortLabel: 'ИИ' },
  ]

  const QUICK_QUESTIONS = [
    'Кто лучший ТП по прибыли?',
    'Какие клиенты приносят больше всего выручки?',
    'Какие продукты самые маржинальные?',
    'Какие ТП показали худшую динамику?',
    'Сколько всего уникальных SKU?',
  ]

  return (
    <div className="sales-page">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <BarChart3 size={24} style={{ color: '#2563eb' }} />
            Аналитика продаж
          </h1>
          <p>Загрузка отчётов, ИИ-анализ данных и рекомендации</p>
        </div>
        <button
          className="sales-sidebar-toggle"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          title="Показать/скрыть панель отчётов"
        >
          {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      <div className="sales-layout">
        {/* LEFT SIDEBAR: Reports */}
        {sidebarOpen && <div className="sales-overlay" onClick={() => setSidebarOpen(false)} />}
        <div className={`sales-sidebar ${sidebarOpen ? 'open' : ''}`}>
          {/* Upload Area */}
          <div
            className={`sales-upload-area ${dragOver ? 'drag-over' : ''}`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileRef.current?.click()}
          >
            <Upload size={28} color={dragOver ? '#2563eb' : '#9ca3af'} />
            <div style={{ fontSize: '0.85rem', fontWeight: 500, color: '#374151', marginTop: '0.5rem' }}>
              {uploading ? 'Загрузка...' : 'Загрузить отчёт'}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>
              Перетащите файл или нажмите для выбора
            </div>
            <div style={{ fontSize: '0.7rem', color: '#d1d5db', marginTop: '0.25rem' }}>
              .xlsx, .xls, .csv
            </div>
            <input ref={fileRef} type="file" style={{ display: 'none' }} accept=".xlsx,.xls,.csv" onChange={handleFileInput} />
          </div>

          {/* Reports List */}
          <div className="card" style={{ padding: 0, marginTop: '1rem' }}>
            <div className="sales-report-list-header">
              <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                <FileSpreadsheet size={16} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                Отчёты ({reports.length})
              </span>
            </div>
            <div style={{ maxHeight: '500px', overflowY: 'auto' }}>
              {reports.map(r => (
                <div
                  key={r.id}
                  className={`sales-report-item ${selectedReport?.id === r.id ? 'active' : ''}`}
                >
                  <div onClick={() => selectReport(r)} style={{ flex: 1, cursor: 'pointer' }}>
                    <div style={{ fontWeight: 500, fontSize: '0.85rem', color: '#1f2937' }}>
                      {r.original_filename}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.25rem' }}>
                      {getStatusBadge(r.status)}
                      {r.period_start && (
                        <span style={{ fontSize: '0.7rem', color: '#6b7280' }}>
                          {r.period_start}{r.period_end ? ` — ${r.period_end}` : ''}
                        </span>
                      )}
                    </div>
                    {r.total_revenue && (
                      <div style={{ fontSize: '0.75rem', color: '#2563eb', fontWeight: 500, marginTop: '0.25rem' }}>
                        {fmtCurrency(r.total_revenue)} руб.
                      </div>
                    )}
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteReport(r.id) }}
                    className="sales-delete-btn"
                    title="Удалить отчёт"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
              {reports.length === 0 && (
                <div style={{ padding: '2rem', textAlign: 'center', color: '#9ca3af' }}>
                  <FileSpreadsheet size={32} style={{ opacity: 0.3, marginBottom: '0.5rem' }} />
                  <p style={{ fontSize: '0.85rem' }}>Нет загруженных отчётов</p>
                  <p style={{ fontSize: '0.75rem' }}>Загрузите Excel/CSV файл с данными продаж</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* MAIN CONTENT */}
        <div className="sales-main">
          {!selectedReport ? (
            <div className="card" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
              <BarChart3 size={56} color="#d1d5db" style={{ margin: '0 auto 1rem' }} />
              <h3 style={{ color: '#6b7280', fontWeight: 500, marginBottom: '0.5rem' }}>Выберите отчёт для анализа</h3>
              <p style={{ color: '#9ca3af', fontSize: '0.9rem' }}>
                Загрузите новый отчёт или выберите существующий из списка слева
              </p>
            </div>
          ) : loadingAnalytics ? (
            <div className="card">
              <div className="loading"><div className="spinner" /> Загрузка аналитики...</div>
            </div>
          ) : analytics ? (
            <>
              {/* KPI Cards */}
              <div className="sales-kpi-grid">
                {[
                  { color: '#2563eb', bg: '#eff6ff', icon: DollarSign, label: 'Выручка', value: fmtCurrency(analytics.total_revenue), unit: 'руб.' },
                  { color: '#16a34a', bg: '#f0fdf4', icon: TrendingUp, label: 'Прибыль', value: fmtCurrency(analytics.total_profit), unit: 'руб.', valueColor: '#16a34a' },
                  { color: '#7c3aed', bg: '#f5f3ff', icon: Percent, label: 'Маржа', value: fmtPct(analytics.avg_margin), valueColor: '#7c3aed' },
                  { color: '#ea580c', bg: '#fff7ed', icon: Users, label: 'ТП', value: analytics.manager_count },
                  { color: '#0891b2', bg: '#ecfeff', icon: ShoppingBag, label: 'Клиенты', value: fmt(analytics.client_count) },
                  { color: '#ca8a04', bg: '#fefce8', icon: Package, label: 'SKU', value: fmt(analytics.product_count) },
                ].map((kpi, idx) => (
                  <div key={idx} className="sales-kpi-card" style={{ borderTop: `3px solid ${kpi.color}` }}>
                    <div className="sales-kpi-icon" style={{ background: kpi.bg }}>
                      <kpi.icon size={18} color={kpi.color} />
                    </div>
                    <div>
                      <div className="sales-kpi-label">{kpi.label}</div>
                      <div className="sales-kpi-value" style={kpi.valueColor ? { color: kpi.valueColor } : {}}>
                        {kpi.value}{kpi.unit && <span className="sales-kpi-unit"> {kpi.unit}</span>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Tabs */}
              <div className="card" style={{ padding: 0 }}>
                <div className="sales-tab-bar">
                  {TABS.map(tab => (
                    <button
                      key={tab.key}
                      className={`sales-tab ${activeTab === tab.key ? 'active' : ''}`}
                      onClick={() => {
                        setActiveTab(tab.key)
                        if (tab.key === 'products' && !products) loadProducts()
                        if (tab.key === 'recommendations' && recommendations.length === 0) loadRecommendations()
                        if (tab.key === 'full' && !fullAnalysis) loadFullAnalysis()
                      }}
                      title={tab.label}
                    >
                      <tab.icon size={14} />
                      <span className="sales-tab-label">{tab.label}</span>
                    </button>
                  ))}
                </div>

                <div style={{ padding: '1.25rem' }}>

                  {/* OVERVIEW TAB */}
                  {activeTab === 'overview' && (
                    <div className="grid-2">
                      <div>
                        <h4 className="sales-section-title">
                          <TrendingUp size={16} color="#16a34a" /> Лучшие ТП по прибыли
                        </h4>
                        <div className="table-wrapper">
                          <table>
                            <thead>
                              <tr><th>Имя</th><th style={{ textAlign: 'right' }}>Прибыль</th><th style={{ textAlign: 'right' }}>Маржа</th></tr>
                            </thead>
                            <tbody>
                              {(analytics.top_managers || []).map((m, i) => (
                                <tr key={i}>
                                  <td style={{ fontWeight: 500 }}>
                                    <span className="sales-rank-badge">{i + 1}</span>
                                    {m.name}
                                  </td>
                                  <td style={{ textAlign: 'right', fontWeight: 500, color: '#16a34a' }}>{fmt(m.profit)}</td>
                                  <td style={{ textAlign: 'right' }}>{fmtPct(m.margin)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                      <div>
                        <h4 className="sales-section-title">
                          <TrendingDown size={16} color="#dc2626" /> Слабые ТП (низкая маржа)
                        </h4>
                        <div className="table-wrapper">
                          <table>
                            <thead>
                              <tr><th>Имя</th><th style={{ textAlign: 'right' }}>Прибыль</th><th style={{ textAlign: 'right' }}>Маржа</th></tr>
                            </thead>
                            <tbody>
                              {(analytics.weak_managers || []).map((m, i) => (
                                <tr key={i}>
                                  <td style={{ fontWeight: 500 }}>{m.name}</td>
                                  <td style={{ textAlign: 'right', color: '#dc2626' }}>{fmt(m.profit)}</td>
                                  <td style={{ textAlign: 'right', color: '#dc2626', fontWeight: 500 }}>{fmtPct(m.margin)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* MANAGERS TAB */}
                  {activeTab === 'managers' && (
                    <div>
                      <div style={{ marginBottom: '0.75rem', fontSize: '0.8rem', color: '#6b7280' }}>
                        Всего торговых представителей: <strong>{managers.length}</strong>. Нажмите на заголовок для сортировки.
                      </div>
                      <div className="table-wrapper">
                        <table>
                          <thead>
                            <tr>
                              <th>ТП</th>
                              <SortHeader label="Выручка" sortKey="revenue" sortState={managersSort} setSortState={setManagersSort} />
                              <SortHeader label="Прибыль" sortKey="profit" sortState={managersSort} setSortState={setManagersSort} />
                              <SortHeader label="Маржа" sortKey="margin" sortState={managersSort} setSortState={setManagersSort} />
                              <SortHeader label="Клиенты" sortKey="client_count" sortState={managersSort} setSortState={setManagersSort} />
                              <SortHeader label="SKU" sortKey="sku_count" sortState={managersSort} setSortState={setManagersSort} />
                            </tr>
                          </thead>
                          <tbody>
                            {sortedManagers.map((m, i) => (
                              <tr key={i}>
                                <td style={{ fontWeight: 500 }}>{m.name}</td>
                                <td style={{ textAlign: 'right' }}>{fmt(m.revenue)}</td>
                                <td style={{ textAlign: 'right', color: (m.profit || 0) >= 0 ? '#16a34a' : '#dc2626', fontWeight: 500 }}>{fmt(m.profit)}</td>
                                <td style={{ textAlign: 'right' }}>{fmtPct(m.margin)}</td>
                                <td style={{ textAlign: 'right' }}>{m.client_count}</td>
                                <td style={{ textAlign: 'right' }}>{m.sku_count}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* CLIENTS TAB */}
                  {activeTab === 'clients' && (
                    <div>
                      <div style={{ marginBottom: '0.75rem', fontSize: '0.8rem', color: '#6b7280' }}>
                        Всего клиентов: <strong>{clients.length}</strong>
                      </div>
                      <div className="table-wrapper">
                        <table>
                          <thead>
                            <tr>
                              <th>Клиент</th>
                              <th>ТП</th>
                              <SortHeader label="Выручка" sortKey="revenue" sortState={clientsSort} setSortState={setClientsSort} />
                              <SortHeader label="Прибыль" sortKey="profit" sortState={clientsSort} setSortState={setClientsSort} />
                              <SortHeader label="Маржа" sortKey="margin" sortState={clientsSort} setSortState={setClientsSort} />
                              <SortHeader label="SKU" sortKey="sku_count" sortState={clientsSort} setSortState={setClientsSort} />
                            </tr>
                          </thead>
                          <tbody>
                            {sortedClients.slice((clientsPage - 1) * PAGE_SIZE, clientsPage * PAGE_SIZE).map((c, i) => (
                              <tr key={i}>
                                <td style={{ fontWeight: 500 }}>{c.name}</td>
                                <td style={{ color: '#6b7280' }}>{c.manager}</td>
                                <td style={{ textAlign: 'right' }}>{fmt(c.revenue)}</td>
                                <td style={{ textAlign: 'right', color: (c.profit || 0) >= 0 ? '#16a34a' : '#dc2626', fontWeight: 500 }}>{fmt(c.profit)}</td>
                                <td style={{ textAlign: 'right' }}>{fmtPct(c.margin)}</td>
                                <td style={{ textAlign: 'right' }}>{c.sku_count}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <Pagination page={clientsPage} setPage={setClientsPage} total={clients.length} pageSize={PAGE_SIZE} />
                    </div>
                  )}

                  {/* PRODUCTS TAB */}
                  {activeTab === 'products' && (
                    <div>
                      {loadingProducts ? (
                        <div className="loading"><div className="spinner" /> Загрузка продуктов...</div>
                      ) : !products ? (
                        <div style={{ textAlign: 'center', padding: '2rem' }}>
                          <Package size={40} color="#d1d5db" />
                          <p style={{ color: '#9ca3af', marginTop: '0.5rem' }}>Нажмите вкладку для загрузки анализа продуктов</p>
                        </div>
                      ) : (
                        <>
                          {products.sku_dependencies && products.sku_dependencies.length > 0 && (
                            <div className="sales-alert-warning">
                              <AlertTriangle size={16} color="#854d0e" />
                              <div>
                                <strong>Зависимость от SKU</strong>
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
                            </div>
                          )}
                          {products.low_margin_products && products.low_margin_products.length > 0 && (
                            <div className="sales-alert-danger">
                              <TrendingDown size={16} color="#991b1b" />
                              <div>
                                <strong>Низкомаржинальные продукты</strong>
                                <ul style={{ paddingLeft: '1.25rem', marginTop: '0.25rem' }}>
                                  {products.low_margin_products.map((p, i) => (
                                    <li key={i} style={{ fontSize: '0.85rem' }}>
                                      {p.name} — маржа {fmtPct(p.avg_margin)}, выручка {fmt(p.total_revenue)}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            </div>
                          )}
                          <div className="table-wrapper">
                            <table>
                              <thead>
                                <tr>
                                  <th>Продукт</th>
                                  <th style={{ textAlign: 'right' }}>Выручка</th>
                                  <th style={{ textAlign: 'right' }}>Прибыль</th>
                                  <th style={{ textAlign: 'right' }}>Тоннаж</th>
                                  <th style={{ textAlign: 'right' }}>Маржа</th>
                                  <th style={{ textAlign: 'right' }}>Доля</th>
                                </tr>
                              </thead>
                              <tbody>
                                {(products.products || []).slice((productsPage - 1) * PAGE_SIZE, productsPage * PAGE_SIZE).map((p, i) => (
                                  <tr key={i}>
                                    <td style={{ fontWeight: 500 }}>{p.name}</td>
                                    <td style={{ textAlign: 'right' }}>{fmt(p.total_revenue)}</td>
                                    <td style={{ textAlign: 'right', color: (p.total_profit || 0) >= 0 ? '#16a34a' : '#dc2626', fontWeight: 500 }}>{fmt(p.total_profit)}</td>
                                    <td style={{ textAlign: 'right' }}>{p.total_tonnage?.toFixed(2) || '-'}</td>
                                    <td style={{ textAlign: 'right' }}>{fmtPct(p.avg_margin)}</td>
                                    <td style={{ textAlign: 'right' }}>{fmtPct(p.revenue_share_pct)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          <Pagination page={productsPage} setPage={setProductsPage} total={(products.products || []).length} pageSize={PAGE_SIZE} />
                          <p style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.5rem' }}>
                            Всего уникальных SKU: <strong>{products.total_unique_skus || 0}</strong>
                          </p>
                        </>
                      )}
                    </div>
                  )}

                  {/* COMPARE TAB */}
                  {activeTab === 'compare' && (
                    <div>
                      {reports.filter(r => r.id !== selectedReport?.id && (r.status === 'processed' || r.status === 'ready')).length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '2rem' }}>
                          <GitCompare size={40} color="#d1d5db" />
                          <p style={{ color: '#9ca3af', marginTop: '0.5rem' }}>Загрузите второй отчёт для сравнения периодов</p>
                        </div>
                      ) : (
                        <>
                          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
                            <label style={{ fontWeight: 500, fontSize: '0.85rem', color: '#374151' }}>Сравнить с:</label>
                            <select
                              className="form-control"
                              style={{ maxWidth: '350px' }}
                              value={compareReport || ''}
                              onChange={e => {
                                const id = parseInt(e.target.value)
                                setCompareReport(id)
                                if (id) loadComparison(id)
                              }}
                            >
                              <option value="">Выберите отчёт для сравнения</option>
                              {reports.filter(r => r.id !== selectedReport?.id && (r.status === 'processed' || r.status === 'ready')).map(r => (
                                <option key={r.id} value={r.id}>{r.original_filename} ({r.period_start || 'нет периода'})</option>
                              ))}
                            </select>
                            <button className="btn btn-outline btn-sm" onClick={handleReindex} disabled={reindexing} title="Переиндексация профилей продаж в Qdrant">
                              <RefreshCw size={14} /> {reindexing ? 'Переиндексация...' : 'Переиндексировать'}
                            </button>
                          </div>

                          {loadingCompare ? (
                            <div className="loading"><div className="spinner" /> Сравнение отчётов...</div>
                          ) : comparison ? (
                            <>
                              <div className="sales-kpi-grid">
                                <div className="sales-kpi-card" style={{ borderTop: `3px solid ${(comparison.overview.revenue_change || 0) >= 0 ? '#16a34a' : '#dc2626'}` }}>
                                  <div className="sales-kpi-label">Выручка (изм.)</div>
                                  <ChangeIndicator value={comparison.overview.revenue_change} />
                                </div>
                                <div className="sales-kpi-card" style={{ borderTop: `3px solid ${(comparison.overview.profit_change || 0) >= 0 ? '#16a34a' : '#dc2626'}` }}>
                                  <div className="sales-kpi-label">Прибыль (изм.)</div>
                                  <ChangeIndicator value={comparison.overview.profit_change} />
                                </div>
                                <div className="sales-kpi-card" style={{ borderTop: '3px solid #16a34a' }}>
                                  <div className="sales-kpi-label">Новые клиенты</div>
                                  <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#16a34a' }}>+{comparison.new_clients_count}</div>
                                </div>
                                <div className="sales-kpi-card" style={{ borderTop: '3px solid #dc2626' }}>
                                  <div className="sales-kpi-label">Потерянные клиенты</div>
                                  <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#dc2626' }}>-{comparison.lost_clients_count}</div>
                                </div>
                              </div>

                              <h4 className="sales-section-title">Изменения по ТП</h4>
                              <div className="table-wrapper">
                                <table>
                                  <thead>
                                    <tr>
                                      <th>ТП</th>
                                      <th style={{ textAlign: 'right' }}>Выручка (тек.)</th>
                                      <th style={{ textAlign: 'right' }}>Выручка (пред.)</th>
                                      <th style={{ textAlign: 'right' }}>Изменение</th>
                                      <th>Статус</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {(comparison.rep_changes || []).map((r, i) => (
                                      <tr key={i}>
                                        <td style={{ fontWeight: 500 }}>{r.name}</td>
                                        <td style={{ textAlign: 'right' }}>{fmt(r.revenue_current)}</td>
                                        <td style={{ textAlign: 'right', color: '#6b7280' }}>{fmt(r.revenue_previous)}</td>
                                        <td style={{ textAlign: 'right' }}>
                                          <ChangeIndicator value={r.revenue_change} />
                                          {r.revenue_change_pct != null && (
                                            <span style={{ fontSize: '0.75rem', color: '#6b7280', marginLeft: 4 }}>
                                              ({r.revenue_change_pct >= 0 ? '+' : ''}{r.revenue_change_pct.toFixed(1)}%)
                                            </span>
                                          )}
                                        </td>
                                        <td>
                                          <span className={`badge badge-${r.status === 'new' ? 'success' : r.status === 'lost' ? 'danger' : 'info'}`}>
                                            {r.status === 'new' ? 'Новый' : r.status === 'lost' ? 'Ушёл' : 'Активный'}
                                          </span>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>

                              {comparison.new_products && comparison.new_products.length > 0 && (
                                <div style={{ marginTop: '1rem' }}>
                                  <h4 className="sales-section-title">Новые продукты ({comparison.new_products_count})</h4>
                                  <div style={{ fontSize: '0.85rem', color: '#16a34a', lineHeight: 1.8 }}>
                                    {comparison.new_products.join(', ')}
                                  </div>
                                </div>
                              )}
                              {comparison.lost_products && comparison.lost_products.length > 0 && (
                                <div style={{ marginTop: '0.75rem' }}>
                                  <h4 className="sales-section-title">Потерянные продукты ({comparison.lost_products_count})</h4>
                                  <div style={{ fontSize: '0.85rem', color: '#dc2626', lineHeight: 1.8 }}>
                                    {comparison.lost_products.join(', ')}
                                  </div>
                                </div>
                              )}
                            </>
                          ) : null}
                        </>
                      )}
                    </div>
                  )}

                  {/* RECOMMENDATIONS TAB */}
                  {activeTab === 'recommendations' && (
                    <div>
                      {loadingRecs ? (
                        <div className="loading"><div className="spinner" /> Генерация ИИ-рекомендаций...</div>
                      ) : recommendations.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '2rem' }}>
                          <Lightbulb size={40} color="#d1d5db" />
                          <p style={{ color: '#9ca3af', marginTop: '0.5rem' }}>Переключитесь на эту вкладку для генерации рекомендаций</p>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                          {recommendations.map((r, i) => (
                            <div key={i} className="sales-rec-card">
                              <div className="sales-rec-num">{i + 1}</div>
                              <div style={{ flex: 1, lineHeight: 1.7, fontSize: '0.9rem' }}>{r}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* FULL ANALYSIS TAB */}
                  {activeTab === 'full' && (
                    <div>
                      {loadingFull ? (
                        <div className="loading"><div className="spinner" /> Генерация полного ИИ-анализа... Это может занять 30-60 секунд.</div>
                      ) : !fullAnalysis ? (
                        <div style={{ textAlign: 'center', padding: '2rem' }}>
                          <Brain size={40} color="#d1d5db" />
                          <p style={{ color: '#9ca3af', marginTop: '0.5rem' }}>Переключитесь на эту вкладку для генерации полного анализа</p>
                        </div>
                      ) : (
                        <div style={{
                          whiteSpace: 'pre-wrap',
                          lineHeight: 1.8,
                          fontSize: '0.9rem',
                          color: '#1f2937',
                          background: '#f9fafb',
                          padding: '1.5rem',
                          borderRadius: '0.75rem',
                          border: '1px solid #e5e7eb',
                        }}>
                          {fullAnalysis.detailed_analysis || fullAnalysis.overview || JSON.stringify(fullAnalysis, null, 2)}
                        </div>
                      )}
                    </div>
                  )}

                  {/* ASK AI TAB */}
                  {activeTab === 'ask' && (
                    <div>
                      <div style={{ marginBottom: '1rem' }}>
                        <h4 className="sales-section-title">
                          <Search size={16} color="#2563eb" /> Задайте вопрос по данным продаж
                        </h4>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
                          {QUICK_QUESTIONS.map((q, i) => (
                            <button
                              key={i}
                              className="btn btn-outline btn-sm"
                              style={{ fontSize: '0.75rem', borderRadius: '2rem' }}
                              onClick={() => { setQuestion(q); }}
                            >
                              {q}
                            </button>
                          ))}
                        </div>
                        <form onSubmit={handleAsk} style={{ display: 'flex', gap: '0.75rem' }}>
                          <input
                            className="form-control"
                            value={question}
                            onChange={e => setQuestion(e.target.value)}
                            placeholder="Например: Какой ТП показал лучшую динамику по марже?"
                            style={{ flex: 1 }}
                          />
                          <button className="btn btn-primary" type="submit" disabled={askLoading || !question.trim()}>
                            {askLoading ? (
                              <><div className="spinner" style={{ width: 16, height: 16, borderWidth: 2, marginRight: 4 }} /> Анализ...</>
                            ) : (
                              <><Send size={15} /> Спросить</>
                            )}
                          </button>
                        </form>
                      </div>
                      {answer && (
                        <div style={{
                          background: '#f9fafb',
                          padding: '1.25rem',
                          borderRadius: '0.75rem',
                          border: '1px solid #e5e7eb',
                          whiteSpace: 'pre-wrap',
                          lineHeight: 1.7,
                          fontSize: '0.9rem',
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: '#2563eb', fontWeight: 600, fontSize: '0.85rem' }}>
                            <Brain size={16} /> Ответ ИИ
                          </div>
                          {answer}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="card">
              <div className="loading"><div className="spinner" /> Отчёт обрабатывается...</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


