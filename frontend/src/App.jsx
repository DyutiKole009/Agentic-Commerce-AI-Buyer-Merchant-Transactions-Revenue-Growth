import React, { useEffect, useMemo, useState } from 'react';
import Layout from './components/Layout.jsx';
import BuyerJourney from './components/BuyerJourneyInteractive.jsx';
import GrowthPage from './components/GrowthPage.jsx';
import RevenueGrowthPanel from './components/RevenueGrowthPanel.jsx';
import ObservabilityPage from './components/ObservabilityPage.jsx';
import AdminPage from './components/AdminPage.jsx';
import MerchantAccessPage from './components/MerchantAccessPage.jsx';
import ActivityDrawer from './components/ActivityDrawer.jsx';
import A2AConversation from './components/A2AConversation.jsx';
import TransactionProof from './components/TransactionProof.jsx';
import PolicyDecision from './components/PolicyDecision.jsx';
import CustomerAccessPage from './components/CustomerAccessPage.jsx';
import ProtocolPage from './components/ProtocolPage.jsx';
import './app.css';

const API = 'http://127.0.0.1:8000/api/v1';
const readStored = (key) => { try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch { return null; } };
const request = async (path, options = {}) => { const method = options.method || 'GET'; const started = performance.now(); const response = await fetch(`${API}${path}`, options); window.dispatchEvent(new CustomEvent('api-call', { detail: { method, path, status: response.status, latency: Math.round(performance.now() - started) } })); if (!response.ok) throw new Error(await response.text()); return response.json(); };
const post = (path, body = {}) => request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export default function App() {
  const [view, setView] = useState(() => readStored('commerce_merchant') ? 'admin' : readStored('commerce_customer') ? 'journey' : 'customer-auth');
  const [session, setSession] = useState(() => readStored('commerce_session'));
  const [customer, setCustomer] = useState(() => readStored('commerce_customer'));
    const [merchant, setMerchant] = useState(() => readStored('commerce_merchant'));
  const [system, setSystem] = useState(null);
  const [prompt, setPrompt] = useState('I need wireless headphones under ₹5,000 with good battery life for daily commuting. Prioritize noise cancellation.');
  const [loading, setLoading] = useState(false);
  const [activeAgent, setActiveAgent] = useState(null);
  const [error, setError] = useState('');
  const [timings, setTimings] = useState([]);
  const [usage, setUsage] = useState(null);
  const [apiCalls, setApiCalls] = useState([]);
  const [liveEvents, setLiveEvents] = useState([]);
  const [buyerDecision, setBuyerDecision] = useState(null);
  const [activityOpen, setActivityOpen] = useState(false);
  const [sessionStarting, setSessionStarting] = useState(false);

  const refresh = async (merchantId = merchant?.merchant_id) => { if (!merchantId) return; const data = await request(`/merchant/dashboard?merchant_id=${encodeURIComponent(merchantId)}`); setMerchant((current) => ({ ...data, token: current?.token, password: current?.password })); };
  const run = async (label, action) => { const start = performance.now(); setLoading(true); setActiveAgent(label.toLowerCase().includes('discover') ? 'merchant' : 'buyer'); setError(''); try { const result = await action(); if (result?.snapshot) setSession(result.snapshot); await refresh(); } catch (err) { setError(err.message || 'Request failed'); } finally { setTimings((items) => [...items.slice(-7), { label, value: Math.round(performance.now() - start) }]); setLoading(false); setActiveAgent(null); } };
  const authenticateMerchant = async (merchantData) => { setMerchant(merchantData); await refresh(merchantData.merchant_id); setView('admin'); };
  useEffect(() => { try { if (customer) localStorage.setItem('commerce_customer', JSON.stringify(customer)); else localStorage.removeItem('commerce_customer'); } catch { /* storage disabled */ } }, [customer]);
    useEffect(() => { try { if (merchant) localStorage.setItem('commerce_merchant', JSON.stringify(merchant)); else localStorage.removeItem('commerce_merchant'); } catch { /* storage disabled */ } }, [merchant]);
    const logout = async () => { const requests = []; if (customer?.token) requests.push(fetch(`${API}/customers/logout`, { method: 'POST', headers: { Authorization: `Bearer ${customer.token}` } })); if (merchant?.token) requests.push(fetch(`${API}/agent/merchants/logout`, { method: 'POST', headers: { Authorization: `Bearer ${merchant.token}` } })); await Promise.allSettled(requests); setCustomer(null); setMerchant(null); setSession(null); setView('customer-auth'); };
  useEffect(() => { try { if (session) localStorage.setItem('commerce_session', JSON.stringify(session)); else localStorage.removeItem('commerce_session'); } catch { /* storage disabled */ } }, [session]);
  useEffect(() => { request('/system/status').then(setSystem).catch((err) => setError(err.message)); }, []);
  useEffect(() => { if (!customer?.token) { setSession(null); setView('customer-auth'); return; } if (session?.session_id || sessionStarting) { setView('journey'); return; } setSessionStarting(true); post('/commerce/session/start', { customer_token: customer.token }).then((started) => { setSession(started); setView('journey'); }).catch(() => { localStorage.removeItem('commerce_customer'); localStorage.removeItem('commerce_session'); setCustomer(null); setSession(null); setView('customer-auth'); }).finally(() => setSessionStarting(false)); }, [customer?.token, session?.session_id, sessionStarting]);
  useEffect(() => { if (!session?.session_id) return; request(`/system/usage?session_id=${encodeURIComponent(session.session_id)}`).then(setUsage).catch(() => setUsage(null)); }, [session]);
  useEffect(() => { if (session?.current_state !== 'AUTHORIZED') setBuyerDecision(null); }, [session?.current_state]);
  useEffect(() => { const onApiCall = (event) => setApiCalls((items) => [...items.slice(-19), event.detail]); window.addEventListener('api-call', onApiCall); return () => window.removeEventListener('api-call', onApiCall); }, []);
  useEffect(() => { if (!session?.session_id) return undefined; setLiveEvents([]); const stream = new EventSource(`${API}/commerce/session/${session.session_id}/stream`); stream.onmessage = (event) => { const received = JSON.parse(event.data); if (received.event_type === 'CONNECTED') return; const data = received.data || {}; setLiveEvents((items) => [...items.slice(-39), { event_type: received.event_type, timestamp: received.timestamp, message: data.message || received.message, payload: data.payload || received.payload || data, data }]); }; stream.onerror = () => stream.close(); return () => stream.close(); }, [session?.session_id]);

  const activityEvents = useMemo(() => { const events = [...(session?.audit_logs || []).map((event) => ({ label: event.event_type, agent: event.payload?.from_agent || 'Commerce workflow', time: event.timestamp?.slice(11, 19), message: event.message, payload: event.payload })), ...liveEvents.map((event) => ({ label: event.event_type, agent: event.payload?.from_agent || 'Commerce workflow', time: event.timestamp?.slice(11, 19), message: event.message, payload: event.payload }))]; const seen = new Set(); return events.filter((event) => { const key = `${event.label}:${event.payload?.offer?.offer_id || event.payload?.to_agent}:${event.message}`; if (seen.has(key)) return false; seen.add(key); return true; }); }, [session?.audit_logs, liveEvents]);
  const agentTokenMetrics = useMemo(() => { const agentNames = [...new Set(activityEvents.map((event) => event.payload?.from_agent).filter(Boolean))]; return agentNames.map((agent) => { const inbound = activityEvents.filter((event) => event.payload?.to_agent === agent); const outbound = activityEvents.filter((event) => event.payload?.from_agent === agent); const input = inbound.reduce((sum, event) => sum + (event.payload?.input_tokens_estimate || Math.ceil(JSON.stringify(event.payload?.intent_spec || event.payload?.offer || event.payload || '').length / 4)), 0) || outbound.reduce((sum, event) => sum + (event.payload?.input_tokens_estimate || 0), 0); const output = outbound.reduce((sum, event) => sum + (event.payload?.output_tokens_estimate || Math.ceil(JSON.stringify(event.payload?.offer || event.payload || '').length / 4)), 0); const latencies = [...inbound, ...outbound].map((event) => event.payload?.latency_ms).filter(Number.isFinite); return { agent, calls: Math.max(inbound.length, outbound.length), input, output, latency: latencies.length ? Math.round(latencies.reduce((sum, value) => sum + value, 0) / latencies.length) : null, realTokens: usage?.by_agent?.[agent] }; }); }, [activityEvents, usage?.by_agent]);
  const negotiation = useMemo(() => activityEvents.some((event) => event.label === 'A2A_QUERY_SENT' || event.label === 'MERCHANT_OFFER_RECEIVED'), [activityEvents]);
  const revenueAdvice = merchant ? 'Increase revenue with bundles, targeted upsells, and agent-negotiated offers that protect margin while improving conversion.' : 'A merchant can increase revenue by improving conversion, raising average order value with bundles, and using agent insights to price and target offers.';
  const sendConversation = async () => { const extracted = await post('/commerce/intent/extract', { prompt, session_id: session.session_id }); return request(`/commerce/orchestrate/discover-and-score?session_id=${extracted.session_id}`, { method: 'POST' }); };
  const authenticateCustomer = async (result) => { const signedIn = { ...result.customer, token: result.token }; localStorage.setItem('commerce_customer', JSON.stringify(signedIn)); setCustomer(signedIn); setView('journey'); setSessionStarting(true); try { const started = await post('/commerce/session/start', { customer_token: result.token }); localStorage.setItem('commerce_session', JSON.stringify(started)); setSession(started); } catch (err) { localStorage.removeItem('commerce_customer'); localStorage.removeItem('commerce_session'); setCustomer(null); setSession(null); setView('customer-auth'); throw err; } finally { setSessionStarting(false); } };
  return <><Layout view={view} setView={setView} session={session} system={system} merchant={merchant} customer={customer} onReset={() => window.location.reload()} onLogout={logout} onActivity={() => setActivityOpen(true)}>
    {error && <div className="error-banner">{error}</div>}
    {view === 'customer-auth' && <CustomerAccessPage request={request} onAuthenticated={authenticateCustomer} />}
    {view === 'journey' && <div className="journey-layout"><div><BuyerJourney session={session} liveEvents={liveEvents} prompt={prompt} setPrompt={setPrompt} loading={loading} run={run} post={post} request={request} buyerDecision={buyerDecision} onUpsellDecision={(accept) => run('Customer add-on decision', async () => { const result = await post('/commerce/upsell/customer-decision', { session_id: session.session_id, accept }); setBuyerDecision(result); return result; })} /><PolicyDecision session={session} audience="buyer" /><TransactionProof session={session} buyerDecision={buyerDecision} /></div><A2AConversation session={session} liveEvents={liveEvents} buyerDecision={buyerDecision} prompt={prompt} setPrompt={setPrompt} loading={loading} thinkingAgent={activeAgent} onApprove={() => run('Buyer purchase approval', async () => { const approved = await post('/commerce/policy/grant-user-approval', { session_id: session.session_id, customer_token: customer.token }); if (approved?.fsm_state === 'AUTHORIZED') { return request(`/commerce/transaction/create-razorpay-order?session_id=${session.session_id}`, { method: 'POST' }); } return approved; })} onPay={() => run('Payment verification', () => request(`/commerce/transaction/simulate-success?session_id=${session.session_id}`, { method: 'POST' }))} onSend={() => run('Conversational buyer request', sendConversation)} /></div>}
    {view === 'growth' && <><RevenueGrowthPanel merchant={merchant} /><GrowthPage merchant={merchant} loading={loading} run={run} post={post} /></>}
    {view === 'observability' && <ObservabilityPage session={session} timings={timings} />}
    {view === 'protocols' && <ProtocolPage />}
    {view === 'auth' && <MerchantAccessPage request={request} run={run} onMerchantAuthenticated={authenticateMerchant} />}
    {view === 'admin' && <AdminPage request={request} run={run} merchant={merchant} session={session} />}
  </Layout><ActivityDrawer open={activityOpen} onClose={() => setActivityOpen(false)} title={`${view} metrics`} details={[{ label: 'Workflow state', value: session?.current_state || 'Idle' }, { label: 'Audit events', value: activityEvents.length }, { label: 'API actions', value: apiCalls.length }, { label: 'Provider tokens', value: usage?.total_tokens || 0 }, { label: 'Merchant', value: merchant?.merchant_id || 'Buyer workflow' }]} agents={agentTokenMetrics} negotiation={negotiation} revenueAdvice={revenueAdvice} apis={apiCalls} /></>;
}
