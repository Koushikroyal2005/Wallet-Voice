import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { currencyMoney, paymentStatus } from '../lib/formatting';
import { Dialog } from './Dialog';
type Row = { id:string; kind:string; title:string; search_text:string; status:string; created_at:string; totals:Record<string,number>; source:string; reference:string; batch_id?:string; payment_id?:string; attempt_id?:string; download_url?:string };
type Attempt = {attempt_id:string;payment_id:string;merchant:string;amount:number;currency:string;status:string;funding_source:string;created_at:string;journal_id?:string;provider_reference?:string;order_id?:string;capture_id?:string;provider_status?:string};
export function ActivityTimeline({onBatch,onPayment}:{onBatch:(id:string)=>void;onPayment:(id:string)=>void}) {
  const [filter,setFilter]=useState('All'), [search,setSearch]=useState(''), [selected,setSelected]=useState<Row>();
  const q=useQuery({queryKey:['activity-timeline'],queryFn:()=>api<Row[]>('/api/product/activity')});
  const detail=useQuery({queryKey:['attempt-record',selected?.attempt_id],enabled:!!selected?.attempt_id,queryFn:()=>api<Attempt>(`/api/product/documents/attempts/${selected!.attempt_id}`)});
  const kinds:Record<string,string>={Sent:'SENT',Received:'RECEIVED',Bills:'BILL','Batch payments':'BATCH'};
  const rows=(Array.isArray(q.data)?q.data:[]).filter(r=> {
    const matches=filter==='All'||(filter==='Pending'?['PROCESSING','PENDING','REVIEW','AWAITING_APPROVAL'].includes(r.status):filter==='Failed'?['FAILED','PARTIAL'].includes(r.status):r.kind===kinds[filter]);
    return matches&&`${r.title} ${r.search_text} ${r.reference} ${r.created_at}`.toLowerCase().includes(search.toLowerCase());
  });
  const source=(s:string)=>s==='PAYPAL_SANDBOX'?'PayPal Sandbox':s==='UNRESOLVED'?'Funding evidence unavailable':'Simulated wallet';
  return <section className="surface consumer-card"><h2>Your Activity</h2><p>Every recorded payment, in one place.</p><div className="toolbar"><input aria-label="Search recorded activity" placeholder="Merchant, recipient, reference or date" value={search} onChange={e=>setSearch(e.target.value)}/><select aria-label="Recorded activity filter" value={filter} onChange={e=>setFilter(e.target.value)}>{['All','Sent','Received','Bills','Batch payments','Pending','Failed'].map(f=><option key={f}>{f}</option>)}</select></div>
    {q.isPending&&<p role="status">Loading recorded activity…</p>}{q.isError&&<p role="alert">Activity unavailable. <button onClick={()=>void q.refetch()}>Retry</button></p>}
    {rows.map(r=><article className="record-row" key={`${r.kind}:${r.id}`}><div><strong>{r.title}</strong><p>{Object.entries(r.totals).map(([c,v])=>currencyMoney(v,c)).join(' · ')} · {paymentStatus(r.status)}</p><small>{new Date(r.created_at).toLocaleString()} · {source(r.source)}</small></div>{r.batch_id?<button className="secondary" onClick={()=>onBatch(r.batch_id!)}>View batch</button>:<button className="secondary" onClick={()=>setSelected(r)}>View payment record</button>}</article>)}
    {!q.isPending&&!q.isError&&!rows.length&&<p>No matching recorded activity. Tracked bills and requested money are not completed transactions.</p>}
    {selected&&<Dialog title="Transaction record" onClose={()=>setSelected(undefined)}><div className="document-preview"><h3>{selected.title}</h3>{selected.attempt_id&&detail.isPending&&<p role="status">Loading exact attempt…</p>}{detail.isError&&<p role="alert">Could not load this attempt. <button onClick={()=>void detail.refetch()}>Retry</button></p>}
      {(!selected.attempt_id||detail.data)&&<><p>{detail.data?currencyMoney(detail.data.amount,detail.data.currency):Object.entries(selected.totals).map(([c,v])=>currencyMoney(v,c)).join(' · ')}</p><p>{paymentStatus(detail.data?.status??selected.status)} · {source(detail.data?.funding_source??selected.source)}</p><p>{new Date(selected.created_at).toLocaleString()}</p><details><summary>Transaction references</summary><dl>{Object.entries({'Attempt':detail.data?.attempt_id,'Journal':detail.data?.journal_id,'Provider reference':detail.data?.provider_reference,'PayPal order':detail.data?.order_id,'PayPal capture':detail.data?.capture_id,'Current provider state':detail.data?.provider_status,'Reference':selected.reference}).filter(([,v])=>v).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl></details>{selected.download_url&&<a className="document-link" href={selected.download_url}>Download this attempt record</a>}{selected.payment_id&&<button className="secondary" onClick={()=>{onPayment(selected.payment_id!);setSelected(undefined);}}>Review current request</button>}<p>Pending or failed records are not proof of payment. Simulated wallet records are not bank transfers.</p></>}
    </div></Dialog>}
  </section>;
}
