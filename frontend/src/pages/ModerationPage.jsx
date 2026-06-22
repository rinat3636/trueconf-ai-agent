import React, { useState, useEffect } from 'react'
import { Check, X, Clock } from 'lucide-react'
import { api } from '../services/api'

export default function ModerationPage() {
  const [items, setItems] = useState([])
  const [filter, setFilter] = useState('pending')
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadItems() }, [filter])

  const loadItems = async () => {
    setLoading(true)
    try {
      const data = await api.getModerationQueue(filter)
      setItems(data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleAction = async (id, action) => {
    try {
      await api.moderateItem(id, action)
      loadItems()
    } catch (err) {
      alert('Failed: ' + err.message)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Moderation Queue</h1>
        <p>Review and approve new knowledge suggestions</p>
      </div>

      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {['pending', 'approved', 'rejected'].map(f => (
              <button key={f} className={`btn ${filter === f ? 'btn-primary' : 'btn-outline'} btn-sm`}
                onClick={() => setFilter(f)}>
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
          <span style={{ color: '#6b7280', fontSize: '0.85rem' }}>{items.length} items</span>
        </div>

        {loading ? (
          <div className="loading"><div className="spinner" /> Loading...</div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <Clock size={48} color="#d1d5db" />
            <p>No items in {filter} queue</p>
          </div>
        ) : (
          items.map(item => (
            <div key={item.id} style={{
              padding: '1rem',
              borderBottom: '1px solid #e5e7eb',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'start',
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.25rem' }}>
                  <span className={`badge badge-${
                    item.item_type === 'new_knowledge' ? 'info' :
                    item.item_type === 'bad_answer' ? 'danger' :
                    item.item_type === 'conflict' ? 'warning' : 'info'
                  }`}>
                    {item.item_type}
                  </span>
                  <strong>{item.title}</strong>
                </div>
                <p style={{ fontSize: '0.85rem', color: '#4b5563', whiteSpace: 'pre-wrap' }}>{item.content}</p>
                {item.source_info && (
                  <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>Source: {item.source_info}</p>
                )}
              </div>
              {filter === 'pending' && (
                <div style={{ display: 'flex', gap: '0.5rem', marginLeft: '1rem' }}>
                  <button className="btn btn-success btn-sm" onClick={() => handleAction(item.id, 'approve')}>
                    <Check size={14} /> Approve
                  </button>
                  <button className="btn btn-danger btn-sm" onClick={() => handleAction(item.id, 'reject')}>
                    <X size={14} /> Reject
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
