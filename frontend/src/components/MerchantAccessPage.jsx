import React, { useState } from 'react';
import { ArrowRight, Check, LockKeyhole, Store } from 'lucide-react';
import '../admin.css';

export default function MerchantAccessPage({ request, run, onMerchantAuthenticated }) {
  const [mode, setMode] = useState('login');
  const [login, setLogin] = useState({ merchant_id: '', password: '' });
  const [merchant, setMerchant] = useState({ merchant_id: '', merchant_name: '', agent_name: '', endpoint: 'http://localhost:8000/api/v1/agent', password: '' });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const update = (setter) => (event) => setter((value) => ({ ...value, [event.target.name]: event.target.value }));
  const submit = async () => {
    setError(''); setMessage('');
    try {
      if (mode === 'register') {
        await request('/agent/merchants/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(merchant) });
        setLogin({ merchant_id: merchant.merchant_id, password: merchant.password }); setMode('login'); setMessage('Merchant registered. Sign in to open the workspace.');
      } else {
        const result = await request('/agent/merchants/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(login) });
        await onMerchantAuthenticated({ ...result.merchant, token: result.token });
      }
    } catch (err) { setError(err.message || 'Request failed'); }
  };
  return <div className="access-page"><section className="page-intro"><p className="eyebrow">MERCHANT ACCESS</p><h2>Connect your<br /><em>commerce agent.</em></h2><p>Register an account or sign in to manage the catalog, policy, and revenue workspace.</p></section><section className="card access-card"><div className="access-tabs"><button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Sign in</button><button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Register</button></div>{error && <div className="error-banner">{error}</div>}{message && <div className="result-line"><Check size={15} /> {message}</div>}{mode === 'login' ? <><label>Merchant ID<input name="merchant_id" value={login.merchant_id} onChange={update(setLogin)} /></label><label>Password<input name="password" type="password" value={login.password} onChange={update(setLogin)} /></label></> : <div className="form-grid">{[['merchant_id','Merchant ID'],['merchant_name','Merchant name'],['agent_name','Agent name'],['password','Password (8+ chars)']].map(([name, label]) => <label key={name}>{label}<input name={name} type={name === 'password' ? 'password' : 'text'} value={merchant[name]} onChange={update(setMerchant)} /></label>)}</div>}{mode === 'register' && <label>Network endpoint<input name="endpoint" value={merchant.endpoint} onChange={update(setMerchant)} /></label>}<button className="button" onClick={() => run(mode === 'login' ? 'Merchant login' : 'Merchant registration', submit)}><LockKeyhole size={15} /> {mode === 'login' ? 'Sign in' : 'Create merchant account'} <ArrowRight size={15} /></button><div className="access-note"><Store size={15} /> One login unlocks your policy, catalog, and growth workspace.</div></section></div>;
}
