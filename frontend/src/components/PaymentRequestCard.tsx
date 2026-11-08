import { useState } from "react";
import {
  CheckCircle2,
  Clock3,
  Pause,
  ShieldCheck,
  TriangleAlert,
  WalletCards,
} from "lucide-react";
import { PayPalCheckoutPanel } from "./PayPalCheckoutPanel";
import {
  money,
  paymentStatus,
  remainingTime,
  urgencyLabel,
} from "../lib/formatting";

export type Payment = {
  id: string;
  merchant: string;
  description: string;
  amount: number;
  verified: boolean;
  status: string;
  explicit_hold: boolean;
  expires_at: string | null;
  trace: any;
};

type Props = {
  payment: Payment;
  onPay: (payment: Payment) => void | Promise<void>;
  onHold: (payment: Payment) => void | Promise<void>;
  onComplete: () => void;
};

export function PaymentRequestCard({
  payment,
  onPay,
  onHold,
  onComplete,
}: Props) {
  const [showPayPal, setShowPayPal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const urgency = payment.trace?.urgency || "FLEXIBLE";
  const expired =
    payment.status === "EXPIRED" || payment.trace?.decision === "EXPIRED";
  const completed = payment.status === "SUCCEEDED";
  const payable = !expired && !completed && payment.status !== "FAILED";
  const submitWallet = async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      await onPay(payment);
    } finally {
      setSubmitting(false);
    }
  };
  return (
    <article className={`payment-card ${expired ? "is-expired" : ""}`}>
      <div className="merchant-identity payment-cell">
        <span className="merchant-avatar" aria-hidden="true">
          {payment.merchant.slice(0, 1)}
        </span>
        <div>
          <h3>{payment.merchant}</h3>
          <p>{payment.description || "Payment request"}</p>
          <span
            className={`verification ${payment.verified ? "verified" : "unverified"}`}
          >
            {payment.verified ? (
              <ShieldCheck size={13} />
            ) : (
              <TriangleAlert size={13} />
            )}{" "}
            {payment.verified ? "Verified" : "Verify merchant"}
          </span>
        </div>
      </div>
      <div className="payment-cell amount-cell">
        <span>Amount</span>
        <strong className="amount">{money(payment.amount)}</strong>
      </div>
      <div className="payment-cell due-cell">
        <span>Deadline</span>
        <b>
          <Clock3 size={14} />
          {remainingTime(payment.expires_at)}
        </b>
      </div>
      <div className="payment-cell state-cell">
        <span>State</span>
        <div
          className="badges"
          aria-label={`Urgency ${urgencyLabel(urgency)}. Status ${paymentStatus(payment.status)}`}
        >
          <span className={`badge urgency-${urgency.toLowerCase()}`}>
            {urgencyLabel(urgency)}
          </span>
          <span className={`badge status-${payment.status.toLowerCase()}`}>
            {paymentStatus(payment.status)}
          </span>
        </div>
      </div>
      <div className="payment-cell action-cell">
        {expired ? (
          <p className="payment-note">
            <TriangleAlert size={15} /> Expired
          </p>
        ) : completed ? (
          <p className="payment-note success">
            <CheckCircle2 size={15} /> Confirmed
          </p>
        ) : (
          <>
            <button disabled={submitting} onClick={submitWallet}>
              <WalletCards size={15} />
              {submitting ? "Submitting..." : "Pay from wallet"}
            </button>
            <div className="secondary-actions">
              <button
                className="text-button"
                onClick={() => setShowPayPal((value) => !value)}
              >
                PayPal Sandbox
              </button>
              <button
                className="icon-button"
                aria-label={`${payment.explicit_hold ? "Release" : "Hold"} ${payment.merchant} payment`}
                onClick={() => onHold(payment)}
              >
                <Pause size={15} /> {payment.explicit_hold ? "Release" : "Hold"}
              </button>
            </div>
          </>
        )}
      </div>
      {payable && showPayPal && (
        <div className="paypal-drawer">
          <div>
            <b>External Sandbox checkout</b>
            <span>
              Buyer approval is separate and your AI Wallet balance is not
              debited.
            </span>
          </div>
          <PayPalCheckoutPanel
            paymentId={payment.id}
            amount={payment.amount}
            onComplete={onComplete}
          />
        </div>
      )}
    </article>
  );
}
