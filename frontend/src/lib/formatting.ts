export const money = (paise = 0) => new Intl.NumberFormat('en-IN', {
  style: 'currency', currency: 'INR', maximumFractionDigits: 0,
}).format(paise / 100);

const labels: Record<string, string> = {
  PENDING: 'Pending', HELD: 'On hold', PROCESSING: 'Processing',
  SUCCEEDED: 'Paid', FAILED: 'Failed', EXPIRED: 'Expired',
  RESERVED: 'Reserved', ACTIVE: 'Active', CONSUMED: 'Consumed', RELEASED: 'Released',
};

export const paymentStatus = (status?: string) => labels[status || ''] || 'Needs review';
export const urgencyLabel = (urgency?: string) => ({ URGENT: 'Urgent', DUE_SOON: 'Due soon', FLEXIBLE: 'Flexible' }[urgency || ''] || 'Flexible');

export const remainingTime = (expiresAt?: string | null) => {
  if (!expiresAt) return 'No deadline';
  const seconds = Math.max(0, Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000));
  if (!seconds) return 'Expired';
  if (seconds < 3600) return `Due in ${Math.ceil(seconds / 60)} min`;
  if (seconds < 86400) return `Due in ${Math.ceil(seconds / 3600)} hr`;
  return `Due ${new Date(expiresAt).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}`;
};
