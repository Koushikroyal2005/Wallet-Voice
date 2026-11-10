import { money,paymentStatus,remainingTime } from '../lib/formatting';

/** Presentation only. Opening a card always loads the authoritative Guardian review. */
export function ConversationPayments({items,onReview}:{items:any[];onReview:(id:string)=>void}) {
  return <div className="conversation-payments" aria-label="Payments in this conversation">{items.slice(0,8).map((item,index)=>{
    const id=item.payment_request_id||item.id;
    return <article className="conversation-payment" key={id||index}><div><strong>{item.merchant||item.kind||'Payment'}</strong><b>{typeof item.amount==='number' ? item.currency && item.currency!=='INR' ? `${(item.amount/100).toFixed(2)} ${item.currency}` : money(item.amount) : ''}</b></div><p>{paymentStatus(item.status||item.payment_status)}{item.expires_at||item.deadline ? ` · ${remainingTime(item.expires_at||item.deadline)}` : ''}</p>{item.verified===false && <small>Unrecognized recipient. Check independently before approval.</small>}{item.order_status && <p>{item.fulfilled_at ? 'Merchant reports fulfillment completed.' : 'Merchant fulfillment has not been confirmed.'}</p>}{item.receipt?.journal_id && <small>Journal receipt: {item.receipt.journal_id}</small>}{id && item.merchant && <button className="secondary" onClick={()=>onReview(id)}>Review {item.merchant}</button>}</article>;
  })}</div>;
}
