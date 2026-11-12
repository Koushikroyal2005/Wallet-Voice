import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post, minorUnits } from "../lib/api";
import { currencyMoney } from "../lib/formatting";
import { Dialog } from "./Dialog";
export type Intake = {
  id: string;
  merchant: string;
  description: string;
  amount: number;
  currency: string;
  deadline?: string;
  source_type: string;
  source_url?: string;
  status: string;
  remind_at?: string;
  can_pay: false;
  explanation: string;
};
export function IntakeFlow({
  mode = "manual",
  initialURL = "",
  onClose,
  onChanged,
}: {
  mode?: "manual" | "link" | "qr" | "share";
  initialURL?: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [url, setURL] = useState(initialURL),
    [merchant, setMerchant] = useState(""),
    [amount, setAmount] = useState(""),
    [currency, setCurrency] = useState("INR"),
    [description, setDescription] = useState(""),
    [deadline, setDeadline] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [saved, setSaved] = useState<Intake>();
  const video = useRef<HTMLVideoElement>(null),
    stream = useRef<MediaStream>(),
    timer = useRef<number>(),
    flight = useRef(false),
    cameraStarting = useRef(false),
    mounted = useRef(true);
  const [scanning, setScanning] = useState(false);
  const stop = () => {
    clearInterval(timer.current);
    timer.current = undefined;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = undefined;
    setScanning(false);
  };
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      clearInterval(timer.current);
      stream.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);
  async function scan() {
    if (cameraStarting.current || stream.current) return;
    type Detector = {
      detect: (v: HTMLVideoElement) => Promise<{ rawValue: string }[]>;
    };
    const Constructor = (
      window as unknown as {
        BarcodeDetector?: new (options: { formats: string[] }) => Detector;
      }
    ).BarcodeDetector;
    if (!Constructor) {
      setError(
        "QR scanning is unavailable in this browser. Paste the HTTPS payment link instead.",
      );
      return;
    }
    cameraStarting.current = true;
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      });
      if (!mounted.current) {
        media.getTracks().forEach((t) => t.stop());
        return;
      }
      stream.current = media;
      setScanning(true);
      if (video.current) {
        video.current.srcObject = media;
        await video.current.play();
      }
      const detector = new Constructor({ formats: ["qr_code"] });
      timer.current = window.setInterval(async () => {
        if (flight.current || !video.current) return;
        flight.current = true;
        try {
          const rows = await detector.detect(video.current);
          if (!mounted.current || !stream.current) return;
          if (rows[0]) {
            const parsed = new URL(rows[0].rawValue);
            if (
              parsed.protocol !== "https:" ||
              parsed.username ||
              parsed.password
            )
              throw Error(
                "Only HTTPS checkout links can be saved. This QR is not a verified payee.",
              );
            setURL(parsed.href);
            stop();
          }
        } catch (e) {
          setError((e as Error).message);
        } finally {
          flight.current = false;
        }
      }, 500);
    } catch {
      stop();
      setError(
        "Camera access was not available. Allow camera permission or paste the link.",
      );
    } finally {
      cameraStarting.current = false;
    }
  }
  return (
    <Dialog
      className="intake-dialog"
      title={mode === "qr" ? "Scan or paste a payment link" : "Save a checkout"}
      busy={busy}
      onClose={() => {
        stop();
        onClose();
      }}
    >
      <p>
        Save unfinished payment details for review. Importing never verifies a
        merchant or authorizes payment.
      </p>
      {mode === "qr" && !saved && (
        <>
          <button
            className="secondary"
            onClick={() => void scan()}
            disabled={scanning}
          >
            Start camera
          </button>
          <video
            ref={video}
            muted
            playsInline
            hidden={!scanning}
            className="qr-preview"
          />
          {scanning && (
            <button className="secondary" onClick={stop}>
              Stop camera
            </button>
          )}
        </>
      )}
      {saved ? (
        <>
          <h3>Saved · Unverified</h3>
          <p>
            {saved.merchant} · {currencyMoney(saved.amount, saved.currency)}
          </p>
          <p>{saved.explanation}</p>
          <button onClick={onClose}>Done</button>
        </>
      ) : (
        <form
          className="form-stack intake-form"
          onSubmit={async (e) => {
            e.preventDefault();
            if (busy) return;
            setBusy(true);
            setError("");
            try {
              setSaved(
                await post<Intake>("/api/product/intakes", {
                  source_type: url
                    ? mode === "manual"
                      ? "LINK"
                      : mode.toUpperCase()
                    : "MANUAL",
                  source_url: url || null,
                  merchant: merchant.trim(),
                  amount: minorUnits(amount),
                  currency,
                  description,
                  deadline: deadline ? new Date(deadline).toISOString() : null,
                }),
              );
              stop();
              onChanged();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label className="field">
            HTTPS checkout link (optional for manual entry)
            <input
              type="url"
              maxLength={2048}
              placeholder="https://merchant.example/checkout"
              value={url}
              onChange={(e) => setURL(e.target.value)}
            />
          </label>
          <small>
            We do not visit or extract details from this URL. Check its domain
            independently.
          </small>
          <label className="field">
            Claimed merchant
            <input
              required
              maxLength={120}
              value={merchant}
              onChange={(e) => setMerchant(e.target.value)}
            />
          </label>
          <label className="field">
            Amount
            <input
              inputMode="decimal"
              required
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </label>
          <label className="field">
            Currency
            <input
              required
              maxLength={3}
              pattern="[A-Z]{3}"
              value={currency}
              onChange={(e) => setCurrency(e.target.value.toUpperCase())}
            />
          </label>
          <label className="field">
            Description
            <input
              maxLength={500}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>
          <label className="field">
            Deadline (optional)
            <input
              type="datetime-local"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
            />
          </label>
          <p>
            Enter the amount/currency shown by the merchant. No conversion or
            charge is performed.
          </p>
          <button
            disabled={
              busy ||
              !merchant.trim() ||
              !minorUnits(amount) ||
              currency.length !== 3 ||
              (mode !== "manual" && !url)
            }
          >
            {busy ? "Saving…" : "Save unverified checkout"}
          </button>
        </form>
      )}
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
    </Dialog>
  );
}

export function ImportedCheckouts({ onChanged }: { onChanged: () => void }) {
  const query = useQuery({
    queryKey: ["imported-checkouts"],
    queryFn: () => api<Intake[]>("/api/product/intakes"),
  });
  const [selected, setSelected] = useState<Intake>(),
    [reminder, setReminder] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [leaving, setLeaving] = useState(false);
  async function update(row: Intake, action: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await post<Intake>(
        `/api/product/intakes/${row.id}/state`,
        {
          action,
          ...(action === "REMIND"
            ? { remind_at: new Date(reminder).toISOString() }
            : {}),
        },
      );
      setSelected(result);
      await query.refetch();
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="surface consumer-card">
      <h2>Imported & manually saved</h2>
      <p>
        Unverified details, separate from connected merchant payments. They
        cannot be selected for wallet execution.
      </p>
      {query.isError && (
        <p role="alert">
          Imports unavailable.{" "}
          <button onClick={() => void query.refetch()}>Retry</button>
        </p>
      )}
      {Array.isArray(query.data) &&
        query.data.map((r) => (
          <article className="record-row" key={r.id}>
            <div>
              <strong>
                {r.merchant} · {currencyMoney(r.amount, r.currency)}
              </strong>
              <small>
                {r.status} · Imported, unverified · {r.source_type}
              </small>
              <p>{r.description}</p>
            </div>
            <button
              className="secondary"
              onClick={() => {
                setSelected(r);
                setError("");
                setLeaving(false);
              }}
            >
              Review saved details
            </button>
          </article>
        ))}
      {Array.isArray(query.data) && !query.data.length && (
        <p>No imported checkouts saved.</p>
      )}
      {selected && (
        <Dialog
          title="Unverified checkout details"
          busy={busy}
          onClose={() => setSelected(undefined)}
        >
          <h3>{selected.merchant}</h3>
          <strong className="review-amount">
            {currencyMoney(selected.amount, selected.currency)}
          </strong>
          <p>{selected.description}</p>
          <p>{selected.explanation}</p>
          <p>
            Deadline:{" "}
            {selected.deadline
              ? new Date(selected.deadline).toLocaleString()
              : "Not supplied"}
          </p>
          <p className="safe-url">
            Source: {selected.source_url || "Manually entered"}
          </p>
          {selected.remind_at && (
            <p>
              In-app reminder: {new Date(selected.remind_at).toLocaleString()}
            </p>
          )}
          <div className="button-row">
            {selected.status === "SAVED" ? (
              <>
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => void update(selected, "HOLD")}
                >
                  Hold imported checkout
                </button>
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => void update(selected, "DISMISS")}
                >
                  Dismiss imported checkout
                </button>
              </>
            ) : (
              selected.status !== "EXPIRED" && (
                <button
                  disabled={busy}
                  onClick={() => void update(selected, "RESTORE")}
                >
                  Restore imported checkout
                </button>
              )
            )}
          </div>
          {selected.status === "SAVED" && (
            <>
              <label className="field">
                In-app reminder time
                <input
                  type="datetime-local"
                  value={reminder}
                  onChange={(e) => setReminder(e.target.value)}
                />
              </label>
              <button
                disabled={busy || !reminder}
                onClick={() => void update(selected, "REMIND")}
              >
                Set in-app reminder
              </button>
            </>
          )}
          {selected.source_url && (
            <>
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={leaving}
                  onChange={(e) => setLeaving(e.target.checked)}
                />
                I checked the URL. Leaving Wallet-Voice is not a verified
                payment.
              </label>
              {leaving && (
                <a
                  className="document-link"
                  href={selected.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Open original checkout externally
                </a>
              )}
            </>
          )}
          {error && <p role="alert">{error}</p>}
        </Dialog>
      )}
    </section>
  );
}
