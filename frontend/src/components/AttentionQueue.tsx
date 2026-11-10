import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, post } from '../lib/api';
import { money } from '../lib/formatting';

export function AttentionQueue({ onReview }: { onReview: (id: string) => void }) {
  const { data, refetch } = useQuery({ queryKey: ['attention'], queryFn: () => api('/api/notifications') });
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  async function attentionAction(id:string,action:'SNOOZE'|'DISMISS'|'RESTORE') {try{await post(`/api/notifications/attention/${id}`,{action,minutes:5});await refetch();setMessage(action==='SNOOZE'?'Reminder paused for up to five minutes. Payment deadline is unchanged.':action==='DISMISS'?'Hidden from attention. The request remains in Payments.':'Restored to attention.');}catch(e){setMessage((e as Error).message);}}
  async function enable() {
    setBusy(true);
    try {
      if (!isSecureContext || !('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) throw new Error('This browser cannot receive background reminders here. In-app attention remains available.');
      if (!data?.push_configured) throw new Error('Background reminders are not configured. Your requests remain saved in the inbox.');
      if (await Notification.requestPermission() !== 'granted') throw new Error('Notifications were not enabled. You can still review reminders in the app.');
      await navigator.serviceWorker.register('/sw.js');
      const registration = await navigator.serviceWorker.ready;
      const raw = atob(data.public_key.replace(/-/g, '+').replace(/_/g, '/'));
      const applicationServerKey = Uint8Array.from(raw, c => c.charCodeAt(0));
      const subscription = await registration.pushManager.getSubscription() || await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey });
      await post('/api/notifications/subscriptions', subscription.toJSON());
      await api('/api/notifications/preferences', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...data.preferences, push_enabled: true }) });
      await refetch(); setMessage('Background reminders enabled. Quiet hours still apply.');
    } catch (e) { setMessage((e as Error).message); }
    finally { setBusy(false); }
  }
  return <section className="attention-queue surface" aria-label="Payment reminders">
    <div><span className="eyebrow">NEEDS YOUR ATTENTION</span><h2>Remembered for you</h2></div>
    {!data?.preferences?.enabled && <p>Alerts are off. Your saved payments are still here.</p>}
    {data?.items?.length ? data.items.map((item: any) => <article key={item.id}><div><strong>{item.merchant}</strong><small>{item.stage === 'EXPIRED' ? 'Expired checkout' : item.stage === 'URGENT' ? 'Expiring soon' : item.stage === 'DUE_SOON' ? 'Due soon' : item.stage === 'SAVED_CHECKOUT' ? 'Saved merchant checkout · Simulated' : 'Saved payment'}</small><p>{money(item.amount)} · {item.deadline ? `Due ${new Date(item.deadline).toLocaleString()}` : 'Saved for review'}</p>{item.snoozed_until && <small>Reminder paused until {new Date(item.snoozed_until).toLocaleTimeString()}</small>}</div><div className="attention-actions"><button className="secondary" onClick={() => onReview(item.payment_id)}>{item.stage === 'EXPIRED' ? 'View details' : 'Review now'}</button>{item.stage!=='EXPIRED' && !item.explicit_hold && <button className="text-button" onClick={()=>void attentionAction(item.payment_id,'SNOOZE')}>Remind in 5 min</button>}<button className="text-button" onClick={()=>void attentionAction(item.payment_id,'DISMISS')}>Dismiss</button></div></article>) : <p>No saved payments need attention. Your payment history stays in Payments.</p>}
    {!!data?.dismissed_items?.length && <details><summary>Hidden from attention ({data.dismissed_items.length})</summary>{data.dismissed_items.map((item:any)=><p key={item.payment_id}>{item.merchant} <button className="text-button" onClick={()=>void attentionAction(item.payment_id,'RESTORE')}>Restore</button></p>)}</details>}
    <details><summary>Reminder preferences</summary>
      <label><input type="checkbox" checked={data?.preferences?.enabled ?? true} onChange={async e => {
        try { await api('/api/notifications/preferences', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...data.preferences, enabled: e.target.checked }) }); await refetch(); } catch (error) { setMessage((error as Error).message); }
      }}/> Deadline alerts (saved payments stay visible)</label>
      <p>Quiet hours: {data?.preferences?.quiet_start ?? 22}:00–{data?.preferences?.quiet_end ?? 8}:00, local wallet time.</p>
      {(['quiet_start','quiet_end'] as const).map(key => <label key={key}>{key === 'quiet_start' ? 'Quiet hours start' : 'Quiet hours end'}<select value={data?.preferences?.[key] ?? (key === 'quiet_start' ? 22 : 8)} onChange={async e => {
        try { await api('/api/notifications/preferences', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...data.preferences, [key]: Number(e.target.value) }) }); await refetch(); } catch (error) { setMessage((error as Error).message); }
      }}>{Array.from({length:24},(_,hour)=><option value={hour} key={hour}>{String(hour).padStart(2,'0')}:00</option>)}</select></label>)}
      <button className="secondary" disabled={busy} onClick={() => void enable()}>Enable background reminders</button>
      <button className="text-button" disabled={!data?.preferences?.push_enabled} onClick={async () => {
        try { await api('/api/notifications/preferences', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...data.preferences, push_enabled: false }) }); await refetch(); setMessage('Background reminders paused.'); } catch (e) { setMessage((e as Error).message); }
      }}>Pause background reminders</button>
    </details>
    {message && <p role="status">{message}</p>}
  </section>;
}
