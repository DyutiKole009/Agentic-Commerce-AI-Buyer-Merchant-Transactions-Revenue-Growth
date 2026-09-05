import React from 'react';
import { FileCheck2, ShieldCheck } from 'lucide-react';

const formatDate = (value) => value ? new Date(value).toLocaleString() : 'Not recorded';
const checks = (value) => Object.entries(value || {});

export default function PolicyDecision({ session, audience = 'buyer' }) {
  const decision = session?.authorization_result;
  const details = decision?.details || {};
  if (!decision) return null;
  const buyerView = audience === 'buyer';
  return <section className="card policy-decision-card"><div className="card-head"><div><p className="eyebrow">POLICY EXPLAINABILITY</p><h3>{buyerView ? 'Why this purchase was allowed' : 'Policy decision record'}</h3></div><ShieldCheck className="teal-icon" size={18} /></div><div className="policy-decision-status"><FileCheck2 size={16} /><b>{decision.status}</b><span>{decision.is_authorized ? 'Authorization granted' : 'Approval required before payment'}</span></div><div className="policy-facts"><Fact label="Policy ID" value={details.policy_id || 'static_default'} /><Fact label="Version" value={details.policy_version ?? 0} /><Fact label="Effective from" value={formatDate(details.policy_effective_from)} /><Fact label="Requested amount" value={`₹${Math.round(decision.requested_amount || 0).toLocaleString('en-IN')}`} /></div><div className="policy-reason"><small>Decision reason</small><p>{decision.reason}</p></div>{checks(decision.policy_checks).length > 0 && <div className="policy-checks"><small>Policy checks</small>{checks(decision.policy_checks).map(([label, passed]) => <span className={passed ? 'policy-check pass' : 'policy-check fail'} key={label}><b>{passed ? 'PASS' : 'FAIL'}</b>{label.replaceAll('_', ' ')}</span>)}</div>}{details.retrieved_clauses?.length > 0 && <div className="policy-clauses"><small>Retrieved policy clauses</small>{details.retrieved_clauses.map((clause, index) => <p key={`${clause}-${index}`}>{clause}</p>)}</div>}{!buyerView && <div className="policy-provenance"><small>Merchant audit provenance</small><Fact label="Source document" value={details.policy_source || 'Not recorded'} /><Fact label="Policy hash" value={details.policy_hash || 'Not recorded'} /><Fact label="Effective to" value={formatDate(details.policy_effective_to)} /></div>}</section>;
}

function Fact({ label, value }) { return <div className="policy-fact"><small>{label}</small><b>{value}</b></div>; }
