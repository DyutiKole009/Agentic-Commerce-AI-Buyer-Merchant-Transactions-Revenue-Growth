import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, ExternalLink, Globe2, LoaderCircle, Radio, ShieldAlert } from 'lucide-react';

const API_ROOT = 'http://127.0.0.1:8000';
const API = `${API_ROOT}/api/v1`;
const protocols = [
  { id: 'uap', label: 'UAP', tone: 'teal' },
  { id: 'ap2', label: 'Google AP2', tone: 'amber' },
  { id: 'acp', label: 'OpenAI ACP', tone: 'blue' },
  { id: 'x402', label: 'x402 / L402', tone: 'coral' },
];

const intent = {
  category: 'wireless headphones',
  max_price: 5000,
  use_case: 'daily commuting',
  priorities: ['noise cancellation', 'battery life'],
};

export default function ProtocolPage() {
  const [manifest, setManifest] = useState(null);
  const [catalog, setCatalog] = useState(null);
  const [selected, setSelected] = useState('uap');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const merchantId = catalog?.merchants?.[0];
  const productCount = catalog?.products?.length || 0;
  const selectedProtocol = useMemo(() => protocols.find((item) => item.id === selected), [selected]);

  useEffect(() => {
    Promise.all([
      fetch(`${API_ROOT}/.well-known/agent-manifest.json`).then((response) => response.json()),
      fetch(`${API}/agent/catalog`).then((response) => response.json()),
    ]).then(([discovered, products]) => {
      setManifest(discovered);
      setCatalog(products);
    }).catch((requestError) => setError(requestError.message));
  }, []);

  const runProtocol = async () => {
    if (!merchantId) return;
    setLoading(true);
    setError('');
    setResult(null);
    const endpoint = `${API}/agent/merchants/${encodeURIComponent(merchantId)}/${selected}/query`;
    const body = { buyer_agent_id: 'frontend-demo-agent', intent_spec: intent, request_id: `demo-${Date.now()}` };
    try {
      const response = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const text = await response.text();
      let payload;
      try { payload = JSON.parse(text); } catch { payload = text; }
      setResult({ status: response.status, protocol: response.headers.get('X-Agent-Protocol'), version: response.headers.get('X-Agent-Protocol-Version'), payment: response.headers.get('PAYMENT-REQUIRED'), payload });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  return <div className="protocol-page">
    <section className="page-intro protocol-intro"><p className="eyebrow">GLOBAL PROTOCOL BRIDGE</p><h2>One catalog.<br /><em>Every agent.</em></h2><p>Live discovery and adapter checks for the merchant network.</p><div className="protocol-links"><a href={`${API_ROOT}/.well-known/agent-manifest.json`} target="_blank" rel="noreferrer">Manifest <ExternalLink size={13} /></a><a href={`${API_ROOT}/ai-plugin.json`} target="_blank" rel="noreferrer">Plugin card <ExternalLink size={13} /></a><a href={`${API_ROOT}/docs`} target="_blank" rel="noreferrer">OpenAPI <ExternalLink size={13} /></a></div></section>
    {error && <div className="error-banner">{error}</div>}
    <div className="protocol-stats"><div className="stat"><small><Globe2 size={14} /> Discovery</small><b>{manifest ? 'Online' : 'Loading'}</b><em>agent-manifest.json</em></div><div className="stat"><small><Radio size={14} /> Merchant</small><b>{merchantId || 'Waiting'}</b><em>{productCount} catalog products</em></div><div className="stat"><small><CheckCircle2 size={14} /> Capabilities</small><b>{manifest?.capabilities?.length || 0}</b><em>Advertised actions</em></div><div className="stat"><small><ShieldAlert size={14} /> Payment rail</small><b>x402 ready</b><em>Challenge on demand</em></div></div>
    <div className="protocol-layout"><section className="card protocol-console"><div className="card-head"><div><p className="eyebrow">ADAPTER TESTER</p><h3>Send a commerce intent</h3></div><span className={`protocol-badge ${selectedProtocol?.tone}`}>{selectedProtocol?.label}</span></div><div className="protocol-tabs">{protocols.map((item) => <button key={item.id} className={selected === item.id ? 'protocol-tab active' : 'protocol-tab'} onClick={() => { setSelected(item.id); setResult(null); }}>{item.label}</button>)}</div><div className="intent-preview"><span>buyer_agent_id</span><b>frontend-demo-agent</b><span>intent_spec</span><b>headphones · INR 5,000 · commuting</b></div><button className="button protocol-run" disabled={!merchantId || loading} onClick={runProtocol}>{loading ? <LoaderCircle className="spin" size={15} /> : <Radio size={15} />} {loading ? 'Sending...' : `Send via ${selectedProtocol?.label}`}</button></section><section className="card protocol-result"><div className="card-head"><div><p className="eyebrow">WIRE RESPONSE</p><h3>{result ? `${result.status} response` : 'Waiting for a request'}</h3></div>{result?.status === 402 && <span className="response-chip challenge">Payment required</span>}</div>{result ? <><div className="header-grid"><span>Protocol header<b>{result.protocol || 'Not returned'}</b></span><span>Version<b>{result.version || 'Not returned'}</b></span><span>Status<b className={result.status >= 400 ? 'warn' : 'ok'}>{result.status}</b></span></div>{result.payment && <div className="challenge-box"><ShieldAlert size={16} /><div><b>PAYMENT-REQUIRED</b><small>{result.payment.slice(0, 72)}...</small></div></div>}<pre className="protocol-json">{JSON.stringify(result.payload, null, 2)}</pre></> : <div className="empty">Choose an adapter and send the shared intent.</div>}</section></div>
  </div>;
}