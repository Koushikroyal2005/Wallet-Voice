import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Download,
  Layers,
  Mic,
  Plus,
  ReceiptText,
  Send,
  Wallet,
} from "lucide-react";
import { api, post, minorUnits } from "../lib/api";
import { currencyMoney } from "../lib/formatting";
import { Dialog } from "./Dialog";
import { Permissions } from "./Workspace";
import { AttentionQueue } from "./AttentionQueue";
import { VoiceSettings } from "./VoiceSettings";
import { DocumentCenter } from "./DocumentCenter";
import { SplitHistory } from "./SplitMoney";
import { NotificationCategories, RenewalControls } from "./PlanningControls";
import {ActivityTimeline} from './ActivityTimeline';

export type Destination =
  | "home"
  | "pay"
  | "payments"
  | "activity"
  | "wallet"
  | "permissions"
  | "merchant"
  | "accounts"
  | "bills"
  | "settings";
type RequestRow = {
  id: string;
  payer: string;
  amount: number;
  currency: string;
  note: string;
  status: string;
  share_text: string;
};
type Bill = {
  id: string;
  merchant: string;
  amount: number;
  currency: string;
  due_at: string;
  recurring: boolean;
  cadence?: string;
  remind_at?: string;
  active: boolean;
};
type Source = {
  id: string;
  label: string;
  configured: boolean;
  approval: string;
  operations: string[];
};
type RecordItem = {
  id: string;
  merchant: string;
  amount: number;
  currency: string;
  status: string;
  attempt_id?: string;
  receipt?: { journal_id: string };
};
type Batch = {
  id: string;
  status: string;
  total: number;
  currency: string;
  created_at: string;
  items: RecordItem[];
};
type Operation = {
  id: string;
  kind: string;
  amount: number;
  status: string;
  reference: string;
  created_at: string;
};
type ExternalRecord = {
  order_id: string;
  payment_request_id: string;
  original_amount: number;
  original_currency: string;
  status: string;
  capture_id?: string;
};

export function PayHub({
  onSend,
  onRequest,
  onBatch,
  onBills,
}: {
  onSend: () => void;
  onRequest: () => void;
  onBatch: () => void;
  onBills: () => void;
}) {
  const [recipientSearch, setRecipientSearch] = useState("");
  const recipients = useQuery({
    queryKey: ["recipients"],
    queryFn: () =>
      api<{ id: string; name: string; handle: string }[]>("/api/recipients"),
  });
  return (
    <div className="consumer-stack">
      <section className="batch-feature surface">
        <span className="eyebrow">PAY NATURALLY. PAY TOGETHER.</span>
        <Layers size={28} />
        <h2>Pay several at once.</h2>
        <p>
          Select your saved payments. Review every amount. Approve an eligible
          exact wallet batch with one PIN.
        </p>
        <div className="button-row">
          <button onClick={onBatch}>
            Select payments <ArrowUpRight size={17} />
          </button>
          <button
            className="secondary"
            onClick={() =>
              window.dispatchEvent(
                new CustomEvent("wallet-assistant-open", { detail: "voice" }),
              )
            }
          >
            <Mic size={17} />
            Use voice
          </button>
        </div>
        <small>
          Simulated wallet only. PayPal requires its own buyer approval.
        </small>
      </section>
      <div className="pay-action-grid">
        <button onClick={onSend}>
          <Send />
          Send money<small>Choose a saved recipient</small>
        </button>
        <button onClick={onRequest}>
          <Plus />
          Request money<small>Save a simulated request</small>
        </button>
        <button onClick={onBills}>
          <ReceiptText />
          Bills & subscriptions<small>Track expected expenses</small>
        </button>
        <button onClick={onBatch}>
          <Layers />
          Batch Pay<small>Review saved checkouts</small>
        </button>
      </div>
      <div className="button-row">
        <button
          className="secondary"
          onClick={() =>
            window.dispatchEvent(
              new CustomEvent("wallet-intake-open", { detail: "manual" }),
            )
          }
        >
          Add payment manually
        </button>
        <button
          className="secondary"
          onClick={() =>
            window.dispatchEvent(
              new CustomEvent("wallet-intake-open", { detail: "link" }),
            )
          }
        >
          Paste payment link
        </button>
        <button
          className="secondary"
          onClick={() =>
            window.dispatchEvent(
              new CustomEvent("wallet-intake-open", { detail: "qr" }),
            )
          }
        >
          Scan QR
        </button>
        <button
          className="secondary"
          onClick={() => window.dispatchEvent(new Event("wallet-split-open"))}
        >
          Split a bill
        </button>
      </div>
      <section className="surface consumer-card">
        <h2>Your saved recipients</h2>
        <input
          aria-label="Search saved recipients"
          placeholder="Name, phone or email"
          value={recipientSearch}
          onChange={(e) => setRecipientSearch(e.target.value)}
        />
        {recipients.isError ? (
          <p role="alert">
            Recipients unavailable.{" "}
            <button onClick={() => void recipients.refetch()}>Retry</button>
          </p>
        ) : Array.isArray(recipients.data) && recipients.data.length ? (
          recipients.data
            .filter((r) =>
              `${r.name} ${r.handle}`
                .toLowerCase()
                .includes(recipientSearch.toLowerCase()),
            )
            .map((r) => (
              <button
                className="recipient-tile secondary"
                key={r.id}
                onClick={() =>
                  window.dispatchEvent(
                    new CustomEvent("wallet-send-recipient", { detail: r.id }),
                  )
                }
              >
                <strong>{r.name}</strong>
                <small>
                  {r.handle} · Saved destination, not bank verification
                </small>
              </button>
            ))
        ) : (
          <p>
            Add your first recipient through Send money. We never discover or
            guess phone numbers.
          </p>
        )}
      </section>
    </div>
  );
}

export function RequestMoney({
  onClose,
  onChanged,
  initial,
}: {
  onClose: () => void;
  onChanged: () => void;
  initial?:{payer:string;amount:string;note:string};
}) {
  const [payer, setPayer] = useState(initial?.payer||""),
    [amount, setAmount] = useState(initial?.amount||""),
    [note, setNote] = useState(initial?.note||"");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [saved, setSaved] = useState<RequestRow>();
  const key = useRef(crypto.randomUUID());
  const flight = useRef(false);
  return (
    <Dialog title="Request money" busy={busy} onClose={onClose}>
      <p>
        Save a simulated request. This does not contact a bank, deliver a
        message or move money.
      </p>
      {saved ? (
        <div className="consumer-stack">
          <h3>Request saved · Not paid</h3>
          <strong className="review-amount">
            {currencyMoney(saved.amount, saved.currency)}
          </strong>
          <p>
            {saved.payer} · {saved.note}
          </p>
          <textarea
            readOnly
            aria-label="Shareable request summary"
            value={saved.share_text}
          />
          <p>
            Select and copy this summary to share. There is no public payment
            link yet.
          </p>
          <button onClick={onClose}>Done</button>
        </div>
      ) : (
        <form
          className="form-stack"
          onSubmit={async (e) => {
            e.preventDefault();
            if (flight.current) return;
            flight.current = true;
            setBusy(true);
            setError("");
            try {
              setSaved(
                await post<RequestRow>("/api/product/money-requests", {
                  payer: payer.trim(),
                  amount: minorUnits(amount),
                  note,
                  request_key: key.current,
                }),
              );
              onChanged();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              flight.current = false;
              setBusy(false);
            }
          }}
        >
          <label className="field">
            Who should pay?
            <input
              required
              maxLength={120}
              value={payer}
              onChange={(e) => setPayer(e.target.value)}
            />
          </label>
          <label className="field">
            Amount (INR)
            <input
              required
              inputMode="decimal"
              value={amount}
              placeholder="0.00"
              onChange={(e) => setAmount(e.target.value)}
            />
          </label>
          <label className="field">
            Note (optional)
            <input
              maxLength={500}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
          <small>
            Enter a payer and an exact positive INR amount. No funds will be
            reserved.
          </small>
          {error && (
            <p role="alert" className="error-banner">
              {error}
            </p>
          )}
          <button disabled={busy || !payer.trim() || !minorUnits(amount)}>
            {busy ? "Saving…" : "Save request"}
          </button>
        </form>
      )}
    </Dialog>
  );
}

export function AccountsScreen() {
  const balance = useQuery({
    queryKey: ["wallet"],
    queryFn: () =>
      api<{
        posted_balance: number;
        reserved_amount: number;
        available_balance: number;
      }>("/api/wallet"),
  });
  const sources = useQuery({
    queryKey: ["sources"],
    queryFn: () => api<Source[]>("/api/product/sources"),
  });
  return (
    <section className="consumer-stack">
      <section className="surface consumer-card">
        <h2>Wallet-Voice simulated balance</h2>
        {balance.data ? (
          <dl className="guardian-details">
            <div>
              <dt>Available</dt>
              <dd>{currencyMoney(balance.data.available_balance, "INR")}</dd>
            </div>
            <div>
              <dt>Posted</dt>
              <dd>{currencyMoney(balance.data.posted_balance, "INR")}</dd>
            </div>
            <div>
              <dt>Reserved</dt>
              <dd>{currencyMoney(balance.data.reserved_amount, "INR")}</dd>
            </div>
          </dl>
        ) : (
          <p role="status">
            Wallet balance {balance.isError ? "unavailable" : "loading…"}
          </p>
        )}
      </section>
      <p>
        Only the simulated wallet has an available balance here. PayPal checkout
        never debits that wallet.
      </p>
      {sources.isError ? (
        <p role="alert">
          Payment methods unavailable.{" "}
          <button onClick={() => void sources.refetch()}>Retry</button>
        </p>
      ) : Array.isArray(sources.data) ? (
        sources.data.map((s) => (
          <article className="surface source-card" key={s.id}>
            <Wallet />
            <div>
              <h2>{s.label}</h2>
              <span className="badge">
                {s.configured
                  ? s.id === "AI_WALLET"
                    ? "Simulated"
                    : "Configured · Not live-tested"
                  : "Not connected"}
              </span>
              <p>{s.approval}</p>
              <small>
                {s.operations.length
                  ? `Supported: ${s.operations.join(", ")} payments`
                  : "No bank/card connection or transfer available"}
              </small>
              {s.id !== "AI_WALLET" && (
                <p>
                  Balance unavailable. We do not collect card numbers or your
                  bank password.
                </p>
              )}
            </div>
          </article>
        ))
      ) : (
        <p>Loading payment methods…</p>
      )}
    </section>
  );
}

export function ActivityScreen({
  onBatch,
  onPayment,
  onChanged,
}: {
  onBatch: (id: string) => void;
  onPayment: (id: string) => void;
  onChanged: () => void;
}) {
  const batches = useQuery({
    queryKey: ["batch-history"],
    queryFn: () => api<Batch[]>("/api/product/batches"),
  });
  const operations = useQuery({
    queryKey: ["transactions"],
    queryFn: () => api<Operation[]>("/api/wallet/transactions"),
  });
  const requests = useQuery({
    queryKey: ["money-requests"],
    queryFn: () => api<RequestRow[]>("/api/product/money-requests"),
  });
  const external = useQuery({
    queryKey: ["paypal-history"],
    queryFn: () => api<ExternalRecord[]>("/api/paypal/payments"),
  });
  const [search, setSearch] = useState(""),
    [filter, setFilter] = useState("All"),
    [error, setError] = useState("");
  const includes = (value: string) =>
    value.toLowerCase().includes(search.toLowerCase());
  return (
    <div className="consumer-stack">
      <ActivityTimeline onBatch={onBatch} onPayment={onPayment}/>
      <details><summary>Documents & shared bill requests</summary><DocumentCenter/><SplitHistory/></details>
      <details className="activity-archive"><summary>Detailed histories & money requests</summary>
      <div className="toolbar">
        <input
          aria-label="Search activity"
          placeholder="Search merchant, reference or status"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          aria-label="Activity filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          {[
            "All",
            "Batch payments",
            "Wallet movements",
            "Money requests",
            "Processing",
            "Failed",
          ].map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
      </div>
      {(batches.isError || operations.isError || requests.isError) && (
        <p role="alert">
          Some activity could not load.{" "}
          <button onClick={onChanged}>Refresh</button>
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {["All", "Batch payments", "Processing", "Failed"].includes(filter) && (
        <section className="surface consumer-card">
          <h2>Batch payments & statements</h2>
          {Array.isArray(batches.data) &&
            batches.data
              .filter(
                (b) =>
                  includes(
                    `${b.id} ${b.status} ${b.items.map((i) => i.merchant).join(" ")}`,
                  ) &&
                  (!["Processing", "Failed"].includes(filter) ||
                    b.status ===
                      (filter === "Processing" ? "PROCESSING" : "FAILED")),
              )
              .map((b) => (
                <article className="record-row" key={b.id}>
                  <div>
                    <strong>
                      {b.items.length} payments · {b.status.toLowerCase()}
                    </strong>
                    <small>
                      {new Date(b.created_at).toLocaleString()} · {b.id}
                    </small>
                  </div>
                  <div className="button-row">
                    <button className="secondary" onClick={() => onBatch(b.id)}>
                      View batch
                    </button>
                    <a
                      className="document-link"
                      href={`/api/product/documents/batches/${b.id}.pdf`}
                    >
                      <Download size={16} />
                      Statement PDF
                    </a>
                  </div>
                  <details>
                    <summary>Individual payment records</summary>
                    {b.items.map((i) => (
                      <p key={i.id}>
                        {i.merchant} · {currencyMoney(i.amount, i.currency)} ·{" "}
                        {i.status}{" "}
                        {i.attempt_id && (
                          <>
                            <button
                              className="text-button"
                              onClick={() => onPayment(i.id)}
                            >
                              Details
                            </button>
                            <a
                              className="document-link"
                              href={`/api/product/documents/payments/${i.id}.pdf`}
                            >
                              Payment PDF
                            </a>
                          </>
                        )}
                      </p>
                    ))}
                  </details>
                </article>
              ))}
          {(!Array.isArray(batches.data) || !batches.data.length) && (
            <p>
              No batch records yet. Prepare one from Inbox or ask your
              assistant.
            </p>
          )}
        </section>
      )}
      {["All", "Wallet movements"].includes(filter) && (
        <section className="surface consumer-card">
          <h2>Wallet movements</h2>
          {Array.isArray(operations.data) &&
            operations.data
              .filter((o) =>
                includes(`${o.reference} ${o.kind} ${o.created_at}`),
              )
              .map((o) => (
                <article className="record-row" key={o.id}>
                  <div>
                    <strong>
                      {o.kind.replaceAll("_", " ")} ·{" "}
                      {currencyMoney(o.amount, "INR")}
                    </strong>
                    <small>
                      {o.status} · {new Date(o.created_at).toLocaleString()} ·{" "}
                      {o.reference}
                    </small>
                  </div>
                  <span className="badge">Simulated</span>
                </article>
              ))}
          {Array.isArray(operations.data) && !operations.data.length && (
            <p>No recorded wallet movements.</p>
          )}
        </section>
      )}
      {filter === "All" && (
        <section className="surface consumer-card">
          <h2>PayPal Sandbox records</h2>
          {external.isError && (
            <p role="alert">
              PayPal history unavailable.{" "}
              <button onClick={() => void external.refetch()}>Retry</button>
            </p>
          )}
          {Array.isArray(external.data) &&
            external.data
              .filter((r) =>
                includes(`${r.order_id} ${r.status} ${r.capture_id || ""}`),
              )
              .map((r) => (
                <article className="record-row" key={r.order_id}>
                  <div>
                    <strong>
                      {currencyMoney(r.original_amount, r.original_currency)} ·{" "}
                      {r.status}
                    </strong>
                    <small>
                      PayPal Sandbox · Order {r.order_id} · Capture{" "}
                      {r.capture_id || "Not recorded"}
                    </small>
                  </div>
                  <button
                    className="secondary"
                    onClick={() => onPayment(r.payment_request_id)}
                  >
                    View provider record
                  </button>
                </article>
              ))}
          {Array.isArray(external.data) && !external.data.length && (
            <p>
              No external orders recorded. PayPal checkout does not use the
              simulated wallet.
            </p>
          )}
        </section>
      )}
      {["All", "Money requests"].includes(filter) && (
        <section className="surface consumer-card">
          <h2>Money you've requested</h2>
          {Array.isArray(requests.data) &&
            requests.data
              .filter((r) => includes(`${r.payer} ${r.note} ${r.status}`))
              .map((r) => (
                <article className="record-row" key={r.id}>
                  <div>
                    <strong>
                      {r.payer} · {currencyMoney(r.amount, r.currency)}
                    </strong>
                    <small>
                      {r.status} · Simulated request · Not proof of receipt
                    </small>
                    <p>{r.note}</p>
                  </div>
                  {r.status === "REQUESTED" && (
                    <button
                      className="secondary"
                      onClick={async () => {
                        try {
                          await post(
                            `/api/product/money-requests/${r.id}/cancel`,
                          );
                          onChanged();
                        } catch (e) {
                          setError((e as Error).message);
                        }
                      }}
                    >
                      Cancel request
                    </button>
                  )}
                </article>
              ))}
          {(!Array.isArray(requests.data) || !requests.data.length) && (
            <p>No money requests saved.</p>
          )}
        </section>
      )}
      <p className="assistant-privacy">
        Wallet-Voice records are not merchant tax invoices. Uploaded invoices remain unverified; refund records appear only when actually recorded.
      </p>
      </details>
    </div>
  );
}

export function BillsScreen({ onChanged }: { onChanged: () => void }) {
  const bills = useQuery({
    queryKey: ["tracked-bills"],
    queryFn: () => api<Bill[]>("/api/product/bills"),
  });
  const [add, setAdd] = useState(false),
    [merchant, setMerchant] = useState(""),
    [amount, setAmount] = useState(""),
    [due, setDue] = useState(""),
    [recurring, setRecurring] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <div className="consumer-stack">
      <section className="surface consumer-card">
        <h2>Plan ahead, without automatic charges.</h2>
        <p>
          Manually tracked expected expenses. This is not a utility connection,
          payment instruction or recurring debit. You can choose in-app reminder times and advance expected renewals without charging money.
        </p>
        <button
          onClick={() => {
            setError("");
            setAdd(true);
          }}
        >
          <Plus size={18} />
          Track a bill or renewal
        </button>
      </section>
      {bills.isError && (
        <p role="alert">
          Bills unavailable.{" "}
          <button onClick={() => void bills.refetch()}>Retry</button>
        </p>
      )}
      {error && !add && <p role="alert">{error}</p>}
      {Array.isArray(bills.data) &&
        bills.data
          .filter((b) => b.active)
          .map((b) => (
            <article key={b.id} className="surface record-row">
              <div>
                <strong>{b.merchant}</strong>
                <p>
                  {currencyMoney(b.amount, b.currency)} expected ·{" "}
                  {new Date(b.due_at).toLocaleString()}
                </p>
                <small>
                  {b.recurring
                    ? "Subscription renewal (manual tracking)"
                    : "Manually tracked bill"}{" "}
                  · Not paid
                </small>
              </div>
              <RenewalControls bill={b} onChanged={onChanged} />
              <button
                className="secondary"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await post(`/api/product/bills/${b.id}/archive`);
                    onChanged();
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Archive
              </button>
            </article>
          ))}
      {add && (
        <Dialog
          title="Track an expected expense"
          busy={busy}
          onClose={() => setAdd(false)}
        >
          <form
            className="form-stack"
            onSubmit={async (e) => {
              e.preventDefault();
              if (busy) return;
              setBusy(true);
              setError("");
              try {
                await post("/api/product/bills", {
                  merchant: merchant.trim(),
                  amount: minorUnits(amount),
                  due_at: new Date(due).toISOString(),
                  recurring,
                });
                setAdd(false);
                setMerchant("");
                setAmount("");
                setDue("");
                onChanged();
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label className="field">
              Biller or subscription
              <input
                required
                maxLength={120}
                value={merchant}
                onChange={(e) => setMerchant(e.target.value)}
              />
            </label>
            <label className="field">
              Expected amount (INR)
              <input
                required
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </label>
            <label className="field">
              Next due date
              <input
                required
                type="datetime-local"
                value={due}
                onChange={(e) => setDue(e.target.value)}
              />
            </label>
            <label className="check-label">
              <input
                type="checkbox"
                checked={recurring}
                onChange={(e) => setRecurring(e.target.checked)}
              />
              This is a subscription renewal (tracking only)
            </label>
            <p>
              No charge will be created. You can add an in-app reminder and
              advance an expected renewal after saving.
            </p>
            {error && <p role="alert">{error}</p>}
            <button
              disabled={busy || !merchant.trim() || !minorUnits(amount) || !due}
            >
              {busy ? "Saving…" : "Save expected expense"}
            </button>
          </form>
        </Dialog>
      )}
    </div>
  );
}

export function SettingsScreen({
  onNavigate,
  onChanged,
  onLock,
}: {
  onNavigate: (d: Destination) => void;
  onChanged: () => void;
  onLock: () => void;
}) {
  const [section, setSection] = useState("Overview");
  const [theme, setTheme] = useState(
    () => localStorage.getItem("wallet-theme") || "light",
  );
  return (
    <div className="consumer-stack">
      <div
        className="settings-sections"
        role="group"
        aria-label="Settings sections"
      >
        {[
          "Overview",
          "Security & AutoPay",
          "Notifications",
          "AI & Voice",
          "Appearance",
          "Privacy & Help",
        ].map((s) => (
          <button
            className={section === s ? "active secondary" : "secondary"}
            aria-pressed={section === s}
            key={s}
            onClick={() => setSection(s)}
          >
            {s}
          </button>
        ))}
      </div>
      {section === "Overview" && (
        <>
          <section className="surface consumer-card">
            <span className="eyebrow">YOUR ACCOUNT</span>
            <h2>Your demo wallet</h2>
            <p>
              Single-owner prototype · Simulated funds · PayPal Sandbox separate
            </p>
            <div className="settings-list">
              {[
                ["Wallet", "wallet"],
                ["Accounts & Cards", "accounts"],
                ["Statements & Receipts", "activity"],
                ["Bills & Subscriptions", "bills"],
              ].map(([label, d]) => (
                <button
                  className="secondary"
                  key={d}
                  onClick={() => onNavigate(d as Destination)}
                >
                  {label}
                  <ArrowUpRight size={18} />
                </button>
              ))}
            </div>
          </section>
          <button className="secondary" onClick={onLock}>
            Lock wallet / Sign out
          </button>
        </>
      )}
      {section === "Security & AutoPay" && (
        <Permissions onChanged={onChanged} />
      )}
      {section === "Notifications" && (
        <>
          <NotificationCategories />
          <p>
            Open the bell to review notices. Push settings do not hide saved
            checkouts.
          </p>
          <AttentionQueue preferencesOnly onReview={() => {}} />
        </>
      )}
      {section === "AI & Voice" && <VoiceSettings />}
      {section === "Appearance" && (
        <section className="surface consumer-card">
          <h2>Appearance</h2>
          <label className="field">
            Theme
            <select
              aria-label="Theme"
              value={theme}
              onChange={(e) => {
                setTheme(e.target.value);
                localStorage.setItem("wallet-theme", e.target.value);
                document.documentElement.dataset.theme = e.target.value;
              }}
            >
              {["light", "dark", "system"].map((t) => (
                <option key={t} value={t}>
                  {t[0].toUpperCase() + t.slice(1)}
                </option>
              ))}
            </select>
          </label>
          <p>
            Reduced motion follows your device settings. Interface language:
            English.
          </p>
        </section>
      )}
      {section === "Privacy & Help" && (
        <section className="surface consumer-card">
          <h2>Stay in control.</h2>
          <p>
            Use your wallet PIN only in secure approval forms. Your PayPal
            password belongs only on PayPal's buyer approval page.
          </p>
          <p>
            This single-owner demo is not a bank account. Bank/card connections,
            tax invoices, account deletion and server conversation deletion are
            not implemented. Starting a new chat does not erase server history.
          </p>
          <p>
            Manage microphone and notification permission in your browser's site
            settings. Close the assistant to stop recording.
          </p>
        </section>
      )}
    </div>
  );
}
