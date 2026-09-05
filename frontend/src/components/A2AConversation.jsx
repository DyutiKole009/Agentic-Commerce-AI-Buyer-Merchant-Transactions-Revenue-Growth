import React from 'react';
import { ArrowUpRight, Bot, MessageSquare, UserRound } from 'lucide-react';

const protocolTypes = ['A2A_QUERY_SENT', 'MERCHANT_OFFER_RECEIVED', 'MERCHANT_APPROVAL_REQUEST', 'MERCHANT_UPSELL_OFFER', 'BUYER_SELECTION_SENT', 'BUYER_UPSELL_DECISION', 'USER_APPROVAL_GRANTED', 'AUTHORIZATION_EVALUATED', 'ORDER_CREATED', 'PAYMENT_INITIATED', 'PAYMENT_VERIFIED', 'PAYMENT_FAILED', 'FAILURE_ANALYSIS', 'RECOVERY_ACTION', 'RECOVERY_ORDER_CREATED', 'RECOVERY_RETRY_INITIATED', 'PURCHASE_ABORTED', 'PURCHASE_COMPLETED'];

export default function A2AConversation({ session, liveEvents = [], buyerDecision, prompt, setPrompt, loading, thinkingAgent, onSend, onApprove, onPay }) {
  const snapshotMessages = (session?.audit_logs || []).filter((event) => protocolTypes.includes(event.event_type));
  const liveMessages = liveEvents.filter((event) => protocolTypes.includes(event.event_type)).map((event) => ({ ...event, message: event.message || describeEvent(event) }));
  const decisionMessage = buyerDecision?.message ? [{ event_type: 'BUYER_UPSELL_DECISION', timestamp: new Date().toISOString(), message: buyerDecision.message, payload: buyerDecision }] : [];
  const messages = [...snapshotMessages, ...liveMessages, ...decisionMessage]
    .filter((event, index, items) => items.findIndex((candidate) => `${candidate.event_type}:${candidate.payload?.offer?.offer_id || candidate.payload?.to_agent}:${candidate.message}` === `${event.event_type}:${event.payload?.offer?.offer_id || event.payload?.to_agent}:${event.message}`) === index)
    .filter((event, index, items) => event.event_type !== 'A2A_QUERY_SENT' || items.findIndex((candidate) => candidate.event_type === 'A2A_QUERY_SENT' && candidate.message === event.message) === index)
    .sort((left, right) => String(left.timestamp || '').localeCompare(String(right.timestamp || '')));

  return <section className="card conversation-card">
    <div className="card-head"><div><p className="eyebrow">CUSTOMER ↔ MERCHANT SIDE</p><h3>Customer and Merchant Side</h3></div><MessageSquare className="teal-icon" size={18} /></div>
    <div className="conversation-intro">The customer sends purchase prompts. Merchant-side agents return offers, policy answers, payment updates, and confirmation.</div>
    <div className="agent-chat-legend"><span><i className="buyer-dot" /> Customer</span><span><i className="merchant-dot" /> Merchant Side</span></div>
    <div className="conversation-compose"><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Tell the merchant side what you need..." /><button className="button" disabled={loading || !prompt?.trim() || !session} onClick={onSend}>{loading ? 'Merchant side is responding...' : <>Send prompt <ArrowUpRight size={15} /></>}</button></div>
    <div className="conversation-list">
      {messages.length ? messages.map((event, index) => {
        const buyer = ['A2A_QUERY_SENT', 'BUYER_SELECTION_SENT', 'BUYER_UPSELL_DECISION', 'USER_APPROVAL_GRANTED'].includes(event.event_type);
        const title = getConversationTitle(event, buyer);
        const approvalComplete = ['AUTHORIZED', 'ORDER_CREATED', 'PAYMENT_INITIATED', 'PAYMENT_VERIFIED', 'PURCHASE_COMPLETED'].includes(session?.current_state);
        const paymentComplete = ['PAYMENT_INITIATED', 'PAYMENT_VERIFIED', 'PURCHASE_COMPLETED'].includes(session?.current_state);
        return <div className={`conversation-row ${buyer ? 'outgoing' : 'incoming'}`} key={`${event.timestamp}-${index}`}><div className="conversation-avatar">{buyer ? <UserRound size={14} /> : <Bot size={14} />}</div><div className="conversation-bubble"><div className="conversation-meta"><b>{title}</b><time>{event.timestamp?.slice(11, 19) || 'now'}</time></div><p>{cleanMessage(event.message || describeEvent(event))}</p>{event.payload?.offer && <div className="offer-preview"><span>{event.payload.offer.product_title || event.payload.offer.recommended_product_title}</span><strong>₹{Number(event.payload.offer.price || event.payload.offer.recommended_price || 0).toLocaleString('en-IN')}</strong><small>{event.payload.offer.merchant_name || 'Merchant add-on offer'}</small></div>}{event.event_type === 'MERCHANT_APPROVAL_REQUEST' && <button className="button chat-approval-button" disabled={loading || approvalComplete} onClick={onApprove}>{approvalComplete ? 'Approved' : 'Approve purchase'} {!approvalComplete && <ArrowUpRight size={15} />}</button>}{event.event_type === 'ORDER_CREATED' && <button className="button chat-approval-button" disabled={loading || paymentComplete} onClick={onPay}>{paymentComplete ? 'Payment done' : 'Pay now'} {!paymentComplete && <ArrowUpRight size={15} />}</button>}</div></div>;
      }) : <div className="conversation-empty"><MessageSquare size={15} /> Agents will chat here after you start a request.</div>}
    </div>
  </section>;
}

function getConversationTitle(event, buyer) {
  return buyer ? 'Customer' : 'Merchant Side';
}

function agentLabel(agentId) {
  if (!agentId) return 'Merchant Side Agent';
  const normalized = String(agentId).replace(/^merchant_/, '').replace(/_agent$/, '').replaceAll('_', ' ');
  if (normalized.toLowerCase().includes('orchestrator')) return 'Merchant Side';
  const label = normalized.replace(/\b\w/g, (character) => character.toUpperCase());
  return label + (String(agentId).endsWith('_agent') ? ' Agent' : '');
}

function cleanMessage(message) {
  return String(message).replace(/^(Customer|Merchant Side)\s*→\s*(Customer|Merchant Side):\s*/, '');
}

function describeEvent(event) {
  const data = event.data || event.payload || {};
  if (event.event_type === 'AUTHORIZATION_EVALUATED') return data.auth_decision?.reason || 'Policy authorization evaluated.';
  if (event.event_type === 'FAILURE_ANALYSIS') return 'Merchant Side: The Verification Agent is diagnosing the payment failure.';
  if (event.event_type === 'RECOVERY_ACTION') return `Merchant Side: Recovery is attempting to ${data.recovery_plan?.action_description || 'restore the purchase flow'}.`;
  if (event.event_type === 'RECOVERY_ORDER_CREATED') return 'Merchant Side: A replacement Razorpay order was created through the recovery flow.';
  if (event.event_type === 'RECOVERY_RETRY_INITIATED') return 'Merchant Side: The payment is being retried through an alternate Razorpay payment rail.';
  if (event.event_type === 'PURCHASE_ABORTED') return `Merchant Side: The purchase was stopped safely. ${data.reason || ''}`;
  if (event.event_type === 'USER_APPROVAL_GRANTED') return 'Customer approval granted; the purchase may proceed.';
  if (event.event_type === 'ORDER_CREATED') return 'Merchant Side: The Razorpay order has been created. Please complete the payment.';
  if (event.event_type === 'PAYMENT_INITIATED') return 'Merchant Side: Payment received. We are verifying the transaction.';
  if (event.event_type === 'PAYMENT_VERIFIED') return 'Merchant Side: Payment verified successfully. Your order has been confirmed.';
  if (event.event_type === 'PURCHASE_COMPLETED') return 'Merchant Side: Your purchase is complete.';
  if (event.event_type === 'PAYMENT_FAILED') return 'Merchant Side: Payment failed; recovery analysis is starting.';
  if (event.event_type === 'RECOVERY_ACTION') return 'Bounded recovery action activated.';
  if (event.event_type === 'BUYER_UPSELL_DECISION') return data.message || data.reason || 'Customer responded to the complementary offer.';
  return event.event_type.replaceAll('_', ' ').toLowerCase();
}
