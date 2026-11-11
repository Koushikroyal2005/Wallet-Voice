import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { currencyMoney } from "../lib/formatting";
import { Dialog } from "./Dialog";
type Document = {
  id: string;
  kind: string;
  title: string;
  status: string;
  created_at: string;
  reference: string;
  trust: string;
  download_url: string;
  amount?: number;
  currency?: string;
  payment_id?: string;
};
const documentLabels: Record<string, string> = {
  ALL: "All documents",
  PAYMENT: "Payment records",
  BATCH: "Batch statements",
  UPLOAD: "Uploaded documents",
  REFUND: "Refund records",
  UNVERIFIED: "Not verified",
  RECORDED_ATTEMPT_NOT_NECESSARILY_SETTLED:
    "Recorded payment attempt — check its status before treating it as paid",
  SIMULATED_WALLET: "Simulated wallet funds, not a bank payment",
  USER_UPLOADED_NOT_PAYMENT_PROOF:
    "Uploaded by you — not verified and not proof of payment",
};
function readable(value: string) {
  return documentLabels[value] ?? value.toLowerCase().replaceAll("_", " ");
}
export function DocumentCenter() {
  const [search, setSearch] = useState(""),
    [kind, setKind] = useState("ALL"),
    [upload, setUpload] = useState(false),
    [title, setTitle] = useState(""),
    [file, setFile] = useState<File>(),
    [selected, setSelected] = useState<Document>(),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const q = useQuery({
    queryKey: ["document-catalog", search, kind],
    queryFn: () =>
      api<Document[]>(
        `/api/product/documents?q=${encodeURIComponent(search)}&kind=${kind}`,
      ),
  });
  return (
    <section className="surface consumer-card">
      <div className="section-heading">
        <h2>Documents</h2>
        <button
          className="secondary"
          onClick={() => {
            setUpload(true);
            setError("");
          }}
        >
          Import bill / invoice PDF
        </button>
      </div>
      <div className="toolbar">
        <input
          aria-label="Search documents"
          maxLength={120}
          placeholder="Merchant, reference or date"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          aria-label="Document type"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          {["ALL", "PAYMENT", "BATCH", "UPLOAD", "REFUND"].map((k) => (
            <option key={k} value={k}>{readable(k)}</option>
          ))}
        </select>
      </div>
      <p>
        Payment records and merchant invoices are different. Uploaded bills are
        unverified documents, never proof that money moved.
      </p>
      {q.isError && (
        <p role="alert">
          Documents unavailable.{" "}
          <button onClick={() => void q.refetch()}>Retry</button>
        </p>
      )}
      {Array.isArray(q.data) &&
        q.data.map((d) => (
          <article className="record-row" key={`${d.kind}:${d.id}`}>
            <div>
              <strong>{d.title}</strong>
              <small>
                {readable(d.kind)} · {readable(d.status)} ·{" "}
                {new Date(d.created_at).toLocaleString()}
              </small>
            </div>
            <button className="secondary" onClick={() => setSelected(d)}>
              Preview record
            </button>
            <a className="document-link" href={d.download_url}>
              Download PDF
            </a>
          </article>
        ))}
      {Array.isArray(q.data) && !q.data.length && (
        <p>No matching documents. We do not invent missing invoices.</p>
      )}
      {selected && (
        <Dialog title="Document record" onClose={() => setSelected(undefined)}>
          <section className="document-preview">
            <h3>Wallet-Voice · {selected.title}</h3>
            <dl className="guardian-details">
              {Object.entries({
                Type: readable(selected.kind),
                Status: readable(selected.status),
                "What this record proves": readable(selected.trust),
                Reference: selected.reference,
                Recorded: new Date(selected.created_at).toLocaleString(),
                ...(selected.amount !== undefined
                  ? {
                      Amount: currencyMoney(selected.amount, selected.currency),
                    }
                  : {}),
              }).map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            <p>
              Pending/failed records and user uploads are not payment proof.
              Wallet-Voice receipts are not merchant tax invoices.
            </p>
            <div className="button-row">
              <a className="document-link" href={selected.download_url}>
                Download PDF
              </a>
              <button className="secondary" onClick={() => window.print()}>
                Print record summary
              </button>
              {"share" in navigator && (
                <button
                  className="secondary"
                  onClick={() =>
                    void navigator
                      .share({
                        title: "Wallet-Voice record",
                        text: `${selected.title} · ${selected.status} · Reference ${selected.reference}`,
                      })
                      .catch(() => {})
                  }
                >
                  Share summary
                </button>
              )}
            </div>
          </section>
        </Dialog>
      )}
      {upload && (
        <Dialog
          title="Import an unverified PDF"
          busy={busy}
          onClose={() => setUpload(false)}
        >
          <form
            className="form-stack"
            onSubmit={async (e) => {
              e.preventDefault();
              if (busy || !file) return;
              setBusy(true);
              setError("");
              try {
                const data = new FormData();
                data.append("title", title);
                data.append("file", file);
                const r = await fetch("/api/product/uploads", {
                  method: "POST",
                  body: data,
                });
                const payload = await r.json();
                if (r.status === 401)
                  window.dispatchEvent(new Event("wallet-session-expired"));
                if (!r.ok)
                  throw Error(
                    typeof payload.detail === "string"
                      ? payload.detail
                      : "Upload failed",
                  );
                setUpload(false);
                setTitle("");
                setFile(undefined);
                await q.refetch();
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label className="field">
              Document title
              <input
                required
                maxLength={120}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            <label className="field">
              PDF file (maximum 2 MiB)
              <input
                required
                type="file"
                accept="application/pdf,.pdf"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  setFile(undefined);
                  if (
                    f &&
                    (f.size > 2 * 1024 * 1024 || f.type !== "application/pdf")
                  )
                    setError("Choose a PDF no larger than 2 MiB");
                  else {
                    setFile(f);
                    setError("");
                  }
                }}
              />
            </label>
            <p>
              Files are stored privately in the demo database and downloaded as
              unverified attachments. We do not execute or scan them for
              malware. Upload only documents you trust.
            </p>
            {error && (
              <p role="alert" className="error-banner">
                {error}
              </p>
            )}
            <button disabled={busy || !file || !title.trim()}>
              {busy ? "Uploading…" : "Save unverified document"}
            </button>
          </form>
        </Dialog>
      )}
    </section>
  );
}
