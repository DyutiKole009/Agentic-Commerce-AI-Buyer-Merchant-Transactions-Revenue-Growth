import React, { useState } from 'react';
import { ArrowRight, LockKeyhole, UserRound } from 'lucide-react';
import '../admin.css';

export default function CustomerAccessPage({ request, onAuthenticated }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ email: '', customer_name: '', password: '' });
  const [error, setError] = useState('');
  const update = (event) => setForm((value) => ({ ...value, [event.target.name]: event.target.value }));
  const submit = async () => {
    setError('');
    try {
      const result = await request(`/customers/${mode}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) });
      await onAuthenticated(result);
    } catch (err) { setError(err.message || 'Customer authentication failed'); }
  };
  return <div className="access-page"><section className="page-intro"><p className="eyebrow">CUSTOMER ACCESS</p><h2>Shop with your<br /><em>Buyer AI.</em></h2><p>Create an account so your intent, approvals, payment history, and audit trail belong to you.</p></section><section className="card access-card"><div className="access-tabs"><button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Sign in</button><button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Register</button></div>{error && <div className="error-banner">{error}</div>}{mode === 'register' && <label>Name<input name="customer_name" value={form.customer_name} onChange={update} /></label>}<label>Email<input name="email" type="email" value={form.email} onChange={update} /></label><label>Password<input name="password" type="password" value={form.password} onChange={update} placeholder="8+ characters" /></label><button className="button" disabled={!form.email || !form.password || (mode === 'register' && !form.customer_name)} onClick={submit}><LockKeyhole size={15} /> {mode === 'login' ? 'Sign in as customer' : 'Create customer account'} <ArrowRight size={15} /></button><div className="access-note"><UserRound size={15} /> Your approvals are tied to your customer account.</div></section></div>;
}
