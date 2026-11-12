import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
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
import {SettingsNavigation} from './SettingsNavigation';
import {MoneyRequests} from './MoneyRequests';

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
        <button aria-label="Split a bill" onClick={() => window.dispatchEvent(new Event('wallet-split-open'))}>
          <Layers />
          Split a bill<small>Track demo shares, not charges</small>
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
    <section className="consumer-stack accounts-screen">
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
        sources.data.filter(s=>s.id!=='AI_WALLET').map((s) => (
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

export function ActivityScreen({ onBatch, onPayment, onChanged }: {
  onBatch: (id: string) => void; onPayment: (id: string) => void; onChanged: () => void;
}) {
  const [documents, setDocuments] = useState(false);
  return <div className="consumer-stack">
    <ActivityTimeline onBatch={onBatch} onPayment={onPayment}/>
    <button className="secondary" onClick={()=>setDocuments(!documents)} aria-expanded={documents}>Documents & Receipts</button>
    {documents && <DocumentCenter/>}
    <MoneyRequests onChanged={onChanged}/>
    <SplitHistory/>
  </div>;
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
  const detail = useRef<HTMLDivElement>(null);
  useEffect(()=>{window.scrollTo({top:0,behavior:'instant'});if(section!=='Overview')detail.current?.focus({preventScroll:true});},[section]);
  const [theme, setTheme] = useState(
    () => localStorage.getItem("wallet-theme") || "light",
  );
  return (
    <div className="consumer-stack settings-layout">
      {section !== "Overview" && <button className="secondary settings-back" onClick={() => setSection("Overview")}>Back to Settings</button>}
      <SettingsNavigation section={section} onSelect={setSection} onNavigate={onNavigate}/>
      <div className="consumer-stack settings-detail" ref={detail} tabIndex={-1}>
      {section === "Overview" && (
        <>
          <section className="surface consumer-card">
            <span className="eyebrow">YOUR ACCOUNT</span>
            <h2>Your wallet, your choices</h2>
            <p>
              Single-owner prototype · Simulated funds · PayPal Sandbox separate
            </p>
            <p>Choose a category to manage your wallet. Only capabilities actually connected in this demo are shown as available.</p>
          </section>
          <button className="secondary" onClick={onLock}>
            Lock wallet / Sign out
          </button>
        </>
      )}
      {section === "Personal Details" && <section className="surface consumer-card"><h2>Your account</h2><p>This is a single-owner demo. Personal profile editing and real bank linking are not available.</p></section>}
      {section === "Security" && <><Permissions focusedSection="security" onChanged={onChanged}/><p>Repeated incorrect PIN attempts may temporarily lock approval. Voice recognition never replaces your secure authorization.</p><button className="secondary" onClick={onLock}>Lock wallet / Sign out</button></>}
      {section === "AutoPay & Permissions" && <Permissions focusedSection="autopay" onChanged={onChanged}/>}
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
          <div className="assistant-mode-switch" role="group" aria-label="Theme">
              {["light", "dark", "system"].map((t) => (
                <button key={t} aria-pressed={theme===t} onClick={()=>{setTheme(t);localStorage.setItem("wallet-theme",t);document.documentElement.dataset.theme=t;}}>
                  {t[0].toUpperCase() + t.slice(1)}
                </button>
              ))}
          </div>
          <p>
            Reduced motion follows your device settings. Interface language:
            English.
          </p>
        </section>
      )}
      {section === "Privacy & Data" && (
        <section className="surface consumer-card">
          <h2>Stay in control.</h2>
          <p>
            Use your wallet PIN only in secure approval forms. Your PayPal
            password belongs only on PayPal's buyer approval page.
          </p>
          <p>
            This single-owner demo is not a bank account. Bank/card connections,
            tax invoices and account deletion are not implemented. Starting a new chat does not erase server history. To delete the current conversation, use the explicit Delete action in assistant details and wait for the server response. Payment records are retained.
          </p>
          <p>
            Manage microphone and notification permission in your browser's site
            settings. Close the assistant to stop recording.
          </p>
        </section>
      )}
      {section === "Help & About" && <section className="surface consumer-card"><h2>Wallet-Voice Guardian</h2><p>Review payments by voice or manually. Simulated wallet funds and PayPal Sandbox are separate. Never share your PIN or OTP with the assistant.</p><p>Microphone and notification permissions are controlled by your browser. This prototype does not move real bank funds.</p></section>}
      </div>
    </div>
  );
}
