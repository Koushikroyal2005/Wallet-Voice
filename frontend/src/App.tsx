import { useCallback, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  AudioLines,
  Check,
  ChevronRight,
  Home,
  Inbox,
  Plus,
  ShieldCheck,
  Sparkles,
  Train,
  Wallet,
  Zap,
} from "lucide-react";
import { api, post, operationKey, finishOperation } from "./lib/api";
import { money, currencyMoney,paymentStatus } from "./lib/formatting";
import { Dialog } from "./components/Dialog";
import { FloatingAssistant } from "./components/FloatingAssistant";
import { WalletPinDialog } from "./components/WalletPinDialog";
import { PaymentGuardian } from "./components/PaymentGuardian";
import { PaymentBatchReview } from "./components/PaymentBatchReview";
import { AttentionQueue } from "./components/AttentionQueue";
import { HomeOverview } from "./components/HomeOverview";
import {
  Drafts,
  Permissions,
  WalletView,
  MerchantDemo,
} from "./components/Workspace";

type Tab = "home" | "payments" | "wallet" | "permissions" | "merchant";
export type Payment = {
  id: string;
  merchant: string;
  amount: number;
  currency?:string;
  category: string;
  description: string;
  status: string;
  payment_source?: string;
  explicit_hold: boolean;
  verified: boolean;
  expires_at?: string;
  trace?: { urgency?: string };
};
const tabs = [
  { id: "home", label: "Home", icon: Home },
  { id: "payments", label: "Payments", icon: Inbox },
  { id: "wallet", label: "Wallet", icon: Wallet },
  { id: "permissions", label: "Auto-pay & security", icon: ShieldCheck },
] as const;
const openPayment = (p: Payment) =>
  ["PENDING", "HELD", "FAILED"].includes(p.status) &&
  (!p.expires_at || new Date(p.expires_at).getTime() > Date.now());
const due = (p: Payment) =>
  !p.expires_at
    ? "No deadline"
    : new Date(p.expires_at).getTime() <= Date.now()
      ? "Expired"
      : `Due ${new Date(p.expires_at).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}`;

export function App() {
  const query = useQueryClient();
  const session = useQuery({
    queryKey: ["session"],
    queryFn: () => api("/api/auth/session"),
    refetchInterval: 30000,
  });
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const expired = () => {
      query.setQueryData(["session"], { required: true, authenticated: false });
      query.removeQueries({ predicate: (q) => q.queryKey[0] !== "session" });
    };
    window.addEventListener("wallet-session-expired", expired);
    return () => window.removeEventListener("wallet-session-expired", expired);
  }, [query]);
  if (session.data?.authenticated) return <WalletApp />;
  return (
    <main className="unlock-page">
      <section className="unlock-story">
        <a className="brand" href="#">
          <span className="brand-mark">
            <AudioLines size={25} />
          </span>
          aiwallet.
        </a>
        <span className="eyebrow">YOUR MONEY. YOUR VOICE.</span>
        <h1>
          Less friction.
          <br />
          More control.
        </h1>
        <p>
          A personal assistant for what’s due, what can wait, and what comes
          next.
        </p>
        <div className="unlock-promise">
          <ShieldCheck />
          Your wallet stays private until you unlock it.
        </div>
      </section>
      <section className="unlock-form surface">
        <span className="round-icon">
          <Wallet size={24} />
        </span>
        <h2>Welcome to your wallet.</h2>
        <p>Enter your six-digit AI Wallet PIN to continue.</p>
        {session.isPending ? (
          <p role="status">Connecting to your wallet…</p>
        ) : session.isError ? (
          <div role="alert">
            <p>We couldn’t reach the wallet service.</p>
            <button onClick={() => session.refetch()}>Reconnect</button>
          </div>
        ) : (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (busy) return;
              setBusy(true);
              setError("");
              try {
                await post("/api/auth/login", { pin });
                setPin("");
                await session.refetch();
              } catch (cause) {
                setError((cause as Error).message);
                setPin("");
              } finally {
                setBusy(false);
              }
            }}
          >
            <label className="field">
              Wallet PIN
              <input
                type="password"
                inputMode="numeric"
                autoComplete="current-password"
                maxLength={6}
                value={pin}
                onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
                autoFocus
              />
            </label>
            {error && (
              <p className="error-banner" role="alert">
                {error}
              </p>
            )}
            <button disabled={busy || pin.length !== 6}>
              {busy ? "Unlocking…" : "Unlock wallet"}
              <ArrowUpRight size={18} />
            </button>
          </form>
        )}
        <small>
          Single-owner demo · simulated funds
          <br />
          Use your wallet PIN, never your bank or PayPal password.
        </small>
      </section>
    </main>
  );
}

function WalletApp() {
  const query = useQueryClient();
  const [tab, setTab] = useState<Tab>("home");
  useEffect(() => { window.scrollTo({ top: 0, behavior: 'instant' }); }, [tab]);
  const [assistant, setAssistant] = useState(false);
  const [sendRequested,setSendRequested] = useState(false);
  const [filter, setFilter] = useState("Open");
  const [search, setSearch] = useState("");
  const [selectedPayments,setSelectedPayments] = useState<string[]>([]);
  const [review, setReview] = useState<{id:string;merchant?:string;payment_source?:string}>();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [failure, setFailure] = useState("");
  const [batch, setBatch] = useState<any>();
  const [batchResults, setBatchResults] = useState<any[]>();
  const [exactBatch, setExactBatch] = useState<string>();
  const [funding, setFunding] = useState<{
    action: "TOPUP" | "WITHDRAWAL";
    amount: number;
  }>();
  const payments = useQuery({
    queryKey: ["payments"],
    queryFn: () => api<Payment[]>("/api/payments"),
  });
  const balance = useQuery({
    queryKey: ["wallet"],
    queryFn: () => api("/api/wallet"),
  });
  const refresh = useCallback(() => {
    void query.invalidateQueries();
  }, [query]);
  useEffect(() => {
    const events = new EventSource("/api/events/stream");
    events.onmessage = refresh;
    return () => events.close();
  }, [refresh]);
  const items = payments.data || [];
  useEffect(()=>{setSelectedPayments(ids=>{const live=ids.filter(id=>items.some(p=>p.id===id&&openPayment(p)));return live.length===ids.length?ids:live;});},[payments.data]);
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('review');
    const payment = items.find(p => p.id === id);
    if (payment) { setReview(payment); window.history.replaceState({}, '', window.location.pathname); }
  }, [payments.data]);
  const pending = items.filter(openPayment);
  const attentionQuery = useQuery({queryKey: ['attention'], queryFn: () => api('/api/notifications')});
  const attention: Payment[] = (attentionQuery.data?.items || []).flatMap((entry: any) => {
    const payment = items.find(p => p.id === entry.payment_id);
    return payment && openPayment(payment) && !entry.explicit_hold && entry.stage !== 'EXPIRED'
      ? [{...payment, trace: {...payment.trace, urgency: entry.stage}}] : [];
  });
  const reviewPayment = (payment: Payment) => {
    setReview(payment);
    setFailure("");
  };
  async function action(run: () => Promise<unknown>, message: string) {
    if (busy) return;
    setBusy(true);
    setFailure("");
    try {
      await run();
      refresh();
      setNotice(message);
    } catch (error) {
      setFailure((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function paymentRows(rows: Payment[]) {
    return rows.length ? (
      rows.map((p) => (
        <article className={`payment-row ${tab==='payments'&&openPayment(p)?'selectable':''}`} key={p.id}>
          {tab==='payments'&&openPayment(p)&&<label className="payment-select"><input type="checkbox" aria-label={`Select ${p.merchant}`} checked={selectedPayments.includes(p.id)} onChange={e=>setSelectedPayments(ids=>e.target.checked?[...ids,p.id]:ids.filter(id=>id!==p.id))}/></label>}
          <span
            className={`merchant-avatar ${p.category === "travel" ? "peach" : "lavender"}`}
          >
            {p.category === "travel" ? (
              <Train size={21} />
            ) : (
              p.merchant.substring(0, 2).toUpperCase()
            )}
          </span>
          <div className="payment-name">
            <strong>{p.merchant}</strong>
            <span>{p.description}</span>
          </div>
          <div className="payment-deadline">
            <span className={p.trace?.urgency === "URGENT" ? "urgent" : ""}>
              {p.explicit_hold ? "On hold · waiting for you" : due(p)}
            </span>
            <small className={`payment-status status-${p.status.toLowerCase()}`}>
              {paymentStatus(p.status)}
            </small>
            <small>{p.verified ? 'Recognized in this app' : 'Check recipient independently'}</small>
          </div>
          <strong className="payment-amount">{currencyMoney(p.amount,p.currency)}</strong>
          <button
            className="row-action"
            onClick={() => reviewPayment(p)}
            aria-label={`Review ${p.merchant} payment`}
          >
            {openPayment(p) ? "Review" : "Details"}
            <ChevronRight size={16} />
          </button>
        </article>
      ))
    ) : (
      <div className="empty-state">
        <Check size={24} />
        <h3>{search ? 'No matching payments' : filter === 'Held' ? 'Nothing on hold' : filter === 'History' ? 'No past payments yet' : "You're all caught up"}</h3>
        <p>{search ? 'Try a business name or a word from the request.' : filter === 'Held' ? 'Requests you hold will wait here until you release them.' : 'New payment requests will appear here.'}</p>
      </div>
    );
  }
  const visible = items.filter(
    (p) =>
      (filter === "Held"
        ? p.explicit_hold && openPayment(p)
        : filter === "History"
          ? !openPayment(p)
          : openPayment(p) && !p.explicit_hold) &&
      `${p.merchant} ${p.description}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(event) => {
            event.preventDefault();
            setTab("home");
          }}
        >
          <span className="brand-mark">
            <AudioLines size={25} />
          </span>
          <span>
            aiwallet<span className="brand-dot">.</span>
            <small className="brand-subtitle">GUARDIAN</small>
          </span>
        </a>
        <span className="nav-caption">YOUR SPACE</span>
        <nav aria-label="Main navigation">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              aria-label={label}
              className={`nav-item ${tab === id ? "active" : ""}`}
              aria-current={tab === id ? "page" : undefined}
              onClick={() => setTab(id)}
            >
              <Icon size={20} />
              <span>{label}</span>
              {id === "payments" && pending.length > 0 && (
                <b>{pending.length}</b>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="mini-assistant">
            <Sparkles size={21} />
            <strong>A little less to think about.</strong>
            <p>Your payments, with a helping hand.</p>
            <button onClick={() => setAssistant(true)}>
              Ask your wallet <ArrowUpRight size={16} />
            </button>
          </div>
          <button className="merchant-link" onClick={() => setTab("merchant")}>
            <Train size={16} /> Merchant demo <ArrowUpRight size={14} />
          </button>
          <div className="profile">
            <span>Y</span>
            <div>
              <strong>Your demo wallet</strong>
              <small>Sandbox workspace</small>
            </div>
            <span className="online-dot" />
          </div>
        </div>
      </aside>
      <main className="content">
        <header className="topbar">
          <span>
            Personal workspace <span className="divider">/</span>{" "}
            {tab === "merchant"
              ? "Merchant demo"
              : tabs.find((t) => t.id === tab)?.label}
          </span>
          <span className="environment">
            <span className="online-dot" />
            Demo funds · PayPal Sandbox
            <button
              className="text-button"
              onClick={async () => {
                try {
                  await post("/api/auth/logout");
                  query.clear();
                } catch {
                  setFailure("Could not lock the wallet. Please retry.");
                }
              }}
            >
              Lock wallet
            </button>
          </span>
        </header>
        <div className="page-heading">
          <div>
            <span className="eyebrow">
              {tab === "home"
                ? "YOUR DAY, A LITTLE LIGHTER"
                : "YOUR WALLET, YOUR RULES"}
            </span>
            <h1>
              {
                {
                  home: "Your wallet.",
                  payments: "Payments.",
                  wallet: "Your money.",
                  permissions: "Your controls.",
                  merchant: "Merchant playground.",
                }[tab]
              }
            </h1>
            <p>
              {
                {
                  home: "A quiet place for the payments you haven't finished.",
                  payments:
                    "Review what’s due, save a draft, or leave it for later.",
                  wallet:
                    "Add money, withdraw, and see every completed movement.",
                  permissions:
                    "Choose who can charge your wallet, and how much.",
                  merchant:
                    "A sample ticket checkout using your saved wallet permission.",
                }[tab]
              }
            </p>
          </div>
          {tab !== "home" && (
            <button className="secondary" onClick={() => setAssistant(true)}>
              <Sparkles size={17} /> Ask AI
            </button>
          )}
        </div>
        {(payments.isError || balance.isError) && (
          <div className="error-banner" role="alert">
            We couldn’t reach your wallet.{" "}
            <button onClick={refresh}>Try again</button>
          </div>
        )}
        {notice && (
          <div className="notice" role="status">
            <Check size={18} />
            {notice}
            <button className="text-button" onClick={() => setNotice("")}>
              Dismiss
            </button>
          </div>
        )}
        {failure && !review && (
          <div className="error-banner" role="alert">
            {failure}
          </div>
        )}
        {tab === "home" && <HomeOverview balance={balance.data} loading={balance.isPending}
          urgent={attentionQuery.isPending||attentionQuery.isError?null:attention.filter(p=>p.trace?.urgency==='URGENT').length}
          onSend={()=>{setSendRequested(true);setTab('payments');}}
          onAdd={()=>{setTab('wallet');window.setTimeout(()=>window.dispatchEvent(new Event('wallet-add-money')),0);}}
          onActivity={()=>setTab('wallet')} onChat={()=>setAssistant(true)}/>}
        {tab === "payments" && (
          <>
            <div className="toolbar">
              <div className="filter-tabs">
                {["Open", "Held", "History"].map((value) => (
                  <button
                    key={value}
                    className={filter === value ? "active" : ""}
                    aria-pressed={filter === value}
                    onClick={() => setFilter(value)}
                  >
                    {value}
                  </button>
                ))}
              </div>
              <input
                aria-label="Search payments"
                placeholder="Search payments…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <button
                className="secondary"
                disabled={busy}
                onClick={() =>
                  action(
                    async () => {
                      if(selectedPayments.length){const result=await post('/api/payment-batches',{payment_ids:selectedPayments});setExactBatch(result.id);}
                      else setBatch(await post("/api/payments/batch/evaluate"));
                    },
                    "Payment preview ready",
                  )
                }
              >
                <Zap size={16} />
                {selectedPayments.length?`Review ${selectedPayments.length} selected`:'Review batch'}
              </button>
            </div>
            <div className="payment-list">{paymentRows(visible)}</div>
            <Drafts requested={sendRequested} onRequestHandled={()=>setSendRequested(false)} onChanged={refresh} />
            <details className="demo-tools">
              <summary>Sample payment requests</summary>
              <div className="button-row">
                {["railway", "movie", "electronics"].map((type) => (
                  <button
                    key={type}
                    className="secondary"
                    disabled={busy}
                    onClick={() =>
                      action(
                        () => post("/api/merchant/payment-requests", { type }),
                        "Sample payment added",
                      )
                    }
                  >
                    Create {type} request
                  </button>
                ))}
              </div>
            </details>
          </>
        )}
        {tab === "wallet" && (
          <WalletView
            balance={balance.data}
            onFund={(action, amount) => setFunding({ action, amount })}
          />
        )}
        {tab === "permissions" && <Permissions onChanged={refresh} />}
        {tab === "merchant" && <MerchantDemo onChanged={refresh} />}
        {(tab === 'home' || tab === 'payments') && <AttentionQueue onReview={id => { const payment = items.find(p => p.id === id); setReview(payment||{id});setFailure(''); }}/ >}
      </main>
      <FloatingAssistant requested={assistant} onClose={() => setAssistant(false)} onConfirmed={refresh} />
      {review && (
        <Dialog
          title={review.merchant||'Payment review'}
          variant="drawer"
          busy={busy}
          onClose={() => setReview(undefined)}
        >
          <PaymentGuardian paymentId={review.id} initialSource={review.payment_source} onChanged={refresh} onCancel={() => setReview(undefined)} />
        </Dialog>
      )}
      {exactBatch && <Dialog title="Exact wallet payment review" onClose={() => setExactBatch(undefined)} variant="drawer"><PaymentBatchReview batchId={exactBatch} onChanged={refresh} onCancel={() => setExactBatch(undefined)}/></Dialog>}
      {funding && (
        <WalletPinDialog
          action={funding.action}
          amount={funding.amount}
          title={
            funding.action === "TOPUP"
              ? "Add money to your wallet"
              : "Withdraw to your demo bank"
          }
          onClose={() => setFunding(undefined)}
          onApproved={async (token) => {
            const scope = `${funding.action}:${funding.amount}`;
            await post(
              funding.action === "TOPUP"
                ? "/api/bank/topups"
                : "/api/bank/withdrawals",
              {
                amount: funding.amount,
                approval_token: token,
                idempotency_key: operationKey(scope),
              },
            );
            finishOperation(scope);
            refresh();
            setNotice(
              `${money(funding.amount)} ${funding.action === "TOPUP" ? "added to your wallet" : "withdrawn to your demo bank"}.`,
            );
            setFunding(undefined);
          }}
        />
      )}
      {batch && (
        <Dialog
          title="Review your payment batch"
          busy={busy}
          onClose={() => setBatch(undefined)}
        >
          <p>
            Only the requests listed here will be submitted. Limits are checked
            again before payment.
          </p>
          <div className="review-amount">{money(batch.required_total)}</div>
          <div className="batch-items">
            {batch.items.map((item: any) => (
              <div key={item.id}>
                <span>
                  <strong>{item.merchant}</strong>
                  <small>
                    {item.decision === "ELIGIBLE"
                      ? "Ready to pay"
                      : item.reason_codes
                          .join(", ")
                          .toLowerCase()
                          .replaceAll("_", " ")}
                  </small>
                </span>
                <b>{money(item.amount)}</b>
              </div>
            ))}
          </div>
          <button
            disabled={busy || !batch.eligible_count}
            onClick={() =>
              action(async () => {
                const response = await post("/api/payment-batches", {
                  payment_ids: batch.items
                    .filter((item: any) => item.decision === "ELIGIBLE")
                    .map((item: any) => item.id),
                  idempotency_key: operationKey("batch"),
                });
                setExactBatch(response.id);
                setBatch(undefined);
                finishOperation("batch");
              }, "Ready for review")
            }
          >
            Confirm {batch.eligible_count} payments
          </button>
          {failure && <p role="alert">{failure}</p>}
        </Dialog>
      )}
      {batchResults && (
        <Dialog
          title="Batch results"
          onClose={() => setBatchResults(undefined)}
        >
          <div className="batch-items">
            {batchResults.map((item) => (
              <div key={item.id}>
                <strong>{item.status.toLowerCase()}</strong>
                <span>{item.provider_reference || item.failure_reason}</span>
              </div>
            ))}
          </div>
          {!batchResults.length && (
            <p>
              These payments were already handled or are no longer eligible.
            </p>
          )}
        </Dialog>
      )}
    </div>
  );
}
