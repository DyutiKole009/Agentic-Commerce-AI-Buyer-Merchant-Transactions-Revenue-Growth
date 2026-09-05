import React from 'react';
import { ArrowUpRight, TrendingUp } from 'lucide-react';
import './revenueGrowth.css';

const money = (value) => `₹${Math.round(value || 0).toLocaleString('en-IN')}`;

export default function RevenueGrowthPanel({ merchant }) {
  const metric = merchant?.metrics || {};
  const opportunity = merchant?.opportunities?.[0];
  const impressions = metric.upsell_impressions || 0;
  const conversions = metric.upsell_conversions || 0;
  const attachRate = Number(metric.upsell_attach_rate || 0) * 100;
  const acceptedValue = metric.accepted_upsell_value || 0;
  const projectedValue = opportunity?.expected_uplift || 0;

  return <section className="card revenue-growth-panel">
    <div className="card-head"><div><p className="eyebrow">REVENUE GROWTH</p><h3>How the agent grows the basket</h3></div><TrendingUp className="teal-icon" size={18} /></div>
    <p className="revenue-growth-copy">The merchant-side agent identifies a relevant add-on, presents it at checkout, and measures whether the customer buys more.</p>
    <div className="revenue-growth-path"><span>Base purchase</span><ArrowUpRight size={14} /><span>Relevant add-on offered</span><ArrowUpRight size={14} /><strong>Higher basket value</strong></div>
    <div className="revenue-growth-metrics"><Metric label="Buyers shown an add-on" value={impressions} note="Upsell impressions" /><Metric label="Buyers convinced" value={conversions} note="Accepted add-ons" /><Metric label="Conversion to add-on" value={`${attachRate.toFixed(1)}%`} note="Attach rate" /><Metric label="Extra revenue" value={money(acceptedValue)} note={acceptedValue ? 'Measured accepted value' : 'No accepted value yet'} /></div>
    {opportunity && <div className="revenue-growth-opportunity"><div><small>NEXT RECOMMENDATION</small><b>{opportunity.recommended_product_title}</b><p>Offer at {money(opportunity.recommended_price)} with a projected uplift of {money(projectedValue)}.</p></div><span>{opportunity.status}</span></div>}
  </section>;
}

function Metric({ label, value, note }) { return <div><small>{label}</small><b>{value}</b><em>{note}</em></div>; }
