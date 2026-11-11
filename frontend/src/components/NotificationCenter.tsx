import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post } from "../lib/api";
import { Dialog } from "./Dialog";
export type Notice = {
  id: string;
  title: string;
  message: string;
  section: string;
  created_at?: string;
  read: boolean;
  payment_id?: string;
  batch_id?: string;
  mode?: string;
  destination?: string;
};
export function useNotifications() {
  return useQuery({
    queryKey: ["notification-center"],
    queryFn: () =>
      api<{ items: Notice[]; unread: number }>("/api/product/notifications"),
  });
}
export function NotificationCenter({
  onClose,
  onPayment,
  onBatch,
}: {
  onClose: () => void;
  onPayment: (id: string) => void;
  onBatch: (id: string) => void;
}) {
  const feed = useNotifications();
  const [tab, setTab] = useState("All"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const rows = Array.isArray(feed.data?.items) ? feed.data.items : [];
  async function update(ids: string[], action: "READ" | "DISMISS") {
    if (busy || !ids.length) return;
    setBusy(true);
    setError("");
    try {
      await post("/api/product/notifications/state", { ids, action });
      await feed.refetch();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title="Notifications"
      variant="popover"
      busy={busy}
      onClose={onClose}
    >
      <div
        className="notification-tabs"
        role="group"
        aria-label="Notification sections"
      >
        {["All", "Needs Review", "AI Updates"].map((t) => (
          <button
            key={t}
            className={tab === t ? "active secondary" : "secondary"}
            aria-pressed={tab === t}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      <button
        className="text-button"
        disabled={busy || !rows.some((r) => !r.read)}
        onClick={() =>
          void update(
            rows.filter((r) => !r.read).map((r) => r.id),
            "READ",
          )
        }
      >
        Mark all read
      </button>
      {feed.isPending && <p role="status">Loading notifications…</p>}
      {feed.isError && (
        <p role="alert">
          Notifications unavailable.{" "}
          <button onClick={() => void feed.refetch()}>Retry</button>
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      <div className="notification-list">
        {rows
          .filter((r) => tab === "All" || r.section === tab)
          .map((r) => (
            <article
              key={r.id}
              className={`notification-row ${r.read ? "" : "unread"}`}
            >
              <strong>
                {r.title}
                {!r.read && <span className="unread-dot" aria-label="Unread" />}
              </strong>
              <p>{r.message}</p>
              <small>
                {r.created_at
                  ? new Date(r.created_at).toLocaleString()
                  : "Current saved payment"}
                {r.mode && ` · ${r.mode}`}
              </small>
              <div className="button-row">
                {(r.payment_id || r.batch_id || r.destination) && (
                  <button
                    className="secondary"
                    onClick={() => {
                      void update([r.id], "READ");
                      if (r.payment_id) onPayment(r.payment_id);
                      else if (r.batch_id) onBatch(r.batch_id);
                      else if (r.destination)
                        window.dispatchEvent(
                          new CustomEvent("wallet-navigate", {
                            detail: r.destination,
                          }),
                        );
                      onClose();
                    }}
                  >
                    View details
                  </button>
                )}
                {!r.read && (
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() => void update([r.id], "READ")}
                  >
                    Mark read
                  </button>
                )}
                <button
                  className="text-button"
                  disabled={busy}
                  onClick={() => void update([r.id], "DISMISS")}
                >
                  Dismiss notice
                </button>
              </div>
            </article>
          ))}
      </div>
      {!feed.isPending &&
        !feed.isError &&
        !rows.some((r) => tab === "All" || r.section === tab) && (
          <p>No notices in this section.</p>
        )}
      <small>
        Dismissing a notice does not cancel a payment or hide it from Inbox.
      </small>
    </Dialog>
  );
}
