import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

export const money = (v) => '₹' + Number(v).toLocaleString('en-IN', { minimumFractionDigits: 2 })

export function useLoad(path) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const load = useCallback(() => api.get(path).then(setData).catch((e) => setErr(e.message)), [path])
  useEffect(() => { load() }, [load])
  return [data, load, err]
}
// run an action, then refresh; show errors instead of crashing
export const act = (fn, reload) => fn().then(reload).catch((e) => alert(e.message))

export function Form({ fields, onSubmit, button }) {
  const init = Object.fromEntries(fields.map((f) => [f.name, f.value ?? '']))
  const [v, setV] = useState(init)
  const [hint, setHint] = useState('')
  return (
    <form className="row" onSubmit={(e) => { e.preventDefault(); onSubmit(v).then(() => { setV(init); setHint('') }).catch((x) => alert(x.message)) }}>
      {fields.map((f) => f.options ? (
        <select key={f.name} value={v[f.name]} title={f.label} onChange={(e) => setV({ ...v, [f.name]: e.target.value })}>
          {f.options.map((o) => <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>)}
        </select>
      ) : f.type === 'date' ? (
        <label key={f.name} className="fld">{f.label}
          <input type="date" value={v[f.name]} required={f.required !== false} onChange={(e) => setV({ ...v, [f.name]: e.target.value })} />
        </label>
      ) : (
        <input key={f.name} type={f.type || 'text'} placeholder={f.label} title={f.label} value={v[f.name]} required={f.required !== false}
          step={f.type === 'number' ? '0.01' : undefined} onChange={(e) => setV({ ...v, [f.name]: e.target.value })}
          onBlur={f.fill ? () => f.fill(v[f.name]).then((r) => { if (r) { setV((c) => ({ ...c, ...r.patch })); setHint(r.hint) } }).catch(() => {}) : undefined} />
      ))}
      {hint && <small className="hint">{hint}</small>}
      <button>{button}</button>
    </form>
  )
}

export function Dashboard({ go }) {
  const [d, , err] = useLoad('/dashboard')
  const [ins] = useLoad('/insights')
  if (err) return <p className="err">{err}</p>
  if (!d) return <p>Loading…</p>
  const { bills, expenses, grocery, trips } = d
  return (
    <div className="grid">
      {ins && (ins.highlights.length > 0 || ins.bills.length > 0) && (
        <section className="card wide">
          <h2>✨ Smart insights</h2>
          {ins.highlights.map((h, i) => <p key={i}>{h}</p>)}
          {ins.bills.map((b) => <p key={b.bill_id}>{b.bill_name}: next bill expected around {money(b.forecast_next)} <small>(from your last {b.payments_used} payments)</small></p>)}
        </section>
      )}
      <section className="card" onClick={() => go('Bills')}>
        <h2>Daily Bills</h2>
        <p className="big">{bills.reminder_count} to pay · {money(bills.amount_due)}</p>
        <p>{bills.overdue_count} overdue · paid this month {money(bills.paid_this_month)}</p>
        {bills.reminders.map((r) => <p key={r.id} className={r.status}>{r.bill_name} — due {r.due_date} <i>{r.status}</i></p>)}
      </section>
      <section className="card" onClick={() => go('Expenses')}>
        <h2>Expenses ({expenses.month})</h2>
        <p className="big">{money(expenses.month_total)}</p>
        {expenses.recent.map((e) => <p key={e.id}>{e.title} — {money(e.amount)}</p>)}
      </section>
      <section className="card" onClick={() => go('Grocery')}>
        <h2>Grocery</h2>
        <p className="big">{grocery.remaining} to buy</p>
        <p>{grocery.bought} bought · about {money(grocery.estimated_remaining_cost)} left</p>
      </section>
      <section className="card" onClick={() => go('Trips')}>
        <h2>Trips</h2>
        {trips.upcoming.length === 0 && <p>No upcoming trips</p>}
        {trips.upcoming.map((t) => <p key={t.id}>{t.name} — {t.start_date} <i>{t.status}</i> · spent {money(t.total_spent)}</p>)}
      </section>
    </div>
  )
}

export function Bills() {
  const [occ, reload, err] = useLoad('/occurrences')
  const pay = (o) => {
    const a = prompt(`Amount paid for ${o.bill_name}?`, o.expected_amount)
    if (a !== null) act(() => api.post(`/occurrences/${o.id}/pay`, { amount: a }), reload)
  }
  const open = (occ || []).filter((o) => !['PAID', 'SKIPPED'].includes(o.status))
  const done = (occ || []).filter((o) => ['PAID', 'SKIPPED'].includes(o.status)).slice(-10).reverse()
  return (
    <>
      <Form button="Add bill" onSubmit={(v) => api.post('/bills', { ...v, reminder_days_before: Number(v.days) }).then(reload)} fields={[
        { name: 'name', label: 'Bill name' }, { name: 'type', options: ['INTERNET', 'MILK', 'ELECTRICITY', 'WATER', 'RENT', 'SUBSCRIPTION', 'MOBILE', 'OTHER'], value: 'OTHER' },
        { name: 'default_amount', label: 'Amount', type: 'number' }, { name: 'first_due_date', label: 'First due date', type: 'date' },
        { name: 'days', label: 'Remind days before', type: 'number', value: 3 },
      ]} />
      {err && <p className="err">{err}</p>}
      <h2>To pay</h2>
      {open.length === 0 && <p>Nothing pending 🎉</p>}
      {open.map((o) => (
        <label key={o.id} className={'item ' + o.status}>
          <input type="checkbox" checked={false} onChange={() => pay(o)} />
          <span>{o.bill_name} — {money(o.expected_amount)}<small>due {o.due_date} · {o.status}</small></span>
          <button className="link" onClick={(e) => { e.preventDefault(); act(() => api.post(`/occurrences/${o.id}/skip`), reload) }}>skip</button>
        </label>
      ))}
      <h2>Recent history</h2>
      {done.map((o) => (
        <label key={o.id} className="item done">
          <input type="checkbox" checked readOnly onClick={() => act(() => api.post(`/occurrences/${o.id}/undo`), reload)} />
          <span>{o.bill_name} — {o.status === 'PAID' ? money(o.paid_amount) + ' paid ' + o.paid_on : 'skipped'}<small>due {o.due_date}</small></span>
        </label>
      ))}
    </>
  )
}

// AI: ask the backend which category a title belongs to; only auto-fill when it is confident
const suggest = async (title) => {
  if (title.trim().length < 3) return null
  const s = await api.get('/expenses/suggest-category?title=' + encodeURIComponent(title.trim()))
  if (!s.confident) return null
  return { patch: { category: s.category }, hint: `✨ Suggested category: ${s.category} (${Math.round(s.confidence * 100)}%${s.source === 'history' ? ', from your past expenses' : ''})` }
}

export function Expenses() {
  const [list, reload, err] = useLoad('/expenses?limit=30')
  const [sum, reloadSum] = useLoad('/expenses/summary')
  const both = () => { reload(); reloadSum() }
  return (
    <>
      <Form button="Add expense" onSubmit={(v) => api.post('/expenses', v).then(both)} fields={[
        { name: 'title', label: 'What for? (category is suggested)', fill: suggest }, { name: 'amount', label: 'Amount', type: 'number' },
        { name: 'category', options: ['FOOD', 'TRAVEL', 'SHOPPING', 'EDUCATION', 'HEALTH', 'ENTERTAINMENT', 'UTILITIES', 'OTHER'], value: 'FOOD' },
      ]} />
      {err && <p className="err">{err}</p>}
      {sum && <div className="card"><h2>This month: {money(sum.total)}</h2>
        {sum.by_category.map((c) => <p key={c.category}>{c.category}: {money(c.total)} ({c.count})</p>)}
        <small>Last month: {money(sum.previous_month_total)}</small></div>}
      {(list || []).map((e) => (
        <div key={e.id} className="item">
          <span>{e.title} — {money(e.amount)}<small>{e.spent_on} · {e.category}</small></span>
          <button className="link" onClick={() => confirm('Delete?') && act(() => api.del(`/expenses/${e.id}`), both)}>delete</button>
        </div>
      ))}
    </>
  )
}

export function Grocery() {
  const [items, reload, err] = useLoad('/grocery/items')
  const todo = (items || []).filter((i) => !i.is_bought)
  const bought = (items || []).filter((i) => i.is_bought)
  const row = (i) => (
    <label key={i.id} className={'item ' + (i.is_bought ? 'done' : '')}>
      <input type="checkbox" checked={i.is_bought} onChange={() => act(() => api.patch(`/grocery/items/${i.id}`, { is_bought: !i.is_bought }), reload)} />
      <span>{i.name}<small>{i.quantity} · {i.category}</small></span>
      <button className="link" onClick={(e) => { e.preventDefault(); act(() => api.del(`/grocery/items/${i.id}`), reload) }}>✕</button>
    </label>
  )
  return (
    <>
      <Form button="Add" onSubmit={(v) => api.post('/grocery/items', v).then(reload)} fields={[
        { name: 'name', label: 'Item' }, { name: 'quantity', label: 'Qty (2 kg)', value: '1' },
        { name: 'category', options: ['VEGETABLES', 'FRUITS', 'DAIRY', 'GRAINS', 'SNACKS', 'HOUSEHOLD', 'PERSONAL_CARE', 'OTHER'], value: 'OTHER' },
      ]} />
      {err && <p className="err">{err}</p>}
      <h2>To buy ({todo.length})</h2>
      {todo.map(row)}
      <h2>Bought ({bought.length})</h2>
      {bought.map(row)}
      {bought.length > 0 && <button onClick={() => act(() => api.post('/grocery/clear-completed'), reload)}>Clear completed</button>}
    </>
  )
}
