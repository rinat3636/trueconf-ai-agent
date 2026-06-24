import React, { useState, useEffect } from 'react'
import { Save, Plus, X, Bot, ShieldAlert, Database, MessageSquare } from 'lucide-react'
import { api } from '../services/api'

const CATEGORY_OPTIONS = [
  { value: 'product_catalog', label: 'Каталог продукции' },
  { value: 'product_knowledge', label: 'Знания о продуктах' },
  { value: 'company_reference', label: 'Справочник компании' },
  { value: 'certification', label: 'Сертификация' },
  { value: 'policy', label: 'Политики' },
  { value: 'sales_methodology', label: 'Методология продаж' },
  { value: 'contacts', label: 'Контакты' },
  { value: 'general', label: 'Общее' },
  { value: 'other', label: 'Прочее' },
]

export default function BotSettingsPage() {
  const [settings, setSettings] = useState({
    system_instructions: '',
    restricted_topics: [],
    allowed_categories: [],
    trueconf_restrictions: '',
    greeting_message: '',
    max_response_length: 2000,
    enable_sales_data: true,
    enable_knowledge_base: true,
    enable_self_learning: true,
    custom_prompt_suffix: '',
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [newTopic, setNewTopic] = useState('')

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      const data = await api.getBotSettings()
      setSettings(data)
    } catch (err) {
      console.error('Failed to load bot settings:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setSaved(false)
    try {
      const data = await api.updateBotSettings(settings)
      setSettings(data)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      alert('Ошибка сохранения: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const addTopic = () => {
    const topic = newTopic.trim()
    if (topic && !settings.restricted_topics.includes(topic)) {
      setSettings({ ...settings, restricted_topics: [...settings.restricted_topics, topic] })
      setNewTopic('')
    }
  }

  const removeTopic = (index) => {
    setSettings({
      ...settings,
      restricted_topics: settings.restricted_topics.filter((_, i) => i !== index),
    })
  }

  const toggleCategory = (cat) => {
    const current = settings.allowed_categories || []
    if (current.includes(cat)) {
      setSettings({ ...settings, allowed_categories: current.filter(c => c !== cat) })
    } else {
      setSettings({ ...settings, allowed_categories: [...current, cat] })
    }
  }

  if (loading) {
    return (
      <div>
        <div className="page-header">
          <h1>Настройки TrueConf бота</h1>
          <p>Загрузка...</p>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="page-header">
        <h1>Настройки TrueConf бота</h1>
        <p>Управление поведением ИИ-ассистента только в TrueConf чатах. На чат в админке эти настройки не влияют.</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

        {/* System Instructions */}
        <div className="card">
          <div className="card-header">
            <span className="card-title"><Bot size={18} style={{ marginRight: 8, verticalAlign: 'middle' }} />Системные инструкции</span>
          </div>
          <div style={{ padding: '1rem' }}>
            <p style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '0.5rem' }}>
              Дополнительные указания для ИИ в TrueConf. Они будут добавлены к системному промпту бота при ответах в TrueConf чатах.
            </p>
            <textarea
              className="form-control"
              rows={4}
              placeholder="Например: Всегда предлагай обратиться к менеджеру для уточнения цен. При ответах используй формальный тон."
              value={settings.system_instructions}
              onChange={e => setSettings({ ...settings, system_instructions: e.target.value })}
            />
          </div>
        </div>

        {/* Restricted Topics */}
        <div className="card">
          <div className="card-header">
            <span className="card-title"><ShieldAlert size={18} style={{ marginRight: 8, verticalAlign: 'middle' }} />Запрещённые темы</span>
          </div>
          <div style={{ padding: '1rem' }}>
            <p style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '0.5rem' }}>
              Темы, которые бот НЕ должен обсуждать. Бот вежливо откажет и предложит обратиться к руководству.
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
              {(settings.restricted_topics || []).map((topic, i) => (
                <span key={i} className="badge badge-danger" style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '4px 10px', fontSize: '0.85rem' }}>
                  {topic}
                  <X size={14} style={{ cursor: 'pointer' }} onClick={() => removeTopic(i)} />
                </span>
              ))}
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <input
                className="form-control"
                placeholder="Добавить тему (например: зарплаты сотрудников)"
                value={newTopic}
                onChange={e => setNewTopic(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addTopic())}
              />
              <button className="btn btn-primary btn-sm" onClick={addTopic} disabled={!newTopic.trim()}>
                <Plus size={14} /> Добавить
              </button>
            </div>
          </div>
        </div>

        {/* TrueConf Restrictions */}
        <div className="card">
          <div className="card-header">
            <span className="card-title"><MessageSquare size={18} style={{ marginRight: 8, verticalAlign: 'middle' }} />Ограничения для TrueConf</span>
          </div>
          <div style={{ padding: '1rem' }}>
            <p style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '0.5rem' }}>
              Специальные ограничения для бота в канале TrueConf. Например, какие данные не разглашать в чате.
            </p>
            <textarea
              className="form-control"
              rows={3}
              placeholder="Например: Не разглашать финансовые показатели компании. Не обсуждать персональные данные сотрудников."
              value={settings.trueconf_restrictions}
              onChange={e => setSettings({ ...settings, trueconf_restrictions: e.target.value })}
            />
          </div>
        </div>

        {/* Data Sources */}
        <div className="card">
          <div className="card-header">
            <span className="card-title"><Database size={18} style={{ marginRight: 8, verticalAlign: 'middle' }} />Источники данных</span>
          </div>
          <div style={{ padding: '1rem' }}>
            <p style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '0.75rem' }}>
              Какие данные бот может использовать для ответов.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1rem' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={settings.enable_knowledge_base}
                  onChange={e => setSettings({ ...settings, enable_knowledge_base: e.target.checked })}
                />
                <span>База знаний (документы, справочники, каталоги)</span>
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={settings.enable_sales_data}
                  onChange={e => setSettings({ ...settings, enable_sales_data: e.target.checked })}
                />
                <span>Аналитика продаж (выручка, прибыль, ТП, клиенты)</span>
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={settings.enable_self_learning}
                  onChange={e => setSettings({ ...settings, enable_self_learning: e.target.checked })}
                />
                <span>Самообучение (автоизвлечение знаний из новых документов)</span>
              </label>
            </div>

            <p style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '0.5rem' }}>
              Разрешённые категории знаний (если пусто — используются все):
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              {CATEGORY_OPTIONS.map(cat => (
                <label
                  key={cat.value}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer',
                    padding: '4px 10px', borderRadius: 6,
                    background: (settings.allowed_categories || []).includes(cat.value) ? '#3b82f6' : '#374151',
                    color: '#fff', fontSize: '0.85rem',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={(settings.allowed_categories || []).includes(cat.value)}
                    onChange={() => toggleCategory(cat.value)}
                    style={{ display: 'none' }}
                  />
                  {cat.label}
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Greeting & Advanced */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Дополнительные настройки</span>
          </div>
          <div style={{ padding: '1rem' }}>
            <div className="form-group">
              <label>Приветственное сообщение</label>
              <input
                className="form-control"
                placeholder="Привет! Я ИИ-ассистент компании. Чем могу помочь?"
                value={settings.greeting_message}
                onChange={e => setSettings({ ...settings, greeting_message: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Макс. длина ответа (символов)</label>
              <input
                className="form-control"
                type="number"
                min={100}
                max={10000}
                value={settings.max_response_length}
                onChange={e => setSettings({ ...settings, max_response_length: parseInt(e.target.value) || 2000 })}
              />
            </div>
            <div className="form-group">
              <label>Дополнение к промпту (для продвинутых)</label>
              <textarea
                className="form-control"
                rows={3}
                placeholder="Текст, который будет добавлен в конец системного промпта"
                value={settings.custom_prompt_suffix}
                onChange={e => setSettings({ ...settings, custom_prompt_suffix: e.target.value })}
              />
            </div>
          </div>
        </div>

        {/* Save Button */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', alignItems: 'center' }}>
          {saved && <span style={{ color: '#22c55e', fontSize: '0.9rem' }}>Сохранено</span>}
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            <Save size={16} /> {saving ? 'Сохранение...' : 'Сохранить настройки'}
          </button>
        </div>
      </div>
    </div>
  )
}
