/** SERVER-SIDE ONLY. Do not bundle merchant credentials in browser code. */
export interface CheckoutRequest { order_reference: string; amount: number; currency: 'INR'; description: string; expires_at: string }
export interface MerchantOrder { payment_request_id: string; merchant_id: string; merchant_order_reference: string; merchant: string; amount: number; currency: 'INR'; payment_status: string; order_status: 'PENDING_PAYMENT' | 'PAYMENT_PROCESSING' | 'PAYMENT_CONFIRMED' | 'FULFILLED' | 'EXPIRED' | 'CANCELLED' | 'PAYMENT_FAILED' | 'REFUNDED'; fulfilled_at: string | null; expires_at: string; review_url: string; mode: 'SIMULATED' }
export class WalletVoiceMerchant {
  constructor(private baseUrl: string, private merchantId: string, private secret: string) {}
  private async request(path: string, method = 'GET', body?: CheckoutRequest, key?: string): Promise<MerchantOrder> {
    const response = await fetch(`${this.baseUrl}/api/merchant/v1${path}`, { method, signal: AbortSignal.timeout(10000), headers: { 'Content-Type': 'application/json', 'X-Merchant-Id': this.merchantId, 'X-Merchant-Key': this.secret, ...(key ? { 'Idempotency-Key': key } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}) });
    if (!response.ok) throw new Error(`Wallet-Voice merchant request failed (${response.status})`);
    return response.json();
  }
  createCheckout(request: CheckoutRequest, idempotencyKey: string) { return this.request('/checkout-requests', 'POST', request, idempotencyKey); }
  getOrder(reference: string) { return this.request(`/orders/${encodeURIComponent(reference)}`); }
  fulfill(reference: string) { return this.request(`/orders/${encodeURIComponent(reference)}/fulfillment`, 'POST'); }
  cancel(reference: string) { return this.request(`/orders/${encodeURIComponent(reference)}/cancel`, 'POST'); }
}
