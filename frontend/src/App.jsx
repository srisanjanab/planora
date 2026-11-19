import { useState } from 'react'
import { getToken, login, register, logout } from './api'
import { Dashboard, Bills, Expenses, Grocery } from './pages'
import { Trips } from './trips'

const TABS = { Dashboard, Bills, Expenses, Grocery, Trips }

function Auth() {
  const [mode, setMode] = useState('login')
  const [f, setF] = useState({ name: '', email: '', password: '' })
  const [err, setErr] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  async function submit(e) {
    e.preventDefault()
    setErr('')
    try {
      if (mode === 'register') await register(f.name, f.email, f.password)
      await login(f.email, f.password)
      location.reload()
    } catch (x) { setErr(x.message) }
  }
  return (
    <form className="card auth" onSubmit={submit}>
      <h1>Planora</h1>
      {mode === 'register' && <input placeholder="Name" value={f.name} onChange={set('name')} required />}
      <input type="email" placeholder="Email" value={f.email} onChange={set('email')} required />
      <input type="password" placeholder="Password (8+ characters)" value={f.password} onChange={set('password')} required minLength={8} />
      {err && <p className="err">{err}</p>}
      <button>{mode === 'login' ? 'Log in' : 'Create account'}</button>
      <a href="#" onClick={(e) => { e.preventDefault(); setMode(mode === 'login' ? 'register' : 'login') }}>
        {mode === 'login' ? 'New here? Create an account' : 'Have an account? Log in'}
      </a>
    </form>
  )
}

export default function App() {
  const [tab, setTab] = useState('Dashboard')
  if (!getToken()) return <Auth />
  const Page = TABS[tab]
  return (
    <div className="app">
      <header>
        <b>Planora</b>
        <nav>{Object.keys(TABS).map((t) => <button key={t} className={t === tab ? 'on' : ''} onClick={() => setTab(t)}>{t}</button>)}</nav>
        <button className="link" onClick={logout}>Log out</button>
      </header>
      <main><Page go={setTab} /></main>
    </div>
  )
}
