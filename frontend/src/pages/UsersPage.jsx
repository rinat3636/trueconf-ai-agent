import React, { useState, useEffect } from 'react'
import { Plus } from 'lucide-react'
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

export default function UsersPage() {
  const [users, setUsers] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [newUser, setNewUser] = useState({ username: '', password: '', full_name: '', email: '', role: 'employee' })

  useEffect(() => { loadUsers() }, [])

  const loadUsers = async () => {
    try {
      const data = await api.getUsers()
      setUsers(data)
    } catch (err) { console.error(err) }
  }

  const handleCreate = async () => {
    try {
      await api.register(newUser)
      setShowModal(false)
      setNewUser({ username: '', password: '', full_name: '', email: '', role: 'employee' })
      loadUsers()
    } catch (err) { alert('Ошибка: ' + err.message) }
  }

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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
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
              <select className="form-control" value={newUser.role} onChange={e => setNewUser({ ...newUser, role: e.target.value })}>
                {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setShowModal(false)}>Отмена</button>
              <button className="btn btn-primary" onClick={handleCreate}>Создать</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
