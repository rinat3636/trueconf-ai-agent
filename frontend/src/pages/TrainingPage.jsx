import React, { useState, useEffect } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { api } from '../services/api'

const RULE_TYPES = [
  { value: 'terminology', label: 'Terminology' },
  { value: 'forbidden', label: 'Forbidden phrases' },
  { value: 'priority_source', label: 'Priority source' },
  { value: 'custom', label: 'Custom rule' },
]

export default function TrainingPage() {
  const [rules, setRules] = useState([])
  const [corrections, setCorrections] = useState([])
  const [showRuleModal, setShowRuleModal] = useState(false)
  const [showCorrectionModal, setShowCorrectionModal] = useState(false)
  const [newRule, setNewRule] = useState({ rule_type: 'terminology', title: '', content: '' })
  const [newCorrection, setNewCorrection] = useState({ original_question: '', original_answer: '', corrected_answer: '' })

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    try {
      const [r, c] = await Promise.all([api.getRules(), api.getCorrections()])
      setRules(r)
      setCorrections(c)
    } catch (err) {
      console.error(err)
    }
  }

  const handleAddRule = async () => {
    try {
      await api.createRule(newRule)
      setShowRuleModal(false)
      setNewRule({ rule_type: 'terminology', title: '', content: '' })
      loadData()
    } catch (err) {
      alert('Failed: ' + err.message)
    }
  }

  const handleDeleteRule = async (id) => {
    if (!confirm('Delete this rule?')) return
    try { await api.deleteRule(id); loadData() } catch (err) { alert('Failed') }
  }

  const handleAddCorrection = async () => {
    try {
      await api.createCorrection(newCorrection)
      setShowCorrectionModal(false)
      setNewCorrection({ original_question: '', original_answer: '', corrected_answer: '' })
      loadData()
    } catch (err) {
      alert('Failed: ' + err.message)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>AI Training</h1>
        <p>Configure rules and correct AI responses</p>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <span className="card-title">Corporate Rules ({rules.length})</span>
            <button className="btn btn-primary btn-sm" onClick={() => setShowRuleModal(true)}>
              <Plus size={14} /> Add Rule
            </button>
          </div>

          {rules.length === 0 ? (
            <div className="empty-state"><p>No rules defined</p></div>
          ) : (
            rules.map(rule => (
              <div key={rule.id} style={{ padding: '0.75rem', borderBottom: '1px solid #e5e7eb' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                  <div>
                    <span className="badge badge-info" style={{ marginRight: '0.5rem' }}>{rule.rule_type}</span>
                    <strong>{rule.title}</strong>
                    <p style={{ fontSize: '0.85rem', color: '#6b7280', marginTop: '0.25rem' }}>{rule.content}</p>
                  </div>
                  <button className="btn btn-danger btn-sm" onClick={() => handleDeleteRule(rule.id)}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title">Answer Corrections ({corrections.length})</span>
            <button className="btn btn-primary btn-sm" onClick={() => setShowCorrectionModal(true)}>
              <Plus size={14} /> Add Correction
            </button>
          </div>

          {corrections.length === 0 ? (
            <div className="empty-state"><p>No corrections yet</p></div>
          ) : (
            corrections.map(c => (
              <div key={c.id} style={{ padding: '0.75rem', borderBottom: '1px solid #e5e7eb' }}>
                <div style={{ fontSize: '0.85rem' }}>
                  <div style={{ color: '#6b7280' }}>Q: {c.original_question}</div>
                  <div style={{ color: '#dc2626', textDecoration: 'line-through', marginTop: '0.25rem' }}>
                    Old: {c.original_answer.substring(0, 100)}...
                  </div>
                  <div style={{ color: '#16a34a', marginTop: '0.25rem' }}>
                    New: {c.corrected_answer.substring(0, 100)}...
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {showRuleModal && (
        <div className="modal-overlay" onClick={() => setShowRuleModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3 className="modal-title">Add Corporate Rule</h3>
            <div className="form-group">
              <label>Rule Type</label>
              <select className="form-control" value={newRule.rule_type} onChange={e => setNewRule({ ...newRule, rule_type: e.target.value })}>
                {RULE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Title</label>
              <input className="form-control" value={newRule.title} onChange={e => setNewRule({ ...newRule, title: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Content</label>
              <textarea className="form-control" value={newRule.content} onChange={e => setNewRule({ ...newRule, content: e.target.value })} />
            </div>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setShowRuleModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleAddRule}>Add</button>
            </div>
          </div>
        </div>
      )}

      {showCorrectionModal && (
        <div className="modal-overlay" onClick={() => setShowCorrectionModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3 className="modal-title">Add Answer Correction</h3>
            <div className="form-group">
              <label>Original Question</label>
              <input className="form-control" value={newCorrection.original_question} onChange={e => setNewCorrection({ ...newCorrection, original_question: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Original (wrong) Answer</label>
              <textarea className="form-control" value={newCorrection.original_answer} onChange={e => setNewCorrection({ ...newCorrection, original_answer: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Corrected Answer</label>
              <textarea className="form-control" value={newCorrection.corrected_answer} onChange={e => setNewCorrection({ ...newCorrection, corrected_answer: e.target.value })} />
            </div>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setShowCorrectionModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleAddCorrection}>Add</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
