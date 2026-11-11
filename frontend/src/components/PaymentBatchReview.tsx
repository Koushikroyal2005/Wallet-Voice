import { useEffect, useRef, useState } from "react";
import { api, post } from "../lib/api";
import { money, currencyMoney, paymentStatus } from "../lib/formatting";

export function PaymentBatchReview({
  batchId,
  onChanged,
  onCancel,
}: {
  batchId: string;
  onChanged: () => void;
  onCancel: () => void;
}) {
  const [reviewId, setReviewId] = useState(batchId);
  const [batch, setBatch] = useState<any>();
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const token = useRef<string>();
  const inFlight = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (batch?.status && batch.status !== "REVIEW") {
      heading.current?.focus({ preventScroll: true });
      heading.current?.closest("dialog")?.scrollTo({ top: 0 });
    }
  }, [batch?.status]);
  const currencyTotals: Record<string, number> = {};
  for (const item of batch?.items || [])
    currencyTotals[item.currency] =
      (currencyTotals[item.currency] || 0) + item.amount;
  const walletCurrencyOnly =
    Object.keys(currencyTotals).length === 1 &&
    Object.keys(currencyTotals)[0] === batch?.currency;
  useEffect(() => {
    let disposed = false;
    const load = async () => {
      try {
        const data = await api(`/api/payment-batches/${reviewId}`);
        if (!disposed) setBatch(data);
      } catch (e) {
        if (!disposed) setError((e as Error).message);
      }
    };
    void load();
    const timer = window.setInterval(load, 3000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [reviewId]);
  async function confirm() {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      if (!token.current) {
        const approval = await post(
          `/api/payment-batches/${reviewId}/authorize`,
          { pin },
        );
        token.current = approval.approval_token;
        setPin("");
      }
      setBatch(
        await post(`/api/payment-batches/${reviewId}/confirm`, {
          approval_token: token.current,
        }),
      );
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  return (
    <section className="batch-review" aria-label="Exact payment review">
      <span className="eyebrow">EXACT WALLET REVIEW · SIMULATED FUNDS</span>
      <h3 ref={heading} tabIndex={-1}>
        {batch?.status === "SUCCEEDED"
          ? "All selected payments completed"
          : batch?.status === "PARTIAL"
            ? "Some payments need attention"
            : batch?.status === "PROCESSING"
              ? "Payments processing"
              : batch?.status === "FAILED"
                ? "Payments failed"
                : batch?.status === "EXPIRED"
                  ? "Review expired"
                  : batch?.status === "CANCELLED"
                    ? "Review cancelled"
                    : "Ready for review"}
      </h3>
      {!batch && <p role="status">Loading the exact server review…</p>}
      {batch && (
        <>
          <ol className="batch-progress" aria-label="Batch decision timeline">
            <li>Exact requests selected</li>
            <li>
              {batch.status === "REVIEW"
                ? "Your PIN approval required"
                : "Review recorded"}
            </li>
            <li>
              {batch.status === "PROCESSING"
                ? "Processing — outcome pending"
                : ["SUCCEEDED", "PARTIAL", "FAILED"].includes(batch.status)
                  ? `Recorded outcome: ${batch.status.toLowerCase()}`
                  : "Not submitted"}
            </li>
          </ol>
          {["SUCCEEDED", "PARTIAL", "FAILED", "PROCESSING"].includes(
            batch.status,
          ) && (
            <div
              className={`batch-outcome outcome-${batch.status.toLowerCase()}`}
              role="status"
            >
              <strong>
                {
                  batch.items.filter((i: any) => i.status === "SUCCEEDED")
                    .length
                }{" "}
                of {batch.items.length} payments completed
              </strong>
              <p>
                {
                  batch.items.filter((i: any) => i.status === "PROCESSING")
                    .length
                }{" "}
                processing ·{" "}
                {batch.items.filter((i: any) => i.status === "FAILED").length}{" "}
                failed
              </p>
              <small>
                Only recorded journal results count as completed. Pending items
                are not settled.
              </small>
            </div>
          )}
          <ul className="batch-items">
            {batch.items.map((item: any) => (
              <li key={item.id}>
                <div>
                  <strong>{item.merchant}</strong>
                  <b>{currencyMoney(item.amount, item.currency)}</b>
                </div>
                <p>
                  {item.deadline
                    ? `Due ${new Date(item.deadline).toLocaleString()}`
                    : "No deadline"}{" "}
                  · {item.currency}
                </p>
                <small>
                  {item.current_identity &&
                  !["ACTIVE", "LEGACY"].includes(item.current_identity)
                    ? item.receipt
                      ? "Merchant identity changed after review. This receipt records the prior settlement."
                      : "Merchant identity is no longer valid. Payment is blocked."
                    : item.verified
                      ? item.provider?.startsWith("MERCHANT:")
                        ? "Authenticated local demo merchant · Simulated checkout"
                        : "Marked verified in this app"
                      : "Unrecognized business — check independently"}
                </small>
                {item.merchant_id && (
                  <details>
                    <summary>Merchant identity</summary>
                    <small>{item.merchant_id}</small>
                  </details>
                )}
                {!item.verified && batch.status === "REVIEW" && (
                  <button
                    className="secondary"
                    disabled={busy || item.acknowledged}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        const next = await post(
                          `/api/payment-batches/${reviewId}/acknowledge`,
                          { payment_id: item.id },
                        );
                        token.current = undefined;
                        setPin("");
                        setBatch(next);
                        setReviewId(next.id);
                      } catch (e) {
                        setError((e as Error).message);
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    {item.acknowledged
                      ? "Acknowledged for this review"
                      : "I checked this recipient independently"}
                  </button>
                )}
                <p role="status">
                  {item.attempt_id
                    ? paymentStatus(item.status)
                    : item.blocked
                      ? `Blocked: ${item.reason_codes.map((s: string) => s.replaceAll("_", " ").toLowerCase()).join(", ")}`
                      : "Ready for your approval"}
                </p>
                {item.failure_reason && <p>{item.failure_reason}</p>}
                {item.receipt && (
                  <details>
                    <summary>Payment receipt</summary>
                    <dl>
                      <dt>Payment</dt>
                      <dd>{item.id}</dd>
                      <dt>Status</dt>
                      <dd>{item.receipt.status}</dd>
                      <dt>Journal reference</dt>
                      <dd>{item.receipt.journal_id}</dd>
                      <dt>Recorded</dt>
                      <dd>
                        {new Date(item.receipt.timestamp).toLocaleString()}
                      </dd>
                      <dt>Source</dt>
                      <dd>Simulated wallet</dd>
                    </dl>
                    <a
                      className="document-link"
                      href={`/api/product/documents/payments/${item.id}.pdf`}
                    >
                      Download payment PDF
                    </a>
                  </details>
                )}
              </li>
            ))}
          </ul>
          <dl className="batch-totals">
            <div>
              <dt>Batch reference</dt>
              <dd className="safe-url">{batch.id}</dd>
            </div>
            {Object.keys(currencyTotals).map((currency) => (
              <div key={`recorded-${currency}`}>
                <dt>Successfully recorded · {currency}</dt>
                <dd>
                  {currencyMoney(
                    batch.items
                      .filter(
                        (i: {
                          currency: string;
                          status: string;
                          receipt?: { journal_id?: string };
                          amount: number;
                        }) =>
                          i.currency === currency &&
                          i.status === "SUCCEEDED" &&
                          i.receipt?.journal_id,
                      )
                      .reduce(
                        (sum: number, i: { amount: number }) => sum + i.amount,
                        0,
                      ),
                    currency,
                  )}
                </dd>
              </div>
            ))}
            {Object.entries(currencyTotals).map(([currency, total]) => (
              <div key={currency}>
                <dt>Total · {currency}</dt>
                <dd>{currencyMoney(total, currency)}</dd>
              </div>
            ))}
            <div>
              <dt>Available now · {batch.currency}</dt>
              <dd>{currencyMoney(batch.available_balance, batch.currency)}</dd>
            </div>
            {batch.status === "REVIEW" && walletCurrencyOnly && (
              <div>
                <dt>After these payments</dt>
                <dd>
                  {currencyMoney(batch.remaining_after_payment, batch.currency)}
                </dd>
              </div>
            )}
          </dl>
          {!walletCurrencyOnly && (
            <p>
              These currencies cannot be combined into one wallet total. Follow
              the backend eligibility checks; no conversion is assumed.
            </p>
          )}
          {batch.funding_shortfall > 0 && batch.status === "REVIEW" && (
            <p>
              Shortfall: {money(batch.funding_shortfall)}. Add simulated money
              from Wallet, then prepare a fresh review. Funding requires your
              PIN.
            </p>
          )}
          {batch.status === "REVIEW" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void confirm();
              }}
            >
              <p>
                One PIN approves only these exact requests and amounts. Changes
                require a new review.
              </p>
              <label htmlFor={`batch-pin-${batchId}`}>
                Six-digit wallet PIN
              </label>
              <input
                id={`batch-pin-${batchId}`}
                type="password"
                inputMode="numeric"
                autoComplete="off"
                maxLength={6}
                value={pin}
                disabled={busy || !!token.current}
                onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
              />
              <button
                disabled={
                  busy ||
                  !batch.can_authorize ||
                  (!token.current && pin.length !== 6)
                }
              >
                {busy
                  ? "Processing…"
                  : token.current
                    ? "Retry approved payments"
                    : "Approve exact payments"}
              </button>
            </form>
          )}
          {batch.status === "PROCESSING" && (
            <p role="status">
              Waiting for recorded outcomes. Do not start another payment. This
              review refreshes automatically.
            </p>
          )}
          <a
            className="document-link"
            href={`/api/product/documents/batches/${reviewId}.pdf`}
          >
            Download batch statement PDF
          </a>
        </>
      )}
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
      <button
        className="secondary"
        disabled={busy}
        onClick={async () => {
          try {
            if (batch?.status === "REVIEW")
              await post(`/api/payment-batches/${reviewId}/cancel`);
            onCancel();
          } catch (e) {
            setError((e as Error).message);
          }
        }}
      >
        {batch?.status === "REVIEW" ? "Cancel review" : "Close review"}
      </button>
    </section>
  );
}
