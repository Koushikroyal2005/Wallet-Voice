import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api,post} from '../lib/api';
import {currencyMoney} from '../lib/formatting';
import {FormError} from './FormControls';
type RequestRecord={id:string;payer:string;amount:number;currency:string;status:string;note:string;share_text:string};
export function MoneyRequests({onChanged}:{onChanged:()=>void}) {
  const q=useQuery({queryKey:['money-requests'],queryFn:()=>api<RequestRecord[]>('/api/product/money-requests')});
  const [error,setError]=useState(''),[busy,setBusy]=useState<string>(),[copied,setCopied]=useState<string>();
  return <section className="surface consumer-card"><h2>Money you've requested</h2><p>Requests are not received payments.</p><FormError message={error}/>
    {q.isPending&&<p role="status">Loading requests…</p>}{q.isError&&<p role="alert">Requests unavailable. <button onClick={()=>void q.refetch()}>Retry</button></p>}
    {(q.data||[]).map(r=><article className="record-row" key={r.id}><div><strong>{r.payer} · {currencyMoney(r.amount,r.currency)}</strong><p>{r.note}</p><small>{r.status==='CANCELLED'?'Cancelled request':'Awaiting payment'} · Simulated request, not proof of receipt</small></div><div className="button-row"><button className="secondary" onClick={async()=>{try{await navigator.clipboard.writeText(r.share_text);setCopied(r.id);}catch{setError('Could not copy. Please use your browser sharing controls.');}}}>{copied===r.id?'Copied':'Copy request'}</button>{r.status==='REQUESTED'&&<button className="text-button" disabled={!!busy} onClick={async()=>{setBusy(r.id);setError('');try{await post(`/api/product/money-requests/${r.id}/cancel`);await q.refetch();onChanged();}catch(cause){setError((cause as Error).message);}finally{setBusy(undefined);}}}>Cancel request</button>}</div></article>)}
    {!q.isPending&&!q.isError&&!q.data?.length&&<p>No money requests saved.</p>}
  </section>;
}
