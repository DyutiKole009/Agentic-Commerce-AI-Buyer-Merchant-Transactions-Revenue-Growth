import React, { useState } from 'react';
import { ArrowRight, BarChart3, Sparkles } from 'lucide-react';

const money = (value) => `₹${Math.round(value || 0).toLocaleString('en-IN')}`;

export default function GrowthPage({ merchant, loading, run, post }) {
  const [approvalPassword, setApprovalPassword] = useState('');
  const [approvalError, setApprovalError] = useState('');
  if (!merchant) return <section className="card login-required"><p className="eyebrow">MERCHANT PERFORMANCE</p><h3>Merchant login required</h3><p>Sign in from Policy & merchants to view this merchant's revenue and growth recommendations.</p></section>;
  const metric = merchant.metrics;
  const item = merchant.opportunities?.[0];
  const approve = async () => {
    setApprovalError('');
    try {
      await run('Merchant approval', () => post(`/merchant/opportunities/${item.opportunity_id}/approve`, { approved_by: merchant.merchant_id, merchant_id: merchant.merchant_id, merchant_token: merchant.token, password: merchant.token ? undefined : approvalPassword }));
      setApprovalPassword('');
    } catch (error) {
      setApprovalError(error.message || 'Merchant approval failed');
    }
  };
  return <><section className="page-intro"><p className="eyebrow">MERCHANT PERFORMANCE</p><h2>Turn agent intelligence into<br /><em>measurable growth.</em></h2><p>Review evidence-backed opportunities, approve them deliberately, and watch performance move.</p></section><div className="stats"><Stat label="Revenue" value={money(metric?.revenue)} note="Current period" /><Stat label="Agent revenue" value={money(metric?.agent_generated_revenue)} note="Attributed to agents" /><Stat label="Average order value" value={money(metric?.average_order_value)} note="Across transactions" /><Stat label="Conversion" value={`${(metric?.conversion_rate || 0) * 100}%`} note="Session conversion" /></div><div className="stats growth-stats"><Stat label="Upsell offers" value={metric?.upsell_impressions || 0} note="Shown to AI buyers" /><Stat label="Accepted" value={metric?.upsell_conversions || 0} note="Measured conversions" /><Stat label="Attach rate" value={`${((metric?.upsell_attach_rate || 0) * 100).toFixed(1)}%`} note="Accepted / offered" /><Stat label="Accepted value" value={money(metric?.accepted_upsell_value)} note="Not yet captured revenue" /></div><section className="card growth-card"><div className="card-head"><div><p className="eyebrow">GROWTH OPPORTUNITY</p><h3>{item?.title || 'Loading opportunity...'}</h3></div><span className="confidence"><Sparkles size={13} /> {item ? `${Math.round(item.confidence * 100)}% confidence` : '—'}</span></div><p className="growth-copy">{item?.description}</p><div className="growth-metrics"><div><small>Expected uplift</small><b>{money(item?.expected_uplift)}</b><em>{item?.evidence_status === 'MEASURED' ? 'Observed estimate' : 'Forecast only'}</em></div><div><small>Recommended price</small><b>{money(item?.recommended_price)}</b></div><div><small>Evidence</small><b>{item?.evidence_status || 'ESTIMATE'}</b></div><div><small>Policy status</small><b>{item?.policy_status || 'PENDING'}</b></div></div>{item && item.status === 'PROPOSED' && <div className="merchant-approval"><small>MERCHANT APPROVAL REQUIRED</small><p>Only the authorized merchant can approve this growth proposal.</p><input type="password" value={approvalPassword} onChange={(event) => setApprovalPassword(event.target.value)} placeholder="Merchant password" /><button disabled={loading || !approvalPassword} onClick={approve} className="button">Approve as {merchant.merchant_name} <ArrowRight size={15} /></button>{approvalError && <span className="approval-error">{approvalError}</span>}</div>}{item && item.status === 'APPROVED' && <button disabled={loading} onClick={() => run('Growth action', () => post(`/merchant/opportunities/${item.opportunity_id}/execute`))} className="button">Execute campaign <ArrowRight size={15} /></button>}{item && item.status === 'EXECUTED' && <span className="growth-live">Campaign live</span>}</section></>;
}

function Stat({ label, value, note }) { return <div className="stat"><small><BarChart3 size={14} /> {label}</small><b>{value}</b><em>{note}</em></div>; }
