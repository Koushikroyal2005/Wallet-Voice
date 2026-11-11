/** Read-only server contracts. These types do not implement financial policy. */
export type BatchItem = {
  id:string;merchant:string;amount:number;currency:string;status:string;deadline?:string|null;
  verified:boolean;provider?:string;merchant_id?:string;current_identity?:string;
  acknowledged:boolean;blocked:boolean;reason_codes:string[];attempt_id?:string|null;failure_reason?:string|null;
  receipt?:{journal_id:string;operation_id:string;timestamp:string;status:string;provider_reference?:string|null}|null;
};
export type BatchReview = {
  id:string;status:string;items:BatchItem[];currency:string;source:string;total:number;snapshot_hash:string;
  available_balance:number;remaining_after_payment:number;funding_shortfall:number;can_authorize:boolean;expires_at:string;
};
type Policy={decision:string;reason_codes:string[];available_balance?:number;daily_spend:number;settings:{minimum_balance:number;daily_limit:number}};
export type PaymentReview = {
  payment:{id:string;merchant:string;amount:number;currency:string;category:string;status:string;provider?:string;verified:boolean;explicit_hold:boolean;expires_at?:string|null};
  wallet_policy:Policy;wallet_policy_after_merchant_confirmation:Policy;wallet_currency:string;wallet_per_transaction_limit:number;
  merchant_identity?:{payable:boolean}|null;
  attempt?:{id:string;status:string;failure_reason?:string|null}|null;
  paypal?:{status:string;capture_id?:string|null}|null;
  merchant_order?:{merchant_order_reference:string;payment_status:string;fulfilled_at?:string|null}|null;
  receipt?:{payment_id:string;attempt_id:string;merchant:string;amount:number;currency:string;funding_source:string;status:string;timestamp_label:string;timestamp:string;order_id?:string|null;capture_id?:string|null;journal_id?:string|null}|null;
};
