import { useState } from 'react'
import { api } from './api'
import { Form, act, money, useLoad } from './pages'

export function Trips() {
  const [open, setOpen] = useState(null)
  return open ? <TripDetail id={open} back={() => setOpen(null)} /> : <TripList onOpen={setOpen} />
}

function TripList({ onOpen }) {
  const [trips, reload, err] = useLoad('/trips')
  const create = (v) => api.post('/trips', {
    name: v.name, destination: v.destination, start_date: v.start_date, end_date: v.end_date,
    member_names: v.members.split(',').map((s) => s.trim()).filter(Boolean),
  }).then(reload)
  return (
    <>
      <Form button="Create trip" onSubmit={create} fields={[
        { name: 'name', label: 'Trip name' }, { name: 'destination', label: 'Destination', required: false },
        { name: 'start_date', label: 'Start', type: 'date' }, { name: 'end_date', label: 'End', type: 'date' },
        { name: 'members', label: 'Friends, comma separated (you are added automatically)', required: false },
      ]} />
      {err && <p className="err">{err}</p>}
      {(trips || []).map((t) => (
        <div key={t.id} className="item clickable" onClick={() => onOpen(t.id)}>
          <span>{t.name}{t.destination && ' · ' + t.destination}
            <small>{t.start_date} → {t.end_date} · {t.status} · {t.member_count} people · spent {money(t.total_spent)}</small></span>
          <button className="link" onClick={(e) => { e.stopPropagation(); confirm('Delete this trip and all its expenses?') && act(() => api.del(`/trips/${t.id}`), reload) }}>delete</button>
        </div>
      ))}
      {trips && trips.length === 0 && <p>No trips yet. Create one above.</p>}
    </>
  )
}

function TripDetail({ id, back }) {
  const [trip, reloadTrip] = useLoad(`/trips/${id}`)
  const [exps, reloadExps] = useLoad(`/trips/${id}/expenses`)
  const [rep, reloadRep] = useLoad(`/trips/${id}/settlement`)
  const all = () => { reloadTrip(); reloadExps(); reloadRep() }
  if (!trip || !exps || !rep) return <p>Loading…</p>
  const pay = (p) => confirm(`Record that ${p.from_name} paid ${p.to_name} ${money(p.amount)}?`) &&
    act(() => api.post(`/trips/${id}/settlements`, { from_member_id: p.from_member_id, to_member_id: p.to_member_id, amount: p.amount }), all)
  return (
    <>
      <button className="link" onClick={back}>← All trips</button>
      <h2>{trip.name}{trip.destination && ' · ' + trip.destination}</h2>
      <p>{trip.start_date} → {trip.end_date} · {trip.status} · spent {money(trip.total_spent)}{trip.budget ? ` of ${money(trip.budget)} budget` : ''}</p>

      <h2>Add expense (split equally between everyone)</h2>
      <Form button="Add" onSubmit={(v) => api.post(`/trips/${id}/expenses`, { title: v.title, amount: v.amount, paid_by_member_id: Number(v.paid_by) }).then(all)} fields={[
        { name: 'title', label: 'What for?' }, { name: 'amount', label: 'Amount', type: 'number' },
        { name: 'paid_by', label: 'Paid by', options: trip.members.map((m) => ({ value: m.id, label: 'Paid by ' + m.display_name })), value: trip.members[0].id },
      ]} />

      <h2>Who owes whom</h2>
      <div className="card">
        {rep.balances.map((b) => {
          const n = Number(b.balance)
          return <p key={b.member_id}>{b.name}: {n === 0 ? 'settled' : n > 0 ? <b>is owed {money(n)}</b> : <b className="OVERDUE">owes {money(-n)}</b>}</p>
        })}
      </div>
      {rep.suggested_payments.map((p, i) => (
        <div key={i} className="item"><span>{p.from_name} pays {p.to_name} {money(p.amount)}</span><button onClick={() => pay(p)}>Mark paid</button></div>
      ))}
      {exps.length > 0 && rep.suggested_payments.length === 0 && <p>All settled 🎉</p>}

      <h2>Expenses</h2>
      {exps.length === 0 && <p>No expenses yet.</p>}
      {exps.map((e) => (
        <div key={e.id} className="item">
          <span>{e.title} — {money(e.amount)}<small>{e.spent_on} · paid by {e.paid_by_name} · {e.shares.length} sharing</small></span>
          <button className="link" onClick={() => confirm('Delete this expense?') && act(() => api.del(`/trips/${id}/expenses/${e.id}`), all)}>delete</button>
        </div>
      ))}

      <h2>People</h2>
      <p>{trip.members.map((m) => m.display_name).join(', ')}</p>
      <Form button="Add person" onSubmit={(v) => api.post(`/trips/${id}/members`, { display_name: v.name }).then(all)} fields={[{ name: 'name', label: 'Name' }]} />
    </>
  )
}
