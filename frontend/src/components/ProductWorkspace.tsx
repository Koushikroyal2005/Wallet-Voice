import { useEffect, useState } from "react";
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  Clock3,
  Plus,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { money } from "../lib/formatting";
import { WalletPinDialog } from "./WalletPinDialog";

const json = async (path: string, init?: RequestInit) => {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok)
    throw new Error(
      (await response.json().catch(() => null))?.detail ||
        (await response.text()),
    );
  return response.json();
};

export function WalletWorkspace({
  onFund,
  onChanged,
}: {
  onFund: (action: "TOPUP" | "WITHDRAWAL", amount: number) => void;
  onChanged: () => void;
}) {
  const [amount, setAmount] = useState("2000");
  const [activity, setActivity] = useState<any[]>([]);
  useEffect(() => {
    json("/api/wallet/transactions")
      .then(setActivity)
      .catch(() => setActivity([]));
  }, []);
  const minor = Math.round(Number(amount || 0) * 100);
  return (
    <section className="workspace-grid">
      <div className="surface transfer-surface">
        <span className="eyebrow">MOVE MONEY</span>
        <h2>Fund or withdraw from your wallet</h2>
        <p>
          Choose the amount first. Your six-digit AI Wallet PIN authorizes only
          this transfer.
        </p>
        <label htmlFor="transfer-amount">Amount in rupees</label>
        <div className="amount-input">
          <span>₹</span>
          <input
            id="transfer-amount"
            inputMode="decimal"
            value={amount}
            onChange={(event) =>
              setAmount(event.target.value.replace(/[^0-9.]/g, ""))
            }
          />
        </div>
        <div className="transfer-actions">
          <button disabled={!minor} onClick={() => onFund("TOPUP", minor)}>
            <ArrowDownToLine size={17} /> Add funds
          </button>
          <button
            className="secondary"
            disabled={!minor}
            onClick={() => onFund("WITHDRAWAL", minor)}
          >
            <ArrowUpFromLine size={17} /> Withdraw
          </button>
        </div>
        <small>
          <ShieldCheck size={14} /> Demo bank rail. Never enter a bank or PayPal
          password here.
        </small>
      </div>
      <div className="surface">
        <div className="section-heading">
          <div>
            <h2>Recent wallet activity</h2>
            <p>Journal-confirmed balance changes.</p>
          </div>
        </div>
        <div className="activity-list">
          {activity.slice(0, 8).map((item) => (
            <div className="activity-row" key={item.id}>
              <span className="activity-icon">
                {item.kind === "TOPUP" ? (
                  <ArrowDownToLine size={16} />
                ) : (
                  <ArrowUpFromLine size={16} />
                )}
              </span>
              <div>
                <b>{item.kind.replaceAll("_", " ")}</b>
                <small>
                  {new Date(item.created_at).toLocaleString("en-IN")}
                </small>
              </div>
              <strong>
                {item.kind === "TOPUP" ? "+" : "−"}
                {money(item.amount)}
              </strong>
            </div>
          ))}
          {!activity.length && <p className="muted">No wallet activity yet.</p>}
        </div>
      </div>
    </section>
  );
}

export function DraftsWorkspace({ onChanged }: { onChanged: () => void }) {
  const [drafts, setDrafts] = useState<any[]>([]);
  const [recipients, setRecipients] = useState<any[]>([]);
  const [form, setForm] = useState({ merchant: "", amount: "", note: "" });
  const [execute, setExecute] = useState<any>();
  const [message, setMessage] = useState("");
  const load = () =>
    Promise.all([json("/api/payment-intents"), json("/api/recipients")])
      .then(([a, b]) => {
        setDrafts(a);
        setRecipients(b);
      })
      .catch((error) => setMessage(error.message));
  useEffect(() => {
    void load();
  }, []);
  const create = async () => {
    try {
      await json("/api/payment-intents", {
        method: "POST",
        body: JSON.stringify({
          merchant: form.merchant,
          amount: Math.round(Number(form.amount) * 100),
          note: form.note,
          source: "AI_WALLET",
        }),
      });
      setForm({ merchant: "", amount: "", note: "" });
      await load();
      onChanged();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Could not save draft",
      );
    }
  };
  return (
    <section className="workspace-grid">
      <div className="surface">
        <span className="eyebrow">PAY LATER</span>
        <h2>Create a payment draft</h2>
        <p>
          Saving a draft never moves money. You can hold it or authorize it
          later.
        </p>
        <div className="form-stack">
          <label>
            Recipient or merchant
            <input
              value={form.merchant}
              onChange={(event) =>
                setForm({ ...form, merchant: event.target.value })
              }
              placeholder="Asha or merchant name"
            />
          </label>
          <label>
            Amount in rupees
            <input
              inputMode="decimal"
              value={form.amount}
              onChange={(event) =>
                setForm({
                  ...form,
                  amount: event.target.value.replace(/[^0-9.]/g, ""),
                })
              }
              placeholder="500"
            />
          </label>
          <label>
            Note
            <input
              value={form.note}
              onChange={(event) =>
                setForm({ ...form, note: event.target.value })
              }
              placeholder="Dinner, rent, ticket…"
            />
          </label>
          <button
            disabled={!form.merchant || !Number(form.amount)}
            onClick={create}
          >
            <Plus size={16} /> Save draft
          </button>
        </div>
        {message && <p className="error-message">{message}</p>}
        <p className="muted">
          <UserRound size={14} /> {recipients.length} saved recipients
        </p>
      </div>
      <div className="surface">
        <div className="section-heading">
          <div>
            <h2>Drafts and held payments</h2>
            <p>Nothing here executes without a separate approval.</p>
          </div>
        </div>
        <div className="draft-list">
          {drafts.map((draft) => (
            <article className="draft-row" key={draft.id}>
              <div>
                <b>{draft.merchant || "Saved recipient"}</b>
                <span>{draft.note || "Payment draft"}</span>
                <small>
                  <Clock3 size={12} /> {draft.status}
                </small>
              </div>
              <strong>{money(draft.amount)}</strong>
              <div>
                <button
                  className="secondary"
                  onClick={async () => {
                    await json(`/api/payment-intents/${draft.id}/hold`, {
                      method: "POST",
                    });
                    await load();
                  }}
                >
                  Hold
                </button>
                <button onClick={() => setExecute(draft)}>Pay</button>
              </div>
            </article>
          ))}
          {!drafts.length && (
            <p className="muted">
              No drafts yet. Ask the assistant or create one here.
            </p>
          )}
        </div>
      </div>
      {execute && (
        <WalletPinDialog
          action="P2P"
          amount={execute.amount}
          resourceId={execute.id}
          details={{ version: execute.version, source: execute.source }}
          title="Authorize this payment"
          onClose={() => setExecute(undefined)}
          onApproved={async (token) => {
            await json(`/api/payment-intents/${execute.id}/execute`, {
              method: "POST",
              body: JSON.stringify({
                approval_token: token,
                idempotency_key: crypto.randomUUID(),
              }),
            });
            setExecute(undefined);
            await load();
            onChanged();
          }}
        />
      )}
    </section>
  );
}

export function PermissionsWorkspace({
  children,
  onChanged,
}: {
  children: React.ReactNode;
  onChanged: () => void;
}) {
  const [mandates, setMandates] = useState<any[]>([]);
  const [proposal, setProposal] = useState({
    merchant: "Indian Railways",
    max: "1500",
    daily: "3000",
    days: "30",
  });
  const [authorize, setAuthorize] = useState<any>();
  const [message, setMessage] = useState("");
  const load = () =>
    json("/api/mandates")
      .then(setMandates)
      .catch((error) => setMessage(error.message));
  useEffect(() => {
    void load();
  }, []);
  const prepared = () => {
    const expires = new Date(Date.now() + Number(proposal.days) * 86400000);
    return {
      merchant: proposal.merchant,
      max_amount: Math.round(Number(proposal.max) * 100),
      daily_limit: Math.round(Number(proposal.daily) * 100),
      expires_at: expires.toISOString(),
      expiry_epoch: Math.floor(expires.getTime() / 1000),
    };
  };
  return (
    <>
      <section className="workspace-grid permissions-grid">
        <div className="surface">
          <span className="eyebrow">MERCHANT PERMISSION</span>
          <h2>Set a clear spending boundary</h2>
          <div className="form-stack">
            <label>
              Merchant
              <input
                value={proposal.merchant}
                onChange={(event) =>
                  setProposal({ ...proposal, merchant: event.target.value })
                }
              />
            </label>
            <label>
              Maximum per payment
              <input
                inputMode="decimal"
                value={proposal.max}
                onChange={(event) =>
                  setProposal({ ...proposal, max: event.target.value })
                }
              />
            </label>
            <label>
              Daily limit
              <input
                inputMode="decimal"
                value={proposal.daily}
                onChange={(event) =>
                  setProposal({ ...proposal, daily: event.target.value })
                }
              />
            </label>
            <label>
              Valid for days
              <input
                inputMode="numeric"
                value={proposal.days}
                onChange={(event) =>
                  setProposal({ ...proposal, days: event.target.value })
                }
              />
            </label>
            <button onClick={() => setAuthorize(prepared())}>
              Review and authorize
            </button>
          </div>
          {message && <p className="error-message">{message}</p>}
        </div>
        <div className="surface">
          <div className="section-heading">
            <div>
              <h2>Active permissions</h2>
              <p>Revoke access at any time.</p>
            </div>
          </div>
          <div className="mandate-list">
            {mandates.map((item) => (
              <article className="mandate-row" key={item.id}>
                <div>
                  <b>{item.merchant}</b>
                  <span>
                    Up to {money(item.max_amount)} · {money(item.daily_limit)}{" "}
                    daily
                  </span>
                  <small>
                    Expires{" "}
                    {new Date(item.expires_at).toLocaleDateString("en-IN")}
                  </small>
                </div>
                <span className={`badge status-${item.status.toLowerCase()}`}>
                  {item.status}
                </span>
                {item.status === "ACTIVE" && (
                  <button
                    className="secondary"
                    onClick={async () => {
                      await json(`/api/mandates/${item.id}/revoke`, {
                        method: "POST",
                      });
                      await load();
                      onChanged();
                    }}
                  >
                    Revoke
                  </button>
                )}
              </article>
            ))}
            {!mandates.length && (
              <p className="muted">No merchant permissions yet.</p>
            )}
          </div>
        </div>
      </section>
      {children}
      {authorize && (
        <WalletPinDialog
          action="MANDATE"
          amount={authorize.max_amount}
          resourceId={authorize.merchant}
          details={{
            merchant: authorize.merchant,
            daily_limit: authorize.daily_limit,
            expires_at: authorize.expiry_epoch,
          }}
          title="Authorize merchant permission"
          onClose={() => setAuthorize(undefined)}
          onApproved={async (token) => {
            await json("/api/mandates", {
              method: "POST",
              body: JSON.stringify({ ...authorize, approval_token: token }),
            });
            setAuthorize(undefined);
            await load();
            onChanged();
          }}
        />
      )}
    </>
  );
}
