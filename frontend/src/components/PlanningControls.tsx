import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, post } from "../lib/api";
import { currencyMoney } from "../lib/formatting";
type Preferences = {
  payment_alerts: boolean;
  ai_alerts: boolean;
  planning_alerts: boolean;
  lock_screen_private: boolean;
};
export function NotificationCategories() {
  const q = useQuery({
    queryKey: ["product-preferences"],
    queryFn: () => api<Preferences>("/api/product/preferences"),
  });
  const qc = useQueryClient();
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <section className="surface consumer-card">
      <h3>Notification categories & privacy</h3>
      {q.isError && (
        <p role="alert">
          Preferences unavailable.{" "}
          <button onClick={() => void q.refetch()}>Retry</button>
        </p>
      )}
      {q.data &&
        (
          [
            "payment_alerts",
            "ai_alerts",
            "planning_alerts",
            "lock_screen_private",
          ] as const
        ).map((key) => (
          <label className="voice-setting" key={key}>
            <span>
              {
                {
                  payment_alerts: "Payment status updates",
                  ai_alerts: "Payment-planning insights",
                  planning_alerts: "Saved bill and imported-checkout reminders",
                  lock_screen_private:
                    "Keep push notices private on the lock screen",
                }[key]
              }
            </span>
            <input
              type="checkbox"
              disabled={busy}
              checked={q.data[key]}
              onChange={async (e) => {
                setBusy(true);
                setError("");
                try {
                  await api("/api/product/preferences", {
                    method: "PATCH",
                    body: JSON.stringify({
                      ...q.data,
                      [key]: e.target.checked,
                    }),
                  });
                  await qc.invalidateQueries();
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            />
          </label>
        ))}
      <p>
        Security-critical notices always remain in-app. Turning off push does
        not hide saved checkouts. Planning reminders are in-app only; background
        push currently covers connected saved payment deadlines.
      </p>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
export function RenewalControls({
  bill,
  onChanged,
}: {
  bill: {
    id: string;
    due_at: string;
    recurring: boolean;
    remind_at?: string;
    cadence?: string;
  };
  onChanged: () => void;
}) {
  const [time, setTime] = useState(""),
    [cadence, setCadence] = useState(bill.cadence || "MONTHLY"),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  async function run(action: string, body: unknown) {
    if (busy) return;
    setBusy(true);
    setMessage("");
    try {
      await post(`/api/product/bills/${bill.id}/${action}`, body);
      onChanged();
      setMessage(
        action === "advance"
          ? "Next tracked renewal updated. No charge was recorded."
          : "In-app reminder saved.",
      );
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="renewal-controls">
      <summary>Reminder & renewal planning</summary>
      {bill.remind_at && (
        <p>In-app reminder: {new Date(bill.remind_at).toLocaleString()}</p>
      )}
      <label className="field">
        In-app reminder time
        <input
          type="datetime-local"
          value={time}
          onChange={(e) => setTime(e.target.value)}
        />
      </label>
      <button
        className="secondary"
        disabled={busy || !time}
        onClick={() =>
          void run("reminder", { remind_at: new Date(time).toISOString() })
        }
      >
        Save bill reminder
      </button>
      {bill.recurring && (
        <>
          <label className="field">
            Tracked renewal interval
            <select
              value={cadence}
              onChange={(e) => setCadence(e.target.value)}
            >
              {["WEEKLY", "MONTHLY", "YEARLY"].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <button
            className="secondary"
            disabled={busy}
            onClick={() =>
              void run("advance", { expected_due: bill.due_at, cadence })
            }
          >
            Advance expected renewal
          </button>
          <p>
            This changes the next expected date only. It does not pay or claim
            that the prior bill was paid.
          </p>
        </>
      )}
      {message && <p role="status">{message}</p>}
    </details>
  );
}
type Insights = {
  urgent_ids: string[];
  expected_30_day_bills_by_currency: Record<string, number>;
  wallet_shortfall: number;
  wallet_currency: string;
  possible_duplicate_ids: string[][];
};
export function BillReminderCard({
  id,
  onChanged,
  onClose,
}: {
  id: string;
  onChanged: () => void;
  onClose: () => void;
}) {
  const q = useQuery({
    queryKey: ["tracked-bills"],
    queryFn: () =>
      api<
        {
          id: string;
          merchant: string;
          amount: number;
          currency: string;
          due_at: string;
          recurring: boolean;
          remind_at?: string;
          cadence?: string;
        }[]
      >("/api/product/bills"),
  });
  const bill = Array.isArray(q.data)
    ? q.data.find((b) => b.id === id)
    : undefined;
  return (
    <section className="consumer-card">
      <h3>Review bill reminder</h3>
      {bill ? (
        <>
          <p>
            {bill.merchant} · {currencyMoney(bill.amount, bill.currency)}{" "}
            expected · Due {new Date(bill.due_at).toLocaleString()}
          </p>
          <RenewalControls bill={bill} onChanged={onChanged} />
        </>
      ) : (
        <p>
          Loading saved bill details. If unavailable, open Bills and choose the
          exact bill.
        </p>
      )}
      <button className="secondary" onClick={onClose}>
        Close reminder review
      </button>
    </section>
  );
}
export function PlanningInsight({
  onReview,
  onBills,
}: {
  onReview: () => void;
  onBills: () => void;
}) {
  const q = useQuery({
    queryKey: ["planning-insights"],
    queryFn: () => api<Insights>("/api/product/insights"),
  });
  if (!q.data?.urgent_ids) return null;
  return (
    <section className="surface consumer-card planning-insight">
      <span className="eyebrow">
        BASED ON YOUR SAVED DETAILS · NOT A MODEL PREDICTION
      </span>
      <h3>
        {q.data.urgent_ids.length
          ? `${q.data.urgent_ids.length} ${q.data.urgent_ids.length===1?'payment is':'payments are'} expiring soon`
          : "Your next steps, in one place."}
      </h3>
      {q.data.urgent_ids.length > 1 && (
        <button className="secondary" onClick={onReview}>
          Review suggested batch
        </button>
      )}
      {q.data.wallet_shortfall > 0 && (
        <p>
          Saved requests exceed available wallet funds by{" "}
          {currencyMoney(q.data.wallet_shortfall, q.data.wallet_currency)}.
          Limits and individual eligibility still apply.
        </p>
      )}
      {Object.entries(q.data.expected_30_day_bills_by_currency).map(
        ([c, v]) => (
          <p key={c}>
            Expected bills in the next 30 days: {currencyMoney(v, c)}. These are
            estimates, not confirmed charges.
          </p>
        ),
      )}
      {q.data.possible_duplicate_ids.length > 0 && (
        <p>
          {q.data.possible_duplicate_ids.length} possible duplicate request
          pair(s). Review before paying; duplicates are not confirmed.
        </p>
      )}
      <button className="text-button" onClick={onBills}>
        View upcoming bills
      </button>
    </section>
  );
}
