import React, { useState, useEffect } from 'react'
import { Plus, Trash2, Edit } from 'lucide-react'
import { api } from '../services/api'

const RULE_TYPES = [
  { value: 'terminology', label: 'Терминология' },
  { value: 'forbidden', label: 'Запрещённые фразы' },
  { value: 'priority_source', label: 'Приоритетный источник' },
  { value: 'communication', label: 'Правила общения' },
  { value: 'business', label: 'Бизнес-правило' },
  { value: 'custom', label: 'Другое' },
]

const CORRECTION_TYPES = [
  { value: 'answer_fix', label: 'Исправление ответа' },
  { value: 'new_knowledge', label: 'Новое знание' },
  { value: 'new_rule', label: 'Новое правило' },
  { value: 'knowledge_update', label: 'Обновление знания' },
]

export default function TrainingPage() {
  const [rules, setRules] = useState([])
  const [corrections, setCorrections] = useState([])
  const [showRuleModal, setShowRuleModal] = useState(false)
  const [showCorrectionModal, setShowCorrectionModal] = useState(false)
  const [editRule, setEditRule] = useState(null)
  const [newRule, setNewRule] = useState({ rule_type: 'terminology', title: '', content: '', priority: 50 })
  const [newCorrection, setNewCorrection] = useState({
    original_question: '', original_answer: '', corrected_answer: '',
    correction_type: 'answer_fix', admin_comment: '',
  })

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    try {
      const [r, c] = await Promise.all([api.getRules(), api.getCorrections()])
      setRules(r)
      setCorrections(c)
    } catch (err) { console.error(err) }
  }

  const handleAddRule = async () => {
    try {
      await api.createRule(newRule)
      setShowRuleModal(false)
      setNewRule({ rule_type: 'terminology', title: '', content: '', priority: 50 })
      loadData()
    } catch (err) { alert('Ошибка: ' + err.message) }
  }

  const handleEditRule = async () => {
    try {
      await api.updateRule(editRule.id, {
        rule_type: editRule.rule_type,
        title: editRule.title,
        content: editRule.content,
        priority: editRule.priority,
      })
      setEditRule(null)
      loadData()
    } catch (err) { alert('Ошибка: ' + err.message) }
  }

  const handleDeleteRule = async (id) => {
    if (!confirm('Удалить это правило?')) return
    try { await api.deleteRule(id); loadData() } catch (err) { alert('Ошибка') }
  }

  const handleAddCorrection = async () => {
    try {
      await api.createCorrection(newCorrection)
      setShowCorrectionModal(false)
      setNewCorrection({
        original_question: '', original_answer: '', corrected_answer: '',
        correction_type: 'answer_fix', admin_comment: '',
      })
      loadData()
    } catch (err) { alert('Ошибка: ' + err.message) }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Обучение ИИ</h1>
        <p>Корпоративные правила и коррекции ответов</p>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <span className="card-title">Правила ({rules.length})</span>
            <button className="btn btn-primary btn-sm" onClick={() => setShowRuleModal(true)}>
              <Plus size={14} /> Добавить
            </button>
          </div>

          {rules.length === 0 ? (
            <div className="empty-state"><p>Правила не заданы</p></div>
          ) : (
            rules.map(rule => (
              <div key={rule.id} style={{ padding: '0.75rem', borderBottom: '1px solid #e5e7eb' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                  <div style={{ flex: 1 }}>
                    <span className="badge badge-info" style={{ marginRight: '0.5rem' }}>
                      {RULE_TYPES.find(t => t.value === rule.rule_type)?.label || rule.rule_type}
                    </span>
                    <strong>{rule.title}</strong>
                    {rule.priority && <span style={{ fontSize: '0.75rem', color: '#6b7280', marginLeft: '0.5rem' }}>P:{rule.priority}</span>}
                    <p style={{ fontSize: '0.85rem', color: '#6b7280', marginTop: '0.25rem' }}>{rule.content}</p>
                  </div>
                  <div style={{ display: 'flex', gap: '0.25rem' }}>
                    <button className="btn btn-outline btn-sm" onClick={() => setEditRule({ ...rule })}>
                      <Edit size={14} />
                    </button>
                    <button className="btn btn-danger btn-sm" onClick={() => handleDeleteRule(rule.id)}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title">Коррекции ({corrections.length})</span>
            <button className="btn btn-primary btn-sm" onClick={() => setShowCorrectionModal(true)}>
              <Plus size={14} /> Добавить
            </button>
          </div>

          {corrections.length === 0 ? (
            <div className="empty-state"><p>Коррекций пока нет</p></div>
          ) : (
            corrections.map(c => (
              <div key={c.id} style={{ padding: '0.75rem', borderBottom: '1px solid #e5e7eb' }}>
                <div style={{ fontSize: '0.85rem' }}>
                  <span className="badge badge-warning" style={{ marginBottom: '0.25rem' }}>
                    {CORRECTION_TYPES.find(t => t.value === c.correction_type)?.label || c.correction_type || 'answer_fix'}
                  </span>
                  <div style={{ color: '#6b7280', marginTop: '0.25rem' }}>В: {c.original_question}</div>
                  <div style={{ color: '#dc2626', textDecoration: 'line-through', marginTop: '0.25rem' }}>
                    Было: {(c.original_answer || '').substring(0, 100)}{(c.original_answer || '').length > 100 ? '...' : ''}
                  </div>
                  <div style={{ color: '#16a34a', marginTop: '0.25rem' }}>
                    Стало: {(c.corrected_answer || '').substring(0, 100)}{(c.corrected_answer || '').length > 100 ? '...' : ''}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Add Rule Modal */}
      {showRuleModal && (
        <div className="modal-overlay" onClick={() => setShowRuleModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3 className="modal-title">Добавить правило</h3>
            <div className="form-group">
              <label>Тип правила</label>
              <select className="form-control" value={newRule.rule_type} onChange={e => setNewRule({ ...newRule, rule_type: e.target.value })}>
                {RULE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Название</label>
              <input className="form-control" value={newRule.title} onChange={e => setNewRule({ ...newRule, title: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Содержание</label>
              <textarea className="form-control" value={newRule.content} onChange={e => setNewRule({ ...newRule, content: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Приоритет (1-100)</label>
              <input className="form-control" type="number" min="1" max="100" value={newRule.priority}
                onChange={e => setNewRule({ ...newRule, priority: parseInt(e.target.value) || 50 })} />
            </div>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setShowRuleModal(false)}>Отмена</button>
              <button className="btn btn-primary" onClick={handleAddRule}>Добавить</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Rule Modal */}
      {editRule && (
        <div className="modal-overlay" onClick={() => setEditRule(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3 className="modal-title">Редактировать правило</h3>
            <div className="form-group">
              <label>Тип правила</label>
              <select className="form-control" value={editRule.rule_type} onChange={e => setEditRule({ ...editRule, rule_type: e.target.value })}>
                {RULE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Название</label>
              <input className="form-control" value={editRule.title} onChange={e => setEditRule({ ...editRule, title: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Содержание</label>
              <textarea className="form-control" value={editRule.content} onChange={e => setEditRule({ ...editRule, content: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Приоритет (1-100)</label>
              <input className="form-control" type="number" min="1" max="100" value={editRule.priority}
                onChange={e => setEditRule({ ...editRule, priority: parseInt(e.target.value) || 50 })} />
            </div>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setEditRule(null)}>Отмена</button>
              <button className="btn btn-primary" onClick={handleEditRule}>Сохранить</button>
            </div>
          </div>
        </div>
      )}

      {/* Add Correction Modal */}
      {showCorrectionModal && (
        <div className="modal-overlay" onClick={() => setShowCorrectionModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3 className="modal-title">Добавить коррекцию</h3>
            <div className="form-group">
              <label>Тип коррекции</label>
              <select className="form-control" value={newCorrection.correction_type}
                onChange={e => setNewCorrection({ ...newCorrection, correction_type: e.target.value })}>
                {CORRECTION_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Исходный вопрос</label>
              <input className="form-control" value={newCorrection.original_question}
                onChange={e => setNewCorrection({ ...newCorrection, original_question: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Неправильный ответ</label>
              <textarea className="form-control" value={newCorrection.original_answer}
                onChange={e => setNewCorrection({ ...newCorrection, original_answer: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Правильный ответ</label>
              <textarea className="form-control" value={newCorrection.corrected_answer}
                onChange={e => setNewCorrection({ ...newCorrection, corrected_answer: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Комментарий администратора</label>
              <input className="form-control" value={newCorrection.admin_comment}
                onChange={e => setNewCorrection({ ...newCorrection, admin_comment: e.target.value })} />
            </div>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setShowCorrectionModal(false)}>Отмена</button>
              <button className="btn btn-primary" onClick={handleAddCorrection}>Добавить</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
