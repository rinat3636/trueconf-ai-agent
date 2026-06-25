import React, { useState, useEffect } from 'react'
import { Plus, Edit2, Save, X, Trash2 } from 'lucide-react'
import { api } from '../services/api'

const ROLES = [
  { value: 'employee', label: 'Сотрудник' },
  { value: 'manager', label: 'Менеджер' },
  { value: 'admin', label: 'Администратор' },
  { value: 'super_admin', label: 'Суперадмин' },
]

const ROLE_BADGE = {
  super_admin: 'danger',
  admin: 'warning',
  manager: 'info',
  employee: 'success',
}

const PERMISSION_OPTIONS = [
  { key: 'chat', label: 'Чат с ИИ', description: 'Доступ к чату с ИИ-ассистентом' },
  { key: 'knowledge_view', label: 'Просмотр базы знаний', description: 'Просмотр документов и записей знаний' },
  { key: 'knowledge_edit', label: 'Редактирование базы знаний', description: 'Добавление и изменение документов' },
  { key: 'sales_view', label: 'Аналитика продаж', description: 'Просмотр отчётов продаж' },
  { key: 'sales_upload', label: 'Загрузка отчётов', description: 'Загрузка новых отчётов продаж' },
  { key: 'moderation', label: 'Модерация', description: 'Модерация знаний и конфликтов' },
  { key: 'user_management', label: 'Управление пользователями', description: 'Создание и редактирование пользователей' },
  { key: 'bot_settings', label: 'Настройки бота', description: 'Изменение настроек чат-бота' },
  { key: 'trueconf_chat', label: 'Чат в TrueConf', description: 'Общение с ботом через TrueConf' },
]

const DEFAULT_PERMISSIONS_BY_ROLE = {
  super_admin: PERMISSION_OPTIONS.reduce((acc, p) => ({ ...acc, [p.key]: true }), {}),
  admin: { chat: true, knowledge_view: true, knowledge_edit: true, sales_view: true, sales_upload: true, moderation: true, bot_settings: true, trueconf_chat: true, user_management: false },
  manager: { chat: true, knowledge_view: true, knowledge_edit: false, sales_view: true, sales_upload: true, moderation: false, bot_settings: false, trueconf_chat: true, user_management: false },
  employee: { chat: true, knowledge_view: false, knowledge_edit: false, sales_view: false, sales_upload: false, moderation: false, bot_settings: false, trueconf_chat: true, user_management: false },
}

export default function UsersPage() {
  const [users, setUsers] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [newUser, setNewUser] = useState({
    username: '', password: '', full_name: '', email: '', role: 'employee',
    permissions: { ...DEFAULT_PERMISSIONS_BY_ROLE.employee },
  })

  useEffect(() => { loadUsers() }, [])

  const loadUsers = async () => {
    try {
      const data = await api.getUsers()
      setUsers(data)
    } catch (err) { console.error(err) }
  }

  const handleRoleChange = (role) => {
    const defaults = DEFAULT_PERMISSIONS_BY_ROLE[role] || DEFAULT_PERMISSIONS_BY_ROLE.employee
    if (editingUser) {
      setEditingUser({ ...editingUser, role, permissions: { ...defaults } })
    } else {
      setNewUser({ ...newUser, role, permissions: { ...defaults } })
    }
  }

  const togglePermission = (key) => {
    if (editingUser) {
      const perms = { ...(editingUser.permissions || {}) }
      perms[key] = !perms[key]
      setEditingUser({ ...editingUser, permissions: perms })
    } else {
      const perms = { ...(newUser.permissions || {}) }
      perms[key] = !perms[key]
      setNewUser({ ...newUser, permissions: perms })
    }
  }

  const handleCreate = async () => {
    try {
      await api.register(newUser)
      setShowModal(false)
      setNewUser({
        username: '', password: '', full_name: '', email: '', role: 'employee',
        permissions: { ...DEFAULT_PERMISSIONS_BY_ROLE.employee },
      })
      loadUsers()
    } catch (err) { alert('Ошибка: ' + err.message) }
  }

  const handleDelete = async (user) => {
    if (!window.confirm(`Удалить пользователя «${user.username}»? Его история чатов будет удалена.`)) return
    try {
      await api.deleteUser(user.id)
      setEditingUser(null)
      loadUsers()
    } catch (err) { alert('Ошибка: ' + err.message) }
  }

  const handleEdit = (user) => {
    setEditingUser({
      ...user,
      permissions: user.permissions || DEFAULT_PERMISSIONS_BY_ROLE[user.role] || {},
    })
  }

  const handleSaveEdit = async () => {
    try {
      const payload = {
        full_name: editingUser.full_name,
        email: editingUser.email,
        role: editingUser.role,
        is_active: editingUser.is_active,
        permissions: editingUser.permissions,
      }
      if (editingUser.username && editingUser.username.trim()) payload.username = editingUser.username.trim()
      if (editingUser.newPassword && editingUser.newPassword.trim()) payload.password = editingUser.newPassword.trim()
      await api.updateUser(editingUser.id, payload)
      setEditingUser(null)
      loadUsers()
    } catch (err) { alert('Ошибка: ' + err.message) }
  }

  const currentData = editingUser || newUser
  const currentPerms = currentData.permissions || {}

  const renderPermissionsBlock = () => (
    <div className="form-group">
      <label style={{ marginBottom: '0.5rem', display: 'block' }}>Возможности пользователя</label>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
        {PERMISSION_OPTIONS.map(p => (
          <label key={p.key} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', cursor: 'pointer', fontSize: '0.85rem', lineHeight: 1.4 }}>
            <input
              type="checkbox"
              checked={!!currentPerms[p.key]}
              onChange={() => togglePermission(p.key)}
              style={{ marginTop: '0.2rem', flexShrink: 0 }}
            />
            <span>
              {p.label}
              <span style={{ color: '#6b7280', fontSize: '0.7rem', display: 'block' }}>{p.description}</span>
            </span>
          </label>
        ))}
      </div>
    </div>
  )

  return (
    <div>
      <div className="page-header">
        <h1>Пользователи</h1>
        <p>Управление пользователями системы</p>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Все пользователи ({users.length})</span>
          <button className="btn btn-primary btn-sm" onClick={() => setShowModal(true)}>
            <Plus size={14} /> Добавить
          </button>
        </div>

        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Логин</th>
                <th>Имя</th>
                <th>Email</th>
                <th>Роль</th>
                <th>Активен</th>
                <th>TrueConf ID</th>
                <th>Создан</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id}>
                  <td>{u.username}</td>
                  <td>{u.full_name || '-'}</td>
                  <td>{u.email || '-'}</td>
                  <td>
                    <span className={`badge badge-${ROLE_BADGE[u.role] || 'info'}`}>
                      {ROLES.find(r => r.value === u.role)?.label || u.role}
                    </span>
                  </td>
                  <td><span className={`badge badge-${u.is_active ? 'success' : 'danger'}`}>{u.is_active ? 'Да' : 'Нет'}</span></td>
                  <td>{u.trueconf_id || '-'}</td>
                  <td>{new Date(u.created_at).toLocaleDateString('ru-RU')}</td>
                  <td>
                    <button className="btn btn-outline btn-sm" onClick={() => handleEdit(u)} title="Редактировать">
                      <Edit2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create User Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 550 }}>
            <h3 className="modal-title">Добавить пользователя</h3>
            <div className="form-group">
              <label>Логин</label>
              <input className="form-control" value={newUser.username} onChange={e => setNewUser({ ...newUser, username: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Пароль</label>
              <input className="form-control" type="password" value={newUser.password} onChange={e => setNewUser({ ...newUser, password: e.target.value })} />
            </div>
            <div className="form-group">
              <label>ФИО</label>
              <input className="form-control" value={newUser.full_name} onChange={e => setNewUser({ ...newUser, full_name: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Email</label>
              <input className="form-control" type="email" value={newUser.email} onChange={e => setNewUser({ ...newUser, email: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Роль</label>
              <select className="form-control" value={newUser.role} onChange={e => handleRoleChange(e.target.value)}>
                {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
            {renderPermissionsBlock()}
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setShowModal(false)}>Отмена</button>
              <button className="btn btn-primary" onClick={handleCreate}>Создать</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {editingUser && (
        <div className="modal-overlay" onClick={() => setEditingUser(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 550 }}>
            <h3 className="modal-title">Редактировать: {editingUser.username}</h3>
            <div className="form-group">
              <label>Логин</label>
              <input className="form-control" value={editingUser.username || ''} onChange={e => setEditingUser({ ...editingUser, username: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Новый пароль (оставьте пустым, чтобы не менять)</label>
              <input className="form-control" type="password" autoComplete="new-password" placeholder="••••••••" value={editingUser.newPassword || ''} onChange={e => setEditingUser({ ...editingUser, newPassword: e.target.value })} />
            </div>
            <div className="form-group">
              <label>ФИО</label>
              <input className="form-control" value={editingUser.full_name || ''} onChange={e => setEditingUser({ ...editingUser, full_name: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Email</label>
              <input className="form-control" type="email" value={editingUser.email || ''} onChange={e => setEditingUser({ ...editingUser, email: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Роль</label>
              <select className="form-control" value={editingUser.role} onChange={e => handleRoleChange(e.target.value)}>
                {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={editingUser.is_active}
                  onChange={e => setEditingUser({ ...editingUser, is_active: e.target.checked })}
                />
                Активен
              </label>
            </div>
            {renderPermissionsBlock()}
            <div className="modal-actions" style={{ justifyContent: 'space-between' }}>
              <button className="btn btn-danger" onClick={() => handleDelete(editingUser)}><Trash2 size={14} /> Удалить</button>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button className="btn btn-outline" onClick={() => setEditingUser(null)}><X size={14} /> Отмена</button>
                <button className="btn btn-primary" onClick={handleSaveEdit}><Save size={14} /> Сохранить</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
