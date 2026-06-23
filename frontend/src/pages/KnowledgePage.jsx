import React, { useState, useEffect, useRef } from 'react'
import { Upload, Trash2, Plus, FileText, Search, RefreshCw, Edit } from 'lucide-react'
import { api } from '../services/api'

const CATEGORIES = [
  { value: '', label: 'Все категории' },
  { value: 'products', label: 'Продукция' },
  { value: 'logistics', label: 'Логистика' },
  { value: 'commercial', label: 'Коммерческие условия' },
  { value: 'debts', label: 'Дебиторская задолженность' },
  { value: 'employees', label: 'Сотрудники' },
  { value: 'corporate', label: 'Корпоративные правила' },
  { value: 'clients', label: 'Клиенты' },
  { value: 'compliance', label: 'Документы качества' },
  { value: 'marketing', label: 'Маркетинг' },
  { value: 'other', label: 'Прочее' },
]

export default function KnowledgePage() {
  const [documents, setDocuments] = useState([])
  const [knowledgeItems, setKnowledgeItems] = useState([])
  const [category, setCategory] = useState('')
  const [uploading, setUploading] = useState(false)
  const [reindexing, setReindexing] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [editItem, setEditItem] = useState(null)
  const [newItem, setNewItem] = useState({ title: '', content: '', category: 'other' })
  const fileRef = useRef(null)

  useEffect(() => { loadData() }, [category])

  const loadData = async () => {
    try {
      const [docs, items] = await Promise.all([
        api.getDocuments(category || null),
        api.getKnowledgeItems(category || null),
      ])
      setDocuments(docs)
      setKnowledgeItems(items)
    } catch (err) { console.error(err) }
  }

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    try {
      await api.uploadDocument(file, category || null)
      loadData()
    } catch (err) { alert('Ошибка загрузки: ' + err.message) }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = '' }
  }

  const handleDeleteDoc = async (id) => {
    if (!confirm('Удалить этот документ?')) return
    try { await api.deleteDocument(id); loadData() }
    catch (err) { alert('Ошибка удаления') }
  }

  const handleAddItem = async () => {
    try {
      await api.createKnowledgeItem(newItem)
      setShowAddModal(false)
      setNewItem({ title: '', content: '', category: 'other' })
      loadData()
    } catch (err) { alert('Ошибка: ' + err.message) }
  }

  const handleEditItem = async () => {
    try {
      await api.updateKnowledgeItem(editItem.id, {
        title: editItem.title,
        content: editItem.content,
        category: editItem.category,
      })
      setEditItem(null)
      loadData()
    } catch (err) { alert('Ошибка: ' + err.message) }
  }

  const handleDeleteItem = async (id) => {
    if (!confirm('Удалить эту запись знаний?')) return
    try { await api.deleteKnowledgeItem(id); loadData() }
    catch (err) { alert('Ошибка удаления') }
  }

  const handleReindex = async () => {
    if (!confirm('Запустить полную переиндексацию базы знаний?')) return
    setReindexing(true)
    try { await api.reindex(); alert('Переиндексация запущена') }
    catch (err) { alert('Ошибка: ' + err.message) }
    finally { setReindexing(false) }
  }

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    try {
      const data = await api.searchKnowledge(searchQuery, category || null)
      setSearchResults(data)
    } catch (err) { alert('Ошибка поиска: ' + err.message) }
  }

  const statusLabel = (s) => {
    const map = { ready: 'Готов', processing: 'Обработка', error: 'Ошибка', pending: 'Ожидание' }
    return map[s] || s
  }

  return (
    <div>
      <div className="page-header">
        <h1>База знаний</h1>
        <p>Управление документами и записями знаний</p>
      </div>

      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <select className="form-control" style={{ width: '220px' }} value={category} onChange={e => setCategory(e.target.value)}>
              {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
            <form onSubmit={handleSearch} style={{ display: 'flex', gap: '0.5rem' }}>
              <input className="form-control" style={{ width: '200px' }} value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)} placeholder="Поиск по знаниям..." />
              <button className="btn btn-outline btn-sm" type="submit"><Search size={14} /></button>
            </form>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-outline btn-sm" onClick={handleReindex} disabled={reindexing}>
              <RefreshCw size={14} /> {reindexing ? 'Индексация...' : 'Переиндексация'}
            </button>
            <button className="btn btn-primary" onClick={() => fileRef.current?.click()} disabled={uploading}>
              <Upload size={16} /> {uploading ? 'Загрузка...' : 'Загрузить'}
            </button>
            <button className="btn btn-outline" onClick={() => setShowAddModal(true)}>
              <Plus size={16} /> Добавить
            </button>
          </div>
          <input ref={fileRef} type="file" style={{ display: 'none' }} accept=".pdf,.docx,.pptx,.xlsx,.xls,.csv,.txt" onChange={handleUpload} />
        </div>

        {searchResults && (
          <div style={{ marginBottom: '1rem', padding: '1rem', background: '#f0f9ff', borderRadius: '0.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <strong>Результаты поиска ({searchResults.length || 0})</strong>
              <button className="btn btn-outline btn-sm" onClick={() => setSearchResults(null)}>Закрыть</button>
            </div>
            {(searchResults || []).map((r, i) => (
              <div key={i} style={{ padding: '0.5rem', borderBottom: '1px solid #e5e7eb', fontSize: '0.85rem' }}>
                <strong>{r.title || 'Без названия'}</strong>
                <span className="badge badge-info" style={{ marginLeft: '0.5rem' }}>{r.score?.toFixed(2)}</span>
                <p style={{ color: '#4b5563', marginTop: '0.25rem' }}>{r.content?.substring(0, 200)}...</p>
              </div>
            ))}
          </div>
        )}

        <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem' }}>Документы ({documents.length})</h3>
        {documents.length === 0 ? (
          <div className="empty-state"><p>Документы не загружены</p></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr><th>Файл</th><th>Категория</th><th>Статус</th><th>Чанки</th><th>Дата</th><th></th></tr>
              </thead>
              <tbody>
                {documents.map(doc => (
                  <tr key={doc.id}>
                    <td><FileText size={14} style={{ marginRight: '0.5rem' }} />{doc.original_filename}</td>
                    <td>{CATEGORIES.find(c => c.value === doc.category)?.label || doc.category || '-'}</td>
                    <td><span className={`badge badge-${doc.status === 'ready' ? 'success' : doc.status === 'error' ? 'danger' : 'warning'}`}>{statusLabel(doc.status)}</span></td>
                    <td>{doc.chunk_count || 0}</td>
                    <td>{new Date(doc.created_at).toLocaleDateString('ru-RU')}</td>
                    <td>
                      <button className="btn btn-danger btn-sm" onClick={() => handleDeleteDoc(doc.id)}>
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem' }}>Записи знаний ({knowledgeItems.length})</h3>
        {knowledgeItems.length === 0 ? (
          <div className="empty-state"><p>Записей знаний пока нет</p></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr><th>Название</th><th>Категория</th><th>Одобрена</th><th>Версия</th><th>Дата</th><th></th></tr>
              </thead>
              <tbody>
                {knowledgeItems.map(item => (
                  <tr key={item.id}>
                    <td>{item.title}</td>
                    <td>{CATEGORIES.find(c => c.value === item.category)?.label || item.category || '-'}</td>
                    <td><span className={`badge badge-${item.status === 'approved' ? 'success' : 'warning'}`}>{item.status === 'approved' ? 'Одобрена' : 'Ожидает'}</span></td>
                    <td>v{item.version || 1}</td>
                    <td>{new Date(item.created_at).toLocaleDateString('ru-RU')}</td>
                    <td style={{ display: 'flex', gap: '0.25rem' }}>
                      <button className="btn btn-outline btn-sm" onClick={() => setEditItem({ ...item })}>
                        <Edit size={14} />
                      </button>
                      <button className="btn btn-danger btn-sm" onClick={() => handleDeleteItem(item.id)}>
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3 className="modal-title">Добавить запись знаний</h3>
            <div className="form-group">
              <label>Название</label>
              <input className="form-control" value={newItem.title} onChange={e => setNewItem({ ...newItem, title: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Содержание</label>
              <textarea className="form-control" value={newItem.content} onChange={e => setNewItem({ ...newItem, content: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Категория</label>
              <select className="form-control" value={newItem.category} onChange={e => setNewItem({ ...newItem, category: e.target.value })}>
                {CATEGORIES.filter(c => c.value).map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setShowAddModal(false)}>Отмена</button>
              <button className="btn btn-primary" onClick={handleAddItem}>Добавить</button>
            </div>
          </div>
        </div>
      )}

      {editItem && (
        <div className="modal-overlay" onClick={() => setEditItem(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3 className="modal-title">Редактировать запись</h3>
            <div className="form-group">
              <label>Название</label>
              <input className="form-control" value={editItem.title} onChange={e => setEditItem({ ...editItem, title: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Содержание</label>
              <textarea className="form-control" value={editItem.content} onChange={e => setEditItem({ ...editItem, content: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Категория</label>
              <select className="form-control" value={editItem.category} onChange={e => setEditItem({ ...editItem, category: e.target.value })}>
                {CATEGORIES.filter(c => c.value).map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setEditItem(null)}>Отмена</button>
              <button className="btn btn-primary" onClick={handleEditItem}>Сохранить</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
