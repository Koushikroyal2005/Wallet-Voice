import { useEffect, useRef, useState } from 'react';
import { api, operationKey, post } from '../lib/api';
import { PayPalCheckoutPanel } from './PayPalCheckoutPanel';

const amount = (value: number, currency: string) => new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value / 100);
const reasons: Record<string, string> = {
  USER_HELD: 'You put this request on hold. Release it in Payments before paying.',
  EXPIRED: 'The payment deadline has passed.', ALREADY_PAID: 'This request has already been paid.',
  NOT_PAYABLE: 'This request cannot accept another payment in its current state.',
  PER_TRANSACTION_LIMIT: 'The amount exceeds your limit for one wallet payment.',
  DAILY_LIMIT: 'This payment would exceed your daily wallet spending limit.',
  MINIMUM_BALANCE: 'There is not enough available money to pay and keep your required minimum balance.',
  UNKNOWN_MERCHANT_CONFIRMATION_REQUIRED: 'You need to recognize this business before approving.',
};

export function PaymentGuardian({ paymentId, initialSource, onChanged, onCancel }: {
  paymentId: string; initialSource?: string; onChanged: () => void; onCancel: () => void;
}) {
  const [review, setReview] = useState<any>();
  const [source, setSource] = useState(initialSource || 'AI_WALLET');
  const [recognized, setRecognized] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const active = useRef(false);
  const load = async () => {
    const result = await api(`/api/payments/${paymentId}/review`);
    setReview(result); return result;
  };
  useEffect(() => {
    let disposed = false, running = false;
    const refresh = async () => {
      if (running) return;
      running = true;
      try { const result = await api(`/api/payments/${paymentId}/review`); if (!disposed) { setReview(result); setError(''); } }
      catch (e) { if (!disposed) setError((e as Error).message); }
      finally { running = false; }
    };
    void refresh();
    const timer = window.setInterval(refresh, 3000);
    return () => { disposed = true; window.clearInterval(timer); };
  }, [paymentId]);
  const act = async (hold = false) => {
    if (active.current) return;
    active.current = true; setBusy(true); setError('');
    try {
      await post(`/api/payments/${paymentId}/${hold ? 'hold' : 'pay'}`, hold ? undefined : {
        idempotency_key: operationKey(`guardian:wallet:${paymentId}`), confirm_unknown_merchant: recognized,
      });
      await load(); onChanged();
    } catch (e) { setError((e as Error).message); setUncertain(true); await load().catch(() => undefined); }
    finally { active.current = false; setBusy(false); }
  };
  if (!review?.payment) return <section className="payment-guardian" aria-label="Payment Guardian"><h3>Payment Guardian</h3><p role="status">{error || 'Checking payment details…'}</p><button className="secondary" onClick={onCancel}>Cancel review</button></section>;
  const p = review.payment;
  const locked = !!review.attempt && ['PROCESSING', 'SUCCEEDED'].includes(review.attempt.status) || !!review.paypal;
  const actualSource = locked ? review.paypal || review.receipt?.funding_source === 'PAYPAL_SANDBOX' ? 'PAYPAL_SANDBOX' : 'AI_WALLET' : source;
  const paypal = actualSource === 'PAYPAL_SANDBOX';
  const decision = recognized ? review.wallet_policy_after_merchant_confirmation : review.wallet_policy;
  const expired = p.status === 'EXPIRED' || !!p.expires_at && Date.parse(p.expires_at) <= Date.now();
  const status = review.paypal?.status || p.status;
  const done = paypal ? status === 'COMPLETED' && !!review.paypal?.capture_id : p.status === 'SUCCEEDED' && !!review.receipt?.journal_id;
  const processing = !done && (paypal ? review.paypal?.status === 'PENDING' || !review.paypal && p.status === 'PROCESSING' : p.status === 'PROCESSING');
  const approved = processing || done || paypal && review.paypal?.status === 'APPROVED';
  const held = p.explicit_hold;
  const failed = ['FAILED', 'DENIED', 'DECLINED', 'VOIDED', 'REFUNDED'].includes(status);
  const allowed = !expired && !held && !processing && !done && !locked && (!paypal ? decision.decision === 'ELIGIBLE' && p.currency === review.wallet_currency : p.status === 'PENDING' && (p.verified || recognized));
  const title = done ? 'Payment completed' : processing ? 'Waiting for confirmation' : held ? 'Payment on hold' : expired && !locked ? 'Payment expired' : failed ? 'Payment did not complete' : 'Review your payment';
  return <section className="payment-guardian" aria-label="Payment Guardian">
    <span className="eyebrow">PAYMENT GUARDIAN</span><h3 tabIndex={-1}>{title}</h3>
    <p role="status" aria-live="polite">{done ? paypal ? 'PayPal capture confirmed by the backend.' : 'Demo wallet payment recorded in the journal.' : processing ? 'The result is pending. Keep this request open; do not start another payment.' : 'Check the details. Your assistant has prepared this review for you.'}</p>
    <dl className="guardian-details">
      <div><dt>Merchant</dt><dd>{p.merchant}</dd></div><div><dt>Amount</dt><dd>{amount(p.amount, p.currency)} · {p.currency}</dd></div>
      <div><dt>Deadline</dt><dd>{p.expires_at ? new Date(p.expires_at).toLocaleString() : 'No deadline supplied'}</dd></div>
      <div><dt>Verification</dt><dd>{p.verified ? 'Marked verified in this app’s merchant record' : 'Unrecognized business — check independently'}{p.provider?.includes('DEMO') ? ' · Demo merchant' : ''}</dd></div>
    </dl>
    <label>Payment source<select aria-label="Payment source" value={actualSource} disabled={busy || locked || expired || held} onChange={e => { setSource(e.target.value); setRecognized(false); setError(''); }}><option value="AI_WALLET">Demo wallet</option>{p.category !== 'person_to_person' && <option value="PAYPAL_SANDBOX">PayPal Sandbox</option>}</select></label>
    <div className="guardian-rules"><strong>{paypal ? 'PayPal approval' : 'Why this wallet decision?'}</strong>
      {paypal ? <p>PayPal handles buyer approval and capture. Internal wallet limits do not govern these external funds. Your demo wallet is not debited or reserved.</p> : <>
        <p>{decision.decision === 'ELIGIBLE' ? 'The server allows this payment within your current balance and spending rules. Your approval is still required.' : (decision.reason_codes || []).map((r: string) => reasons[r] || r.replaceAll('_', ' ').toLowerCase()).join(' ')}</p>
        {typeof decision.available_balance === 'number' && <p>Available: {amount(decision.available_balance, review.wallet_currency)} · Minimum to keep: {amount(decision.settings.minimum_balance, review.wallet_currency)} · Daily limit: {amount(decision.settings.daily_limit, review.wallet_currency)} · Spent or reserved today: {amount(decision.daily_spend, review.wallet_currency)}</p>}
        {typeof review.wallet_per_transaction_limit === 'number' && <p>Limit per payment: {amount(review.wallet_per_transaction_limit, review.wallet_currency)}</p>}
        {p.currency !== review.wallet_currency && <p>Request and wallet currencies differ. This wallet cannot fund this request.</p>}
      </>}
      <p>{paypal ? 'Continue to PayPal and approve with your Sandbox buyer account.' : 'Confirm action approves this exact demo wallet payment. The server checks the rules again before reserving funds.'}</p>
    </div>
    <ol className="guardian-timeline" aria-label="Payment decision timeline">
      {['Request identified', 'Details checked', 'User approval required', 'Processing', paypal ? 'Provider-confirmed outcome' : 'Demo journal outcome'].map((step, i) => <li key={step} data-complete={i < 2 || i === 2 && approved || i > 2 && done}><span>{i + 1}</span>{step}{i === 3 && processing ? ' — pending' : ''}{i === 4 && failed ? ` — ${status}` : ''}</li>)}
    </ol>
    {!p.verified && !locked && !expired && !held && <label className="check-label"><input type="checkbox" checked={recognized} onChange={e => setRecognized(e.target.checked)}/> I recognize this business and have checked the amount.</label>}
    {review.attempt?.failure_reason && <p role="alert">{review.attempt.failure_reason}</p>}
    {error && <p role="alert">{error}</p>}
    {uncertain && <p>The last response was interrupted. Any wallet retry uses the same payment key.</p>}
    {paypal && (locked || !expired && !held && allowed) && <PayPalCheckoutPanel paymentId={paymentId} amount={p.amount} onComplete={() => { void load().catch(e => setError(e.message)); onChanged(); }}/>}
    <div className="preview-actions">
      {!paypal && !done && <button disabled={!allowed || busy} onClick={() => void act()}>{busy ? 'Processing…' : 'Confirm action'}</button>}
      {!locked && !expired && !held && !done && ['PENDING', 'HELD'].includes(p.status) && <button className="secondary" disabled={busy} onClick={() => void act(true)}>Hold payment</button>}
      {held && !expired && <button disabled={busy} onClick={async () => { if (active.current) return; active.current = true; setBusy(true); try { await post(`/api/payments/${paymentId}/release`); await load(); onChanged(); } catch (e) { setError((e as Error).message); } finally { active.current = false; setBusy(false); } }}>Release hold</button>}
      <button className="secondary" disabled={busy || processing} onClick={onCancel}>{locked || done || held ? 'Close review' : 'Cancel review'}</button>
    </div>
    {review.receipt && <div className="guardian-receipt"><h4>{done ? 'Payment receipt' : 'Payment record'}</h4><dl>{Object.entries({ 'Payment identifier': review.receipt.payment_id, Merchant: review.receipt.merchant, Amount: amount(review.receipt.amount, review.receipt.currency), 'Funding source': review.receipt.funding_source === 'PAYPAL_SANDBOX' ? 'PayPal Sandbox' : 'Simulated internal wallet', 'Actual transaction status': review.receipt.status, [review.receipt.timestamp_label]: new Date(review.receipt.timestamp).toLocaleString(), 'PayPal order': review.receipt.order_id, 'PayPal capture': review.receipt.capture_id, 'Journal reference': review.receipt.journal_id }).filter(([, value]) => value).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl></div>}
  </section>;
}
