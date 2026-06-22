import React, { useState, useEffect } from 'react'
import { Plus } from 'lucide-react'
import { api } from '../services/api'

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
    } catch (err) { alert('Failed: ' + err.message) }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Users</h1>
        <p>Manage system users</p>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">All Users ({users.length})</span>
          <button className="btn btn-primary btn-sm" onClick={() => setShowModal(true)}>
            <Plus size={14} /> Add User
          </button>
        </div>

        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Username</th>
                <th>Full Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Active</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id}>
                  <td>{u.username}</td>
                  <td>{u.full_name || '-'}</td>
                  <td>{u.email || '-'}</td>
                  <td><span className={`badge badge-${u.role === 'admin' ? 'danger' : 'info'}`}>{u.role}</span></td>
                  <td><span className={`badge badge-${u.is_active ? 'success' : 'danger'}`}>{u.is_active ? 'Yes' : 'No'}</span></td>
                  <td>{new Date(u.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3 className="modal-title">Add User</h3>
            <div className="form-group">
              <label>Username</label>
              <input className="form-control" value={newUser.username} onChange={e => setNewUser({ ...newUser, username: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Password</label>
              <input className="form-control" type="password" value={newUser.password} onChange={e => setNewUser({ ...newUser, password: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Full Name</label>
              <input className="form-control" value={newUser.full_name} onChange={e => setNewUser({ ...newUser, full_name: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Email</label>
              <input className="form-control" type="email" value={newUser.email} onChange={e => setNewUser({ ...newUser, email: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Role</label>
              <select className="form-control" value={newUser.role} onChange={e => setNewUser({ ...newUser, role: e.target.value })}>
                <option value="employee">Employee</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleCreate}>Create</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
