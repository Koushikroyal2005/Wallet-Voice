import {
  ArrowDownLeft,
  ArrowUpRight,
  Clock3,
  Mic,
  MessageCircle,
  Plus,
  Wallet,
  Layers,
} from "lucide-react";
import { money } from "../lib/formatting";

export function HomeOverview({
  balance,
  loading,
  urgent,
  onSend,
  onAdd,
  onActivity,
  onChat,
  onRequest,
  onBatch,
}: {
  balance: any;
  loading: boolean;
  urgent: number | null;
  onSend: () => void;
  onAdd: () => void;
  onActivity: () => void;
  onChat: () => void;
  onRequest: () => void;
  onBatch: () => void;
}) {
  return (
    <div className="home-overview">
      <section className="home-balance surface" aria-label="Wallet overview">
        <div className="balance-caption">
          <span>
            <Wallet size={17} />
            Available balance
          </span>
          <span className="demo-pill">Simulated · INR</span>
        </div>
        <strong className="home-balance-amount">
          {balance
            ? money(balance.available_balance)
            : loading
              ? "Loading…"
              : "Unavailable"}
        </strong>
        <p>Your money, ready when you are.</p>
        <div className="money-shortcuts">
          <button onClick={onSend}>
            <ArrowUpRight size={21} />
            <span>Send</span>
          </button>
          <button onClick={onRequest}>
            <ArrowDownLeft size={21} />
            <span>Request</span>
          </button>
          <button onClick={onAdd}>
            <Plus size={21} />
            <span>Add money</span>
          </button>
          <button onClick={onBatch}>
            <Layers size={21} />
            <span>Batch Pay</span>
          </button>
        </div>
      </section>
      <div className="home-companion-column">
        <section className="attention-summary">
          <span className="round-icon">
            <Clock3 size={19} />
          </span>
          <div>
            <strong>
              {urgent === null
                ? "Checking deadlines…"
                : `${urgent} urgent ${urgent === 1 ? "request" : "requests"}`}
            </strong>
            <p>Saved checkouts stay here until you decide.</p>
            <button className="text-button" onClick={onActivity}>
              View recorded activity
            </button>
          </div>
        </section>
        <section className="assistant-invitation">
          <div>
            <span className="eyebrow">A LITTLE HELP, WHEN YOU NEED IT</span>
            <h2>Just ask your wallet.</h2>
            <p>“What needs my attention?”</p>
          </div>
          <div className="button-row">
            <button
              aria-label="Talk to your wallet"
              onClick={() =>
                window.dispatchEvent(
                  new CustomEvent("wallet-assistant-open", { detail: "voice" }),
                )
              }
            >
              <Mic size={17} />
              <span className="wide-copy">Talk to your wallet</span>
              <span className="short-copy">Talk</span>
            </button>
            <button
              aria-label="Type instead"
              className="secondary"
              onClick={onChat}
            >
              <MessageCircle size={17} />
              <span className="wide-copy">Type instead</span>
              <span className="short-copy">Type</span>
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
