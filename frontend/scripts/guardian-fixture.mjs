// Shared browser-only fixtures. These do not demonstrate provider verification.
export function guardianFixture(payment, overrides = {}) {
  const policy = { decision: payment.verified ? 'ELIGIBLE' : 'MANUAL_CONFIRMATION_REQUIRED', reason_codes: payment.verified ? [] : ['UNKNOWN_MERCHANT_CONFIRMATION_REQUIRED'], available_balance: 1000000, daily_spend: 0, settings: { minimum_balance: 10000, daily_limit: 1000000 } };
  return { payment: { currency: 'INR', ...payment }, wallet_currency: 'INR', wallet_policy: policy, wallet_policy_after_merchant_confirmation: { ...policy, decision: 'ELIGIBLE', reason_codes: [] }, receipt: null, paypal: null, attempt: null, ...overrides };
}
