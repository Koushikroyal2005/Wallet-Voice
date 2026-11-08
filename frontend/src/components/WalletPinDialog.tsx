import { useRef, useState } from "react";
import { LoaderCircle } from "lucide-react";
import { money } from "../lib/formatting";
import { post } from "../lib/api";
import { Dialog } from "./Dialog";

type Props = {
  action: "TOPUP" | "WITHDRAWAL" | "P2P" | "MANDATE";
  amount: number;
  resourceId?: string;
  details?: Record<string, unknown>;
  summary?: { label: string; value: string }[];
  title: string;
  onClose: () => void;
  onApproved: (token: string) => Promise<void>;
};
export function WalletPinDialog({
  action,
  amount,
  resourceId,
  details,
  summary,
  title,
  onClose,
  onApproved,
}: Props) {
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const approved = useRef<string>();
  const locked = useRef(false);
  async function approve() {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError("");
    try {
      if (!approved.current) {
        const challenge = await post("/api/security/challenges", {
          action,
          amount,
          resource_id: resourceId,
          details: details || {},
        });
        const approval = await post(
          `/api/security/challenges/${challenge.id}/verify`,
          { pin },
        );
        approved.current = approval.approval_token;
        setPin("");
      }
      await onApproved(approved.current!);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  return (
    <Dialog title={title} busy={busy} onClose={onClose}>
      <div className="review-amount">{money(amount)}</div>
      <dl className="review-details">
        {(
          summary || [
            {
              label: "From",
              value: action === "TOPUP" ? "Demo National Bank" : "Your wallet",
            },
            {
              label: "To",
              value:
                action === "TOPUP"
                  ? "Your wallet"
                  : action === "WITHDRAWAL"
                    ? "Demo National Bank"
                    : resourceId || "Selected recipient",
            },
          ]
        ).map((item) => (
          <div key={item.label}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
      {action === "MANDATE" && (
        <p>
          This is the maximum per payment. Future eligible payments can use this
          permission until it expires or you revoke it.
        </p>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void approve();
        }}
      >
        <label className="pin-label" htmlFor="wallet-pin">
          Your six-digit wallet PIN
        </label>
        <input
          id="wallet-pin"
          className="pin-input"
          type="password"
          inputMode="numeric"
          autoComplete="current-password"
          maxLength={6}
          value={pin}
          disabled={!!approved.current}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
          autoFocus
        />
        <small className="pin-safety">
          Use your AI Wallet PIN. Your bank or PayPal password is never needed
          here.
        </small>
        {error && (
          <p className="error-banner" role="alert">
            {error}
          </p>
        )}
        <div className="dialog-actions">
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={onClose}
          >
            Cancel
          </button>
          <button disabled={busy || (!approved.current && pin.length !== 6)}>
            {busy && <LoaderCircle size={16} className="spin" />}
            {busy
              ? "Processing…"
              : approved.current
                ? "Retry this operation"
                : "Approve"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
