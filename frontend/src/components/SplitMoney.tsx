import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post, minorUnits } from "../lib/api";
import { currencyMoney } from "../lib/formatting";
import { Dialog } from "./Dialog";
type Part = { name: string; amount: number; status?: string };
type Split = {
  id?: string;
  amount: number;
  snapshot_hash?: string;
  participants: Part[];
  outstanding_amount?: number;
  received_amount?: number;
  explanation?: string;
};
export function SplitMoney({
  onClose,
  onChanged,
  initialAmount = "",
  initialPeople = "me, ",
}: {
  onClose: () => void;
  onChanged: () => void;
  initialAmount?: string;
  initialPeople?: string;
}) {
  const [amount, setAmount] = useState(initialAmount),
    [people, setPeople] = useState(initialPeople),
    [note, setNote] = useState(""),
    [preview, setPreview] = useState<Split>(),
    [result, setResult] = useState<Split>(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const key = useRef(crypto.randomUUID());
  const flight = useRef(false);
  const body = () => ({
    amount: minorUnits(amount),
    participants: people.split(",").map((p) => p.trim()),
    note,
  });
  async function run(confirm = false) {
    if (flight.current) return;
    flight.current = true;
    setBusy(true);
    setError("");
    try {
      const r = await post<Split>(
        "/api/product/splits" + (confirm ? "" : "/preview"),
        {
          ...body(),
          ...(confirm
            ? {
                confirmed: true,
                snapshot_hash: preview?.snapshot_hash,
                request_key: key.current,
              }
            : {}),
        },
      );
      if (confirm) {
        setResult(r);
        onChanged();
      } else setPreview(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      flight.current = false;
      setBusy(false);
    }
  }
  return (
    <Dialog title="Split a bill" busy={busy} onClose={onClose}>
      <p>
        Split an exact INR amount with saved recipients. Confirming creates
        simulated requests, not payments or repayments.
      </p>
      {result ? (
        <>
          <h3>Requests created · Not paid</h3>
          <p>{result.explanation}</p>
          <p>
            Outstanding: {currencyMoney(result.outstanding_amount || 0, "INR")}{" "}
            · Recorded repayments:{" "}
            {currencyMoney(result.received_amount || 0, "INR")}
          </p>
          <button onClick={onClose}>Done</button>
        </>
      ) : (
        <>
          <form
            className="form-stack"
            onSubmit={(e) => {
              e.preventDefault();
              void run();
            }}
          >
            <label className="field">
              Total amount (INR)
              <input
                inputMode="decimal"
                required
                value={amount}
                onChange={(e) => {
                  setAmount(e.target.value);
                  setPreview(undefined);
                }}
              />
            </label>
            <label className="field">
              Participants, separated by commas
              <input
                required
                value={people}
                onChange={(e) => {
                  setPeople(e.target.value);
                  setPreview(undefined);
                }}
              />
            </label>
            <small>
              Include “me” once. Use exact saved names, phone numbers or emails
              for the others. Duplicate names require full handles.
            </small>
            <label className="field">
              Split note
              <input
                maxLength={500}
                value={note}
                onChange={(e) => {
                  setNote(e.target.value);
                  setPreview(undefined);
                }}
              />
            </label>
            <button disabled={busy || !minorUnits(amount)}>
              {busy ? "Preparing…" : "Preview exact split"}
            </button>
          </form>
          {preview && (
            <section className="consumer-card">
              <h3>Review each share</h3>
              {preview.participants.map((p, i) => (
                <p key={i}>
                  {p.name}: {currencyMoney(p.amount, "INR")}
                </p>
              ))}
              <p>
                Any indivisible paise are assigned in the displayed participant
                order. The shares sum exactly to your total.
              </p>
                <button className="split-confirm" disabled={busy} onClick={() => void run(true)}>
                Confirm creating requests
              </button>
            </section>
          )}
        </>
      )}
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
    </Dialog>
  );
}
export function SplitHistory() {
  const q = useQuery({
    queryKey: ["split-history"],
    queryFn: () => api<Split[]>("/api/product/splits"),
  });
  return (
    <section className="surface consumer-card">
      <h2>Shared bill requests</h2>
      {q.isError && <p role="alert">Splits could not load.</p>}
      {Array.isArray(q.data) &&
        q.data.map((s) => (
          <article className="record-row" key={s.id}>
            <div>
              <strong>
                {currencyMoney(s.amount, "INR")} split between{" "}
                {s.participants.length}
              </strong>
              <small>
                Outstanding requests{" "}
                {currencyMoney(s.outstanding_amount || 0, "INR")} ·
                Provider-confirmed repayments{" "}
                {currencyMoney(s.received_amount || 0, "INR")}
              </small>
              {s.participants.map((p, i) => (
                <p key={i}>
                  {p.name} · {currencyMoney(p.amount, "INR")} · {p.status}
                </p>
              ))}
            </div>
          </article>
        ))}
      {Array.isArray(q.data) && !q.data.length && <p>No splits created.</p>}
    </section>
  );
}
