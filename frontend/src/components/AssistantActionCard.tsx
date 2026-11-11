import type { WalletAssistant } from "../hooks/useWalletAssistant";
import { PaymentGuardian } from "./PaymentGuardian";
import { PaymentBatchReview } from "./PaymentBatchReview";
import { WalletPinDialog } from "./WalletPinDialog";
import { RecipientTransferCard } from "./RecipientTransferCard";
import { post, operationKey, finishOperation } from "../lib/api";
import { SplitMoney } from "./SplitMoney";
import { BillReminderCard } from "./PlanningControls";
import {RequestMoney} from './ConsumerScreens';

export function AssistantActionCard({
  assistant: a,
  onChanged,
}: {
  assistant: WalletAssistant;
  onChanged: () => void;
}) {
  const p = a.preview;
  const cancel = () => {
    a.setPreview(undefined);
    a.stopVoice();
    void a.ask("cancel");
  };
  if (!p) return null;
  return (
    <div className="assistant-action-card">
      {p.kind==='money_request'?<RequestMoney initial={{payer:p.recipient_name||'',amount:String((p.amount||0)/100),note:typeof p.changes?.note==='string'?p.changes.note:''}} onClose={cancel} onChanged={onChanged}/>:p.kind === "split_requests" ? (
        <SplitMoney
          initialAmount={String((p.amount || 0) / 100)}
          initialPeople={
            Array.isArray(p.changes?.participants)
              ? p.changes.participants.join(", ")
              : "me, "
          }
          onClose={cancel}
          onChanged={onChanged}
        />
      ) : p.kind === "bill_reminder" && p.resource_id ? (
        <BillReminderCard
          id={p.resource_id}
          onChanged={onChanged}
          onClose={cancel}
        />
      ) : p.kind === "recipient_transfer" ? (
        <RecipientTransferCard
          draft={p}
          onRecorded={(id) => {
            a.setPreview({
              kind: "payment",
              payment_id: id,
              payment_source: "AI_WALLET",
              requires_confirmation: true,
            });
            a.setState("ACTION_PREVIEW");
            onChanged();
          }}
          onCancel={cancel}
        />
      ) : p.kind === "payment_batch" && p.batch_id ? (
        <PaymentBatchReview
          key={p.batch_id}
          batchId={p.batch_id}
          onChanged={onChanged}
          onCancel={cancel}
        />
      ) : p.kind === "payment" && p.payment_id ? (
        <PaymentGuardian
          key={`${p.payment_id}:${p.payment_source}`}
          paymentId={p.payment_id}
          initialSource={p.payment_source}
          onChanged={onChanged}
          onCancel={cancel}
        />
      ) : (
        <div className="voice-preview">
          <span className="eyebrow">REVIEW BEFORE APPROVING</span>
          <strong>{a.previewText}</strong>
          <p>Check the exact details. Your voice prepares the action.</p>
          <div className="preview-actions">
            <button
              disabled={a.busy || a.submitting}
              onClick={() => void a.confirm()}
            >
              {a.submitting ? "Processing…" : "Confirm action"}
            </button>
            <button
              className="secondary"
              disabled={a.submitting}
              onClick={cancel}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      {a.pinRequired &&
        (p.kind === "prepare_topup" || p.kind === "prepare_withdrawal") && (
          <WalletPinDialog
            action={p.kind === "prepare_topup" ? "TOPUP" : "WITHDRAWAL"}
            amount={p.amount || 0}
            title={
              p.kind === "prepare_topup"
                ? "Add demo money"
                : "Withdraw demo money"
            }
            onClose={() => a.setPinRequired(false)}
            onApproved={async (token) => {
              const scope = `voice:${p.kind}:${p.amount}`;
              await post(
                p.kind === "prepare_topup"
                  ? "/api/bank/topups"
                  : "/api/bank/withdrawals",
                {
                  amount: p.amount,
                  approval_token: token,
                  idempotency_key: operationKey(scope),
                },
              );
              finishOperation(scope);
              a.setPinRequired(false);
              a.setPreview(undefined);
              a.setReply(
                "The approved simulated transfer is recorded in your wallet.",
              );
              a.setState("COMPLETED");
              onChanged();
            }}
          />
        )}
    </div>
  );
}
