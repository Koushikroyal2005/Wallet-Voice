import { useState } from "react";
import { money } from "../lib/formatting";
import { operationKey, post } from "../lib/api";
import { WalletPinDialog } from "./WalletPinDialog";

export function RecipientTransferCard({
  draft,
  onRecorded,
  onCancel,
}: {
  draft: {
    intent_id?: string;
    amount?: number;
    recipient_name?: string;
    recipient_handle?: string;
    version?: number;
    source?: string;
  };
  onRecorded: (paymentId: string) => void;
  onCancel: () => void;
}) {
  const [pin, setPin] = useState(false);
  return (
    <section aria-label="Recipient transfer review">
      <span className="eyebrow">SIMULATED WALLET TRANSFER</span>
      <h3>Send {money(draft.amount)}</h3>
      <dl className="guardian-details">
        <div>
          <dt>Recipient</dt>
          <dd>{draft.recipient_name}</dd>
        </div>
        <div>
          <dt>Destination</dt>
          <dd>{draft.recipient_handle}</dd>
        </div>
        <div>
          <dt>From</dt>
          <dd>Simulated wallet</dd>
        </div>
      </dl>
      <p>
        Check the saved details. Your wallet PIN approves only this transfer.
      </p>
      <div className="preview-actions">
        <button onClick={() => setPin(true)}>Review transfer</button>
        <button className="secondary" onClick={onCancel}>
          Keep as draft
        </button>
      </div>
      {pin && (
        <WalletPinDialog
          action="P2P"
          amount={draft.amount || 0}
          resourceId={draft.intent_id}
          details={{ version: draft.version, source: draft.source }}
          summary={[
            { label: "Recipient", value: draft.recipient_name || "" },
            { label: "Destination", value: draft.recipient_handle || "" },
            { label: "From", value: "Simulated wallet" },
          ]}
          title="Review your transfer"
          onClose={() => setPin(false)}
          onApproved={async (token) => {
            const result = await post(
              `/api/payment-intents/${draft.intent_id}/execute`,
              {
                approval_token: token,
                idempotency_key: operationKey(`draft:${draft.intent_id}`),
              },
            );
            setPin(false);
            if (result.intent?.payment_request_id)
              onRecorded(result.intent.payment_request_id);
          }}
        />
      )}
    </section>
  );
}
