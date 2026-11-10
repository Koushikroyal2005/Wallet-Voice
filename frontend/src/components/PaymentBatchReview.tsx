import { useEffect, useRef, useState } from 'react';
import { api, post } from '../lib/api';
import { money } from '../lib/formatting';

export function PaymentBatchReview({ batchId, onChanged, onCancel }: { batchId: string; onChanged: () => void; onCancel: () => void }) {
  const [batch, setBatch] = useState<any>();
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const token = useRef<string>();
  const inFlight = useRef(false);
  useEffect(() => {
    let disposed = false;
    const load = async () => { try { const data = await api(`/api/payment-batches/${batchId}`); if (!disposed) setBatch(data); } catch (e) { if (!disposed) setError((e as Error).message); } };
    void load(); const timer = window.setInterval(load, 3000);
    return () => { disposed = true; window.clearInterval(timer); };
  }, [batchId]);
  async function confirm() {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError('');
    try {
      if (!token.current) {
        const approval = await post(`/api/payment-batches/${batchId}/authorize`, { pin });
        token.current = approval.approval_token; setPin('');
      }
      setBatch(await post(`/api/payment-batches/${batchId}/confirm`, { approval_token: token.current })); onChanged();
    } catch (e) { setError((e as Error).message); }
    finally { inFlight.current = false; setBusy(false); }
  }
  return <section className="batch-review" aria-label="Exact payment review">
    <span className="eyebrow">EXACT WALLET REVIEW · SIMULATED FUNDS</span>
    <h3>{batch?.status === 'SUCCEEDED' ? 'All selected payments completed' : batch?.status === 'PARTIAL' ? 'Some payments need attention' : batch?.status === 'PROCESSING' ? 'Payments processing' : batch?.status === 'FAILED' ? 'Payments failed' : batch?.status === 'EXPIRED' ? 'Review expired' : 'Your selected payments'}</h3>
    {!batch && <p role="status">Loading the exact server review…</p>}
    {batch && <>
      <ul className="batch-items">{batch.items.map((item: any) => <li key={item.id}>
        <div><strong>{item.merchant}</strong><b>{money(item.amount)}</b></div>
        <p>{item.deadline ? `Due ${new Date(item.deadline).toLocaleString()}` : 'No deadline'} · {item.currency}</p>
        <small>{item.verified ? 'Marked verified in this app' : 'Unrecognized business — check independently'}</small>
        <p role="status">{item.attempt_id ? item.status : item.blocked ? `Blocked: ${item.reason_codes.map((s: string) => s.replaceAll('_', ' ').toLowerCase()).join(', ')}` : 'Ready for your approval'}</p>
        {item.failure_reason && <p>{item.failure_reason}</p>}
        {item.receipt && <details><summary>Payment receipt</summary><dl><dt>Payment</dt><dd>{item.id}</dd><dt>Status</dt><dd>{item.receipt.status}</dd><dt>Journal reference</dt><dd>{item.receipt.journal_id}</dd><dt>Recorded</dt><dd>{new Date(item.receipt.timestamp).toLocaleString()}</dd><dt>Source</dt><dd>Simulated wallet</dd></dl></details>}
      </li>)}</ul>
      <dl className="batch-totals"><div><dt>Total</dt><dd>{money(batch.total)}</dd></div><div><dt>Available now</dt><dd>{money(batch.available_balance)}</dd></div>{batch.status === 'REVIEW' && <div><dt>After these payments</dt><dd>{money(batch.remaining_after_payment)}</dd></div>}</dl>
      {batch.funding_shortfall > 0 && batch.status === 'REVIEW' && <p>Shortfall: {money(batch.funding_shortfall)}. Add simulated money from Wallet, then prepare a fresh review. Funding requires your PIN.</p>}
      {batch.status === 'REVIEW' && <form onSubmit={e => { e.preventDefault(); void confirm(); }}>
        <p>One PIN approves only these exact requests and amounts. Changes require a new review.</p>
        <label htmlFor={`batch-pin-${batchId}`}>Six-digit wallet PIN</label>
        <input id={`batch-pin-${batchId}`} type="password" inputMode="numeric" autoComplete="off" maxLength={6} value={pin} disabled={busy || !!token.current} onChange={e => setPin(e.target.value.replace(/\D/g, ''))}/>
        <button disabled={busy || !batch.can_authorize || (!token.current && pin.length !== 6)}>{busy ? 'Processing…' : token.current ? 'Retry approved payments' : 'Approve exact payments'}</button>
      </form>}
      {batch.status === 'PROCESSING' && <p role="status">Waiting for recorded outcomes. Do not start another payment. This review refreshes automatically.</p>}
    </>}
    {error && <p role="alert" className="error-banner">{error}</p>}
    <button className="secondary" disabled={busy} onClick={async () => {
      try { if (batch?.status === 'REVIEW') await post(`/api/payment-batches/${batchId}/cancel`); onCancel(); }
      catch (e) { setError((e as Error).message); }
    }}>{batch?.status === 'REVIEW' ? 'Cancel review' : 'Close review'}</button>
  </section>;
}
