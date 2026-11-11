import { Volume2, VolumeX } from "lucide-react";
import { money } from "../lib/formatting";
import type { WalletAssistant } from "../hooks/useWalletAssistant";

export function AssistantResponseCard({
  assistant: a,
}: {
  assistant: WalletAssistant;
}) {
  if (
    (!a.reply && !a.error) ||
    (!a.error && (a.busy || a.state === "RECORDING"))
  )
    return null;
  const balance =
    a.resultData && typeof a.resultData.available_balance === "number"
      ? a.resultData
      : null;
  return (
    <div className={`assistant-response ${a.error ? "has-error" : ""}`}>
      <p role={a.error ? "alert" : undefined}>
        {a.error || (balance ? "Here’s your wallet balance." : a.reply)}
      </p>
      {!a.error && balance && (
        <div className="answer-balance">
          <span>Available · simulated wallet</span>
          <strong>{money(balance.available_balance)}</strong>
          <small>{money(balance.reserved_amount)} set aside</small>
        </div>
      )}
      {!a.error&&Array.isArray(a.resultData?.documents)&&<section aria-label="Matching documents">{a.resultData.documents.map((d:{id:string;title:string;status:string;download_url:string})=><p key={d.id}>{d.title} · {d.status} {d.download_url.startsWith('/api/product/')&&<a className="document-link" href={d.download_url}>Download record PDF</a>}</p>)}</section>}
      {a.error && a.canRetry && (
        <button
          className="text-button"
          disabled={a.busy}
          onClick={() => void a.retry()}
        >
          Retry this request
        </button>
      )}
      {a.error && !a.canRetry && (
        <small>You can type your request below.</small>
      )}
      {a.reply && !a.error && (
        <button
          className="text-button"
          disabled={a.state === "RECORDING" || a.busy}
          onClick={() =>
            a.state === "SPEAKING" ? a.stopVoice() : void a.speak(a.reply)
          }
        >
          {a.state === "SPEAKING" ? (
            <>
              <VolumeX size={15} />
              Stop audio
            </>
          ) : (
            <>
              <Volume2 size={15} />
              Read aloud
            </>
          )}
        </button>
      )}
    </div>
  );
}
