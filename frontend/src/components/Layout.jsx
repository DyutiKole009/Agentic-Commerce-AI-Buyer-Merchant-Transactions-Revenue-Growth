import React from 'react';
import { Activity, FileCog, Globe2, LayoutDashboard, LogOut, RefreshCw, Sparkles, Store } from 'lucide-react';

export default function Layout({ view, setView, session, system, merchant, customer, onReset, onLogout, onActivity, children }) {
  const items = [
    ...(customer ? [['journey', 'Customer journey', LayoutDashboard]] : [['customer-auth', 'Customer sign in', FileCog]]),
    ...(merchant ? [['growth', 'Merchant growth', Store], ['admin', 'Policy & catalog', FileCog]] : []),
    ['auth', merchant ? 'Merchant account' : 'Merchant login', FileCog],
    ['protocols', 'Protocol bridge', Globe2],
    ['observability', 'Observability', Activity]
  ];
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><span className="brand-mark"><Sparkles size={18} /></span><span><b>Commerce OS</b><small>Agent operations</small></span></div><div className="workspace"><i /> Razorpay {system?.razorpay?.environment || 'test'} mode <span>⌄</span></div><nav>{items.map(([id, label, Icon]) => <button key={id} className={view === id ? 'nav-item active' : 'nav-item'} onClick={() => setView(id)}><Icon size={17} />{label}</button>)}</nav><div className="sidebar-bottom"><div className="side-status"><i /><span><b>All systems operational</b><small>{system?.razorpay?.using_real_api ? 'Razorpay test API connected' : 'Local test simulator'}</small></span></div><div className="agent-list"><small>ACTIVE AGENTS</small><span>● Buyer agent <em>ready</em></span><span>● Policy engine <em>ready</em></span><span>● Verification <em>ready</em></span></div></div></aside><div className="main-area"><header className="topbar"><div><span className="breadcrumb">Workspace / {items.find((item) => item[0] === view)?.[1]}</span><h1>{items.find((item) => item[0] === view)?.[1]}</h1></div><div className="top-actions"><span className="session-pill">{session?.session_id || merchant?.merchant_id || customer?.email || 'Customer sign in'}</span>{customer && <button className="activity-button top-activity" onClick={onActivity}><Activity size={13} /> View activity</button>}<button className="icon-button" title="Reset session" onClick={onReset}><RefreshCw size={16} /></button>{(customer || merchant) && <button className="icon-button" title="Sign out" onClick={onLogout}><LogOut size={16} /></button>}<div className="avatar">{customer ? customer.customer_name?.slice(0, 2).toUpperCase() : merchant ? merchant.merchant_name?.slice(0, 2).toUpperCase() : 'C'}</div></div></header><main className="content">{children}</main></div></div>;
}
