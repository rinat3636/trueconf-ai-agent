import React, { useState, useEffect, useRef } from 'react'
import { Upload, Trash2, Plus, FileText, Search } from 'lucide-react'
import { api } from '../services/api'

const CATEGORIES = [
  { value: '', label: 'All categories' },
  { value: 'products', label: 'Products' },
  { value: 'logistics', label: 'Logistics' },
  { value: 'commercial', label: 'Commercial' },
  { value: 'debts', label: 'Debts' },
  { value: 'employees', label: 'Employees' },
  { value: 'corporate', label: 'Corporate' },
]

export default function KnowledgePage() {
  const [documents, setDocuments] = useState([])
  const [knowledgeItems, setKnowledgeItems] = useState([])
  const [category, setCategory] = useState('')
  const [uploading, setUploading] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)
  const [newItem, setNewItem] = useState({ title: '', content: '', category: '' })
  const fileRef = useRef(null)

  useEffect(() => {
    loadData()
  }, [category])

  const loadData = async () => {
    try {
      const [docs, items] = await Promise.all([
        api.getDocuments(category || null),
        api.getKnowledgeItems(category || null),
      ])
      setDocuments(docs)
      setKnowledgeItems(items)
    } catch (err) {
      console.error(err)
    }
  }

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    try {
      await api.uploadDocument(file, category || null)
      loadData()
    } catch (err) {
      alert('Upload failed: ' + err.message)
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const handleDeleteDoc = async (id) => {
    if (!confirm('Delete this document?')) return
    try {
      await api.deleteDocument(id)
      loadData()
    } catch (err) {
      alert('Delete failed')
    }
  }

  const handleAddItem = async () => {
    try {
      await api.createKnowledgeItem(newItem)
      setShowAddModal(false)
      setNewItem({ title: '', content: '', category: '' })
      loadData()
    } catch (err) {
      alert('Failed to create: ' + err.message)
    }
  }

  const handleDeleteItem = async (id) => {
    if (!confirm('Delete this knowledge item?')) return
    try {
      await api.deleteKnowledgeItem(id)
      loadData()
    } catch (err) {
      alert('Delete failed')
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Knowledge Base</h1>
        <p>Manage documents and knowledge items</p>
      </div>

      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <select className="form-control" style={{ width: '200px' }} value={category} onChange={e => setCategory(e.target.value)}>
              {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-primary" onClick={() => fileRef.current?.click()} disabled={uploading}>
              <Upload size={16} /> {uploading ? 'Uploading...' : 'Upload Document'}
            </button>
            <button className="btn btn-outline" onClick={() => setShowAddModal(true)}>
              <Plus size={16} /> Add Knowledge
            </button>
          </div>
          <input ref={fileRef} type="file" style={{ display: 'none' }} accept=".pdf,.docx,.xlsx,.xls,.csv,.txt" onChange={handleUpload} />
        </div>

        <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem' }}>Documents ({documents.length})</h3>
        {documents.length === 0 ? (
          <div className="empty-state"><p>No documents uploaded yet</p></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>File</th>
                  <th>Category</th>
                  <th>Status</th>
                  <th>Chunks</th>
                  <th>Date</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {documents.map(doc => (
                  <tr key={doc.id}>
                    <td><FileText size={14} style={{ marginRight: '0.5rem' }} />{doc.original_filename}</td>
                    <td>{doc.category || '-'}</td>
                    <td><span className={`badge badge-${doc.status === 'ready' ? 'success' : doc.status === 'error' ? 'danger' : 'warning'}`}>{doc.status}</span></td>
                    <td>{doc.chunk_count}</td>
                    <td>{new Date(doc.created_at).toLocaleDateString()}</td>
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
        <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem' }}>Knowledge Items ({knowledgeItems.length})</h3>
        {knowledgeItems.length === 0 ? (
          <div className="empty-state"><p>No knowledge items yet</p></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Category</th>
                  <th>Approved</th>
                  <th>Date</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {knowledgeItems.map(item => (
                  <tr key={item.id}>
                    <td>{item.title}</td>
                    <td>{item.category || '-'}</td>
                    <td><span className={`badge badge-${item.is_approved ? 'success' : 'warning'}`}>{item.is_approved ? 'Yes' : 'Pending'}</span></td>
                    <td>{new Date(item.created_at).toLocaleDateString()}</td>
                    <td>
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
            <h3 className="modal-title">Add Knowledge Item</h3>
            <div className="form-group">
              <label>Title</label>
              <input className="form-control" value={newItem.title} onChange={e => setNewItem({ ...newItem, title: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Content</label>
              <textarea className="form-control" value={newItem.content} onChange={e => setNewItem({ ...newItem, content: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Category</label>
              <select className="form-control" value={newItem.category} onChange={e => setNewItem({ ...newItem, category: e.target.value })}>
                {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setShowAddModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleAddItem}>Add</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
