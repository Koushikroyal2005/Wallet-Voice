import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Plus,
  ShieldCheck,
  Train,
  UserRound,
} from "lucide-react";
import {
  api,
  post,
  minorUnits,
  operationKey,
  finishOperation,
} from "../lib/api";
import { money } from "../lib/formatting";
import { Dialog } from "./Dialog";
import { WalletPinDialog } from "./WalletPinDialog";

export function WalletView({
  balance,
  onFund,
}: {
  balance: any;
  onFund: (action: "TOPUP" | "WITHDRAWAL", amount: number) => void;
}) {
  const transactions = useQuery({
    queryKey: ["transactions"],
    queryFn: () => api<any[]>("/api/wallet/transactions"),
  });
  const reservations = useQuery({
    queryKey: ["reservations"],
    queryFn: () => api<any[]>("/api/wallet/reservations"),
  });
  const [transfer, setTransfer] = useState<"TOPUP" | "WITHDRAWAL">();
  const [amount, setAmount] = useState("");
  return (
    <>
      <section className="wallet-summary surface">
        <div>
          <span className="eyebrow">AVAILABLE BALANCE</span>
          <h2 className="large-amount">
            {balance ? money(balance.available_balance) : "—"}
          </h2>
          <p>
            Total {balance ? money(balance.posted_balance) : "—"} · Reserved for payments{" "}
            {balance ? money(balance.reserved_amount) : "—"}
          </p>
        </div>
        <div className="button-row">
          <button
            onClick={() => {
              setAmount("");
              setTransfer("TOPUP");
            }}
          >
            <Plus size={17} />
            Add demo money
          </button>
          <button
            className="secondary"
            onClick={() => {
              setAmount("");
              setTransfer("WITHDRAWAL");
            }}
          >
            <ArrowUpRight size={17} />
            Withdraw demo money
          </button>
        </div>
      </section>
      <section className="surface" style={{ padding: 20, marginBottom: 24 }}>
        <span className="eyebrow">PAYMENT METHODS</span>
        <h3>PayPal at checkout</h3>
        <p>Choose PayPal when reviewing a payment. Your personal account is selected during PayPal checkout.</p>
        <details><summary>Can I see my bank balance here?</summary><p>No. Check your bank app for your current bank balance. This app’s PayPal checkout cannot retrieve it.</p></details>
      </section>
      <div className="section-heading">
        <div>
          <h2>Recent activity</h2>
          <p>Every completed movement, in one place.</p>
        </div>
        <span className="badge">Demo wallet · no real bank transfers</span>
      </div>
      <section className="surface activity-list">
        {transactions.isError ? (
          <p role="alert">
            Activity could not load.{" "}
            <button onClick={() => transactions.refetch()}>Retry</button>
          </p>
        ) : transactions.isPending ? (
          <p>Loading activity…</p>
        ) : transactions.data?.length ? (
          transactions.data.map((item) => (
            <div className="activity-row" key={item.id}>
              <span
                className={`merchant-avatar ${item.kind === "TOPUP" ? "mint" : "peach"}`}
              >
                {item.kind === "TOPUP" ? (
                  <ArrowDownLeft size={20} />
                ) : (
                  <ArrowUpRight size={20} />
                )}
              </span>
              <div>
                <strong>
                  {(
                    {
                      TOPUP: "Money added",
                      WITHDRAWAL: "Withdrawal",
                      PAYMENT: "Wallet payment",
                    } as Record<string, string>
                  )[item.kind] || item.kind}
                </strong>
                <small>
                  {new Date(item.created_at).toLocaleString("en-IN")}
                </small>
              </div>
              <span className="activity-reference">{item.reference}</span>
              <strong>
                {item.kind === "TOPUP" ? "+" : "−"}
                {money(item.amount)}
              </strong>
            </div>
          ))
        ) : (
          <div className="empty-state">
            <h3>Your story starts here</h3>
            <p>Add demo funds to make your first payment.</p>
          </div>
        )}
      </section>
      {!!reservations.data?.length && (
        <section className="surface section-block">
          <h2>Reserved for payments</h2>
          {reservations.data.map((item) => (
            <div className="activity-row" key={item.id}>
              <span>Payment in progress</span>
              <strong>{money(item.amount)}</strong>
            </div>
          ))}
        </section>
      )}
      {transfer && (
        <Dialog
          title={transfer === "TOPUP" ? "Add money" : "Withdraw money"}
          onClose={() => setTransfer(undefined)}
        >
          <p>
            {transfer === "TOPUP"
              ? "From Demo National Bank to your wallet."
              : "From your wallet to Demo National Bank."}
          </p>
          <label className="field">
            Amount in rupees
            <input
              autoFocus
              inputMode="decimal"
              placeholder="0.00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </label>
          <p className="muted">
            This moves simulated funds. You’ll enter your wallet PIN next.
          </p>
          <button
            disabled={
              !minorUnits(amount) ||
              (transfer === "WITHDRAWAL" &&
                minorUnits(amount) > (balance?.available_balance || 0))
            }
            onClick={() => {
              onFund(transfer, minorUnits(amount));
              setTransfer(undefined);
            }}
          >
            Review {minorUnits(amount) ? money(minorUnits(amount)) : "amount"}
          </button>
        </Dialog>
      )}
    </>
  );
}

export function Drafts({ onChanged }: { onChanged: () => void }) {
  const drafts = useQuery({
    queryKey: ["drafts"],
    queryFn: () => api<any[]>("/api/payment-intents"),
  });
  const recipients = useQuery({
    queryKey: ["recipients"],
    queryFn: () => api<any[]>("/api/recipients"),
  });
  const [creating, setCreating] = useState(false);
  const [addingRecipient, setAddingRecipient] = useState(false);
  const [person, setPerson] = useState({
    name: "",
    handle: "",
    handle_type: "PHONE",
  });
  const [form, setForm] = useState({ recipient_id: "", amount: "", note: "" });
  const [selected, setSelected] = useState<any>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const recipient = (id: string) =>
    recipients.data?.find((item) => item.id === id);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
      onChanged();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="section-block">
      <div className="section-heading">
        <div>
          <h2>For later</h2>
          <p>Save the details now. Decide when to pay.</p>
        </div>
        <button
          className="secondary"
          onClick={() => {
            setCreating(true);
            setError("");
          }}
        >
          <Plus size={16} />
          New draft
        </button>
      </div>
      {error && !creating && !selected && (
        <p className="error-banner" role="alert">
          {error}
        </p>
      )}
      <div className="surface">
        {drafts.isError ? (
          <p role="alert">Drafts could not load.</p>
        ) : drafts.isPending ? (
          <p>Loading drafts…</p>
        ) : drafts.data?.length ? (
          drafts.data.map((item) => (
            <div className="draft-row" key={item.id}>
              <span className="merchant-avatar lavender">
                <UserRound size={20} />
              </span>
              <div>
                <strong>
                  {recipient(item.recipient_id)?.name ||
                    item.merchant ||
                    "Saved recipient"}
                </strong>
                <small>
                  {item.note ||
                    recipient(item.recipient_id)?.handle ||
                    "Payment draft"}{" "}
                  · {item.status.toLowerCase()}
                </small>
              </div>
              <strong>{money(item.amount)}</strong>
              {!item.payment_request_id &&
                ["DRAFT", "HELD"].includes(item.status) && (
                  <div className="button-row">
                    {item.status === "DRAFT" && (
                      <button
                        disabled={busy}
                        className="text-button"
                        onClick={() =>
                          run(async () => {
                            await post(`/api/payment-intents/${item.id}/hold`);
                          })
                        }
                      >
                        Hold
                      </button>
                    )}
                    <button
                      className="secondary"
                      onClick={() => setSelected(item)}
                    >
                      Review
                    </button>
                  </div>
                )}
              {item.status === "FAILED" && (
                <small>See payment details above</small>
              )}
            </div>
          ))
        ) : (
          <div className="empty-state">
            <h3>A place for “not right now.”</h3>
            <p>Your saved payments will wait here until you’re ready.</p>
          </div>
        )}
      </div>
      {creating && (
        <Dialog
          title="Save a payment for later"
          busy={busy}
          onClose={() => setCreating(false)}
        >
          <p>
            Recipient transfers use simulated wallet funds. Saving a draft moves
            no money.
          </p>
          <div className="form-stack">
            <label className="field">
              Recipient
              <select
                value={form.recipient_id}
                onChange={(e) =>
                  setForm({ ...form, recipient_id: e.target.value })
                }
              >
                <option value="">Choose a saved recipient</option>
                {recipients.data?.map((item) => (
                  <option value={item.id} key={item.id}>
                    {item.name} · {item.handle}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="text-button"
              onClick={() => setAddingRecipient(!addingRecipient)}
            >
              <Plus size={16} />
              Add a recipient
            </button>
            {addingRecipient && (
              <fieldset>
                <legend>New recipient</legend>
                <label className="field">
                  Name
                  <input
                    value={person.name}
                    onChange={(e) =>
                      setPerson({ ...person, name: e.target.value })
                    }
                  />
                </label>
                <label className="field">
                  Contact type
                  <select
                    value={person.handle_type}
                    onChange={(e) =>
                      setPerson({ ...person, handle_type: e.target.value })
                    }
                  >
                    <option value="PHONE">Phone number</option>
                    <option value="EMAIL">Email address</option>
                  </select>
                </label>
                <label className="field">
                  {person.handle_type === "PHONE"
                    ? "Phone number with country code"
                    : "Email address"}
                  <input
                    value={person.handle}
                    onChange={(e) =>
                      setPerson({ ...person, handle: e.target.value })
                    }
                  />
                </label>
                <p className="muted">
                  Saved locally for this demo. This does not verify a PayPal or
                  bank account.
                </p>
                <button
                  className="secondary"
                  disabled={
                    busy || !person.name.trim() || !person.handle.trim()
                  }
                  onClick={() =>
                    run(async () => {
                      const created = await post("/api/recipients", person);
                      setForm((previous) => ({
                        ...previous,
                        recipient_id: created.id,
                      }));
                      setAddingRecipient(false);
                      setPerson({ name: "", handle: "", handle_type: "PHONE" });
                    })
                  }
                >
                  Save recipient
                </button>
              </fieldset>
            )}
            <label className="field">
              Amount in rupees
              <input
                inputMode="decimal"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
              />
            </label>
            <label className="field">
              What’s it for?
              <input
                maxLength={500}
                value={form.note}
                onChange={(e) => setForm({ ...form, note: e.target.value })}
                placeholder="Dinner, rent, a gift…"
              />
            </label>
            {error && (
              <p role="alert" className="error-banner">
                {error}
              </p>
            )}
            <button
              disabled={busy || !form.recipient_id || !minorUnits(form.amount)}
              onClick={() =>
                run(async () => {
                  await post("/api/payment-intents", {
                    recipient_id: form.recipient_id,
                    amount: minorUnits(form.amount),
                    note: form.note,
                    source: "AI_WALLET",
                  });
                  setCreating(false);
                  setForm({ recipient_id: "", amount: "", note: "" });
                })
              }
            >
              Save draft
            </button>
          </div>
        </Dialog>
      )}
      {selected && (
        <WalletPinDialog
          action="P2P"
          amount={selected.amount}
          resourceId={selected.id}
          details={{ version: selected.version, source: selected.source }}
          summary={[
            {
              label: "Recipient",
              value:
                recipient(selected.recipient_id)?.name || selected.merchant,
            },
            {
              label: "Destination",
              value:
                recipient(selected.recipient_id)?.handle || "Demo recipient",
            },
            { label: "From", value: "Simulated wallet balance" },
          ]}
          title="Review your transfer"
          onClose={() => setSelected(undefined)}
          onApproved={async (token) => {
            const outcome = await post(
              `/api/payment-intents/${selected.id}/execute`,
              {
                approval_token: token,
                idempotency_key: operationKey(`draft:${selected.id}`),
              },
            );
            onChanged();
            if (outcome.payment?.status === "FAILED")
              setError(
                outcome.payment.failure_reason ||
                  "Payment failed. Your funds were released.",
              );
            setSelected(undefined);
          }}
        />
      )}
    </section>
  );
}

export function Permissions({ onChanged }: { onChanged: () => void }) {
  const [section, setSection] = useState<"autopay" | "security">("autopay");
  const mandates = useQuery({
    queryKey: ["mandates"],
    queryFn: () => api<any[]>("/api/mandates"),
  });
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: () => api("/api/autopay/settings"),
  });
  const [create, setCreate] = useState(false);
  const [form, setForm] = useState({
    merchant: "Indian Railways",
    max: "1500",
    daily: "3000",
    days: "30",
  });
  const [authorize, setAuthorize] = useState<any>();
  const [editPolicy, setEditPolicy] = useState<any>();
  const [changePin, setChangePin] = useState(false);
  const [pin, setPin] = useState({ current: "", next: "", confirm: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
      onChanged();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="assistant-mode-switch" aria-label="Payment settings">
        <button aria-pressed={section === "autopay"} onClick={() => setSection("autopay")}>Auto-pay</button>
        <button aria-pressed={section === "security"} onClick={() => setSection("security")}>Security</button>
      </div>
      {section === "autopay" && <>
      <div className="section-heading">
        <div>
          <h2>Faster checkout</h2>
          <p>Choose businesses your wallet can pay without asking each time, within limits you approve.</p>
        </div>
        <button onClick={() => setCreate(true)}>
          <Plus size={16} />
          Choose a business
        </button>
      </div>
      {error && !create && !changePin && !editPolicy && (
        <p className="error-banner" role="alert">
          {error}
        </p>
      )}
      <section className="permission-list">
        {mandates.isError ? (
          <p role="alert">Permissions could not load.</p>
        ) : mandates.isPending ? (
          <p>Loading permissions…</p>
        ) : mandates.data?.length ? (
          mandates.data.map((item) => {
            const active =
              item.status === "ACTIVE" &&
              Date.parse(item.expires_at) > Date.now();
            return (
              <article className="surface permission-card" key={item.id}>
                <div className="section-heading">
                  <span className="merchant-avatar mint">
                    <ShieldCheck size={21} />
                  </span>
                  <span className={`badge ${active ? "positive" : ""}`}>
                    {active
                      ? "Active"
                      : item.status === "REVOKED"
                        ? "Revoked"
                        : "Expired"}
                  </span>
                </div>
                <h3>{item.merchant}</h3>
                <p>
                  Up to <strong>{money(item.max_amount)}</strong> per payment
                </p>
                <div className="allowance">
                  <span>Used today</span>
                  <b>
                    {money(item.spent_today)} / {money(item.daily_limit)}
                  </b>
                </div>
                <progress
                  max={item.daily_limit}
                  value={item.spent_today}
                  aria-label="Daily allowance used"
                />
                <div className="permission-footer">
                  <small>
                    Until{" "}
                    {new Date(item.expires_at).toLocaleDateString("en-IN")}
                  </small>
                  {active && (
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          await post(`/api/mandates/${item.id}/revoke`);
                        })
                      }
                    >
                      Stop automatic checkout
                    </button>
                  )}
                </div>
              </article>
            );
          })
        ) : (
          <div className="surface empty-state">
            <ShieldCheck size={26} />
            <h3>No businesses approved for automatic checkout</h3>
            <p>
              You review each checkout payment yourself. Choose a business above to set a spending limit.
            </p>
          </div>
        )}
      </section>
      <p className="assistant-privacy">Checkout approvals and automatic request payments are separate. Turning off request payments below does not stop an approved business’s checkout payments.</p>
      </>}
      {section === "security" && <>
      <section className="surface section-block setting-panel">
        <div>
          <span className="round-icon">
            <ShieldCheck size={20} />
          </span>
          <h3>Wallet PIN</h3>
          <p>
            Use your six-digit PIN to approve adding money, withdrawing money, and sending money to people. Never share it with the assistant.
          </p>
        </div>
        <button
          className="secondary"
          onClick={() => {
            setPin({ current: "", next: "", confirm: "" });
            setChangePin(true);
            setError("");
          }}
        >
          Change PIN
        </button>
      </section>
      </>}
      {section === "autopay" && <>
      <section className="surface section-block setting-panel">
        <div>
          <span className="eyebrow">INCOMING PAYMENT REQUESTS</span>
          <h3>
            {settings.data?.enabled
              ? "Pay eligible requests automatically: On"
              : "Pay eligible requests automatically: Off"}
          </h3>
          <p>
            {settings.data
              ? `Up to ${money(settings.data.per_transaction_limit)} per payment · ${money(settings.data.daily_limit)} per day`
              : "Loading spending rules…"}
          </p>
          <small>
            Requests you put on hold always wait for you. Only recognised businesses qualify, and your spending limits still apply.
          </small>
        </div>
        <button
          className="secondary"
          disabled={!settings.data}
          onClick={() =>
            setEditPolicy({
              ...settings.data,
              per_transaction_limit: String(
                settings.data.per_transaction_limit / 100,
              ),
              daily_limit: String(settings.data.daily_limit / 100),
              minimum_balance: String(settings.data.minimum_balance / 100),
            })
          }
        >
          Change request payment settings
        </button>
      </section>
      </>}
      {create && !authorize && (
        <Dialog
          title="Allow faster checkout"
          busy={busy}
          onClose={() => setCreate(false)}
        >
          <div className="form-stack">
            <label className="field">
              Which business can your wallet pay?
              <input
                value={form.merchant}
                onChange={(e) => setForm({ ...form, merchant: e.target.value })}
              />
            </label>
            {[
              ["max", "Most it can pay at once (₹)"],
              ["daily", "Most it can pay in one day (₹)"],
              ["days", "Stop this permission after how many days?"],
            ].map(([key, label]) => (
              <label className="field" key={key}>
                {label}
                <input
                  inputMode="decimal"
                  value={form[key as keyof typeof form]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                />
              </label>
            ))}
            <p>
              Payments within these limits may complete from the merchant page
              without another prompt.
            </p>
            <button
              disabled={
                !form.merchant.trim() ||
                !minorUnits(form.max) ||
                minorUnits(form.daily) < minorUnits(form.max) ||
                !Number.isInteger(Number(form.days)) ||
                Number(form.days) < 1 ||
                Number(form.days) > 365
              }
              onClick={() => {
                const expires = new Date(
                  Date.now() + Number(form.days) * 86400000,
                );
                setAuthorize({
                  merchant: form.merchant.trim(),
                  max_amount: minorUnits(form.max),
                  daily_limit: minorUnits(form.daily),
                  expires_at: expires.toISOString(),
                  epoch: Math.floor(expires.getTime() / 1000),
                });
              }}
            >
              Review checkout approval
            </button>
          </div>
        </Dialog>
      )}
      {authorize && (
        <WalletPinDialog
          title="Approve automatic checkout"
          action="MANDATE"
          amount={authorize.max_amount}
          resourceId={authorize.merchant}
          details={{
            merchant: authorize.merchant,
            daily_limit: authorize.daily_limit,
            expires_at: authorize.epoch,
          }}
          summary={[
            { label: "Business", value: authorize.merchant },
            { label: "Maximum in one day", value: money(authorize.daily_limit) },
            {
              label: "Stops on",
              value: new Date(authorize.expires_at).toLocaleString("en-IN"),
            },
            {
              label: "Approval",
              value: "Checkout payments from your demo wallet inside these limits will not ask again. Other payment checks still apply.",
            },
          ]}
          onClose={() => setAuthorize(undefined)}
          onApproved={async (token) => {
            await post("/api/mandates", {
              ...authorize,
              approval_token: token,
            });
            setAuthorize(undefined);
            setCreate(false);
            onChanged();
          }}
        />
      )}
      {changePin && (
        <Dialog
          title="Change your wallet PIN"
          busy={busy}
          onClose={() => setChangePin(false)}
        >
          <div className="form-stack">
            {[
              ["current", "Current PIN"],
              ["next", "New PIN"],
              ["confirm", "Confirm new PIN"],
            ].map(([key, label]) => (
              <label className="field" key={key}>
                {label}
                <input
                  type="password"
                  inputMode="numeric"
                  autoComplete={
                    key === "current" ? "current-password" : "new-password"
                  }
                  maxLength={6}
                  value={pin[key as keyof typeof pin]}
                  onChange={(e) =>
                    setPin({ ...pin, [key]: e.target.value.replace(/\D/g, "") })
                  }
                />
              </label>
            ))}
            <p>Changing your PIN cancels all unused approvals.</p>
            {error && (
              <p className="error-banner" role="alert">
                {error}
              </p>
            )}
            <button
              disabled={
                busy ||
                pin.current.length !== 6 ||
                pin.next.length !== 6 ||
                pin.next !== pin.confirm
              }
              onClick={() =>
                run(async () => {
                  await post("/api/security/pin/change", {
                    current_pin: pin.current,
                    new_pin: pin.next,
                  });
                  setChangePin(false);
                  setPin({ current: "", next: "", confirm: "" });
                })
              }
            >
              Update PIN
            </button>
          </div>
        </Dialog>
      )}
      {editPolicy && (
        <Dialog
          title="Your automatic payment rules"
          busy={busy}
          onClose={() => setEditPolicy(undefined)}
        >
          <div className="form-stack">
            <label className="check-label">
              <input
                type="checkbox"
                checked={editPolicy.enabled}
                onChange={(e) =>
                  setEditPolicy({ ...editPolicy, enabled: e.target.checked })
                }
              />
              Allow automatic payments to known merchants
            </label>
            <label className="check-label">
              <input
                type="checkbox"
                checked={editPolicy.time_sensitive_only}
                onChange={(e) =>
                  setEditPolicy({
                    ...editPolicy,
                    time_sensitive_only: e.target.checked,
                  })
                }
              />
              Only urgent or due-soon payments
            </label>
            {[
              ["per_transaction_limit", "Maximum per payment (₹)"],
              ["daily_limit", "Maximum per day (₹)"],
              ["minimum_balance", "Keep at least (₹)"],
            ].map(([key, label]) => (
              <label className="field" key={key}>
                {label}
                <input
                  inputMode="decimal"
                  value={editPolicy[key]}
                  onChange={(e) =>
                    setEditPolicy({ ...editPolicy, [key]: e.target.value })
                  }
                />
              </label>
            ))}
            {error && (
              <p className="error-banner" role="alert">
                {error}
              </p>
            )}
            <button
              disabled={
                busy ||
                !minorUnits(editPolicy.per_transaction_limit) ||
                !minorUnits(editPolicy.daily_limit) ||
                (editPolicy.minimum_balance !== "0" &&
                  !minorUnits(editPolicy.minimum_balance))
              }
              onClick={() =>
                run(async () => {
                  await api("/api/autopay/settings", {
                    method: "PATCH",
                    body: JSON.stringify({
                      enabled: editPolicy.enabled,
                      time_sensitive_only: editPolicy.time_sensitive_only,
                      per_transaction_limit: minorUnits(
                        editPolicy.per_transaction_limit,
                      ),
                      daily_limit: minorUnits(editPolicy.daily_limit),
                      minimum_balance: minorUnits(editPolicy.minimum_balance),
                    }),
                  });
                  setEditPolicy(undefined);
                })
              }
            >
              Save rules
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}

export function MerchantDemo({ onChanged }: { onChanged: () => void }) {
  const [order, setOrder] = useState(() => `DEMO-${crypto.randomUUID()}`);
  const [result, setResult] = useState<any>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const status = useQuery({
    queryKey: ["merchant-order", result?.payment_request?.id],
    queryFn: () => api(`/api/demo/checkout/${result.payment_request.id}`),
    enabled: !!result?.payment_request?.id,
    refetchInterval: 2000,
  });
  const state = status.data?.status || result?.status;
  return (
    <div className="merchant-demo-grid">
      <section className="ticket-card surface">
        <span className="badge">
          <Train size={14} /> SAMPLE MERCHANT · INDIAN RAILWAYS
        </span>
        <h2>
          A window seat.
          <br />A simpler checkout.
        </h2>
        <div className="journey">
          <div>
            <strong>HYD</strong>
            <span>Hyderabad</span>
          </div>
          <span className="journey-line" />
          <Train />
          <span className="journey-line" />
          <div>
            <strong>BLR</strong>
            <span>Bengaluru</span>
          </div>
        </div>
        <div className="ticket-details">
          <span>Demo railway ticket</span>
          <strong>{money(125000)}</strong>
        </div>
        <p>This is a sample merchant checkout, not an IRCTC booking.</p>
        <button
          disabled={busy || !!result}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              setResult(
                await post("/api/demo/checkout", { order_reference: order }),
              );
              onChanged();
            } catch (cause) {
              setError((cause as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Contacting your wallet…" : "Pay with AI Wallet"}
          <ArrowUpRight size={18} />
        </button>
        {error && (
          <p role="alert" className="error-banner">
            {error}
          </p>
        )}
      </section>
      <section className="surface checkout-explainer">
        <span className="round-icon">
          <ShieldCheck size={22} />
        </span>
        <h2>
          {state === "SUCCEEDED"
            ? "You’re paid up."
            : state === "HELD" || state === "AWAITING_USER_APPROVAL"
              ? "Your approval is needed."
              : result
                ? "Your wallet is handling it."
                : "Permission comes first."}
        </h2>
        <p>
          {state === "SUCCEEDED"
            ? "Your saved merchant permission covered this ticket. The payment completed without leaving this page."
            : state === "HELD" || state === "AWAITING_USER_APPROVAL"
              ? "No matching permission covered this order. It is held in Payments until you release and approve it."
              : "Add an Indian Railways permission for at least ₹1,250 in Permissions. Then try this checkout to see payment happen right here."}
        </p>
        {result && (
          <>
            <span className="badge">
              {state?.toLowerCase().replaceAll("_", " ")}
            </span>
            <button
              className="secondary"
              onClick={() => {
                setResult(undefined);
                setOrder(`DEMO-${crypto.randomUUID()}`);
              }}
            >
              Start another sample order
            </button>
          </>
        )}
        <small>
          Your merchant API key stays on the server. This sample endpoint is
          available only in demo mode.
        </small>
      </section>
    </div>
  );
}
