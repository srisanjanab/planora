const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'
export const getToken = () => localStorage.getItem('token')
export const logout = () => { localStorage.removeItem('token'); location.reload() }

async function req(path, { method = 'GET', body, form } = {}) {
  const headers = {}
  if (getToken()) headers.Authorization = 'Bearer ' + getToken()
  if (body) headers['Content-Type'] = 'application/json'
  const res = await fetch(BASE + path, {
    method, headers, body: form ? new URLSearchParams(form) : body && JSON.stringify(body),
  })
  if (res.status === 401 && getToken()) return logout() // token expired
  if (res.status === 204) return null
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check the values you entered')
  return data
}

export const api = {
  get: (p) => req(p),
  post: (p, body = {}) => req(p, { method: 'POST', body }),
  patch: (p, body) => req(p, { method: 'PATCH', body }),
  del: (p) => req(p, { method: 'DELETE' }),
}
export async function login(email, password) {
  const d = await req('/auth/login', { method: 'POST', form: { username: email, password } })
  localStorage.setItem('token', d.access_token)
}
export const register = (name, email, password) => req('/auth/register', { method: 'POST', body: { name, email, password } })
