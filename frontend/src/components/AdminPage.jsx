import React, { useEffect, useState } from 'react';
import { Check, FileUp, Plus, RefreshCw, Store } from 'lucide-react';
import '../admin.css';
import PolicyDecision from './PolicyDecision.jsx';

export default function AdminPage({ request, run, merchant, session }) {
  const [policy, setPolicy] = useState(null);
  const [file, setFile] = useState(null);
  const [uploaded, setUploaded] = useState(null);
  const [catalog, setCatalog] = useState(null);
  const [product, setProduct] = useState({ title: '', category: 'wireless headphones', price: '', stock_count: 1, delivery_days: 3 });
  const [error, setError] = useState('');
  const merchantId = merchant?.merchant_id;
  const load = async () => {
    if (!merchantId) return;
    const [catalogResult, policyResult] = await Promise.allSettled([
      request(`/agent/merchants/${encodeURIComponent(merchantId)}/catalog`),
      request(`/policy/documents/current?merchant_id=${encodeURIComponent(merchantId)}`),
    ]);
    if (catalogResult.status === 'fulfilled') setCatalog(catalogResult.value);
    if (policyResult.status === 'fulfilled') setPolicy(policyResult.value);
    const failures = [catalogResult, policyResult].filter((result) => result.status === 'rejected');
    if (failures.length) throw new Error(failures.map((result) => result.reason?.message || 'Request failed').join(' | '));
  };
  useEffect(() => { load().catch((err) => setError(err.message)); }, [merchantId]);
  const action = async (label, callback) => { setError(''); try { await run(label, callback); await load(); } catch (err) { setError(err.message); } };
  const upload = async () => {
    const form = new FormData();
    form.append('file', file);
    setUploaded(await request(`/policy/documents/upload?merchant_id=${encodeURIComponent(merchantId)}`, { method: 'POST', headers: merchant?.token ? { Authorization: `Bearer ${merchant.token}` } : {}, body: form }));
  };
  const addProduct = async () => { const result = await request(`/agent/merchants/${encodeURIComponent(merchantId)}/products`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...product, merchant_token: merchant.token, price: Number(product.price), stock_count: Number(product.stock_count), delivery_days: Number(product.delivery_days) }) }); setCatalog(result.catalog); setProduct({ ...product, title: '', price: '' }); };
  const updateProduct = (event) => setProduct({ ...product, [event.target.name]: event.target.value });
  return <div className="admin-page"><section className="page-intro"><p className="eyebrow">MERCHANT WORKSPACE</p><h2>{merchant?.merchant_name}<br /><em>policy and catalog.</em></h2><p>Manage the signed-in merchant account from one authenticated workspace.</p></section>{error && <div className="error-banner">{error}</div>}<div className="admin-grid">
    <section className="card admin-card"><div className="card-head"><div><p className="eyebrow">01 · POLICY</p><h3>Policy document</h3></div><button className="icon-button" title="Refresh policy and catalog" onClick={() => load().catch((err) => setError(err.message))}><RefreshCw size={15} /></button></div><div className="policy-current">{policy?.active ? <><span className="status-dot" /><div><b>Version {policy.version}</b><small>{policy.source_name}</small></div></> : <span>{policy?.message || 'No active policy for this merchant'}</span>}</div><label className="file-drop"><FileUp size={18} /><span>{file?.name || 'Choose PDF or DOCX'}</span><input type="file" accept=".pdf,.docx" onChange={(event) => setFile(event.target.files?.[0])} /></label><button className="button" disabled={!file} onClick={() => action('Upload policy', upload)}>Upload policy <FileUp size={15} /></button>{uploaded && <><div className="result-line"><Check size={15} /> Uploaded version {uploaded.version}.</div><button className="button secondary" onClick={() => action('Activate policy', async () => { const result = await request(`/policy/documents/${uploaded.policy_id}/${uploaded.version}/activate?merchant_id=${encodeURIComponent(merchantId)}`, { method: 'POST', headers: merchant?.token ? { Authorization: `Bearer ${merchant.token}` } : {} }); setPolicy(result); setUploaded(null); })}>Activate version {uploaded.version}</button></>}</section>
    <section className="card admin-card"><div className="card-head"><div><p className="eyebrow">02 · CATALOG</p><h3>{catalog?.merchant_name || 'Catalog'}</h3></div><Store className="teal-icon" size={18} /></div><div className="catalog-result">{catalog?.products?.length ? catalog.products.map((item) => <div key={item.product_id}><span>{item.title}<small>{item.category} · {item.stock_count} in stock</small></span><strong>₹{Math.round(item.base_price).toLocaleString('en-IN')}</strong></div>) : <span>No products in this catalog.</span>}</div></section>
    <section className="card admin-card add-product-card"><div className="card-head"><div><p className="eyebrow">03 · ADD PRODUCT</p><h3>Add a catalog product</h3></div><Plus className="teal-icon" size={18} /></div><div className="add-product"><div className="form-grid">{[['title','Product title'],['category','Category'],['price','Price (INR)'],['stock_count','Stock'],['delivery_days','Delivery days']].map(([name, label]) => <label key={name}>{label}<input name={name} type={['price','stock_count','delivery_days'].includes(name) ? 'number' : 'text'} value={product[name]} onChange={updateProduct} /></label>)}</div><button className="button secondary" onClick={() => action('Add product', addProduct)}><Plus size={15} /> Add product</button></div></section>
  </div><PolicyDecision session={session} audience="merchant" /></div>;
}
