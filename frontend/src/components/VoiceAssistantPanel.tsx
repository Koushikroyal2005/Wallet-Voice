import { useEffect, useRef } from "react";
import { stateCopy, type WalletAssistant } from "../hooks/useWalletAssistant";
import { AssistantOrb } from "./AssistantOrb";
import { AssistantComposer } from "./AssistantComposer";
import { AssistantResponseCard } from "./AssistantResponseCard";
import { AssistantActionCard } from "./AssistantActionCard";
import { AssistantPreferences } from "./AssistantPreferences";
import { ConversationPayments } from "./ConversationPayments";

/** Two views of one persistent assistant controller. */
export function VoiceAssistantPanel({
  assistant: a,
  mode,
  onChanged,
}: {
  assistant: WalletAssistant;
  mode: "chat" | "voice";
  onChanged: () => void;
}) {
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (mode === "chat") bottom.current?.scrollIntoView({ block: "nearest" });
  }, [a.messages.length, mode]);
  const status = a.busy
    ? "Understanding…"
    : a.state === "RECORDING"
      ? "Listening…"
      : stateCopy[a.state];
  return (
    <section
      className={`voice-panel presentation-${mode} state-${a.state.toLowerCase()}`}
      aria-label="Voice assistant"
    >
      <div className="assistant-scroll">
        {mode === "voice" && (
          <div className="voice-hud">
            <AssistantOrb
              state={a.state}
              level={a.level}
              large
              label={
                a.state === "RECORDING"
                  ? "Stop listening"
                  : a.state === "SPEAKING"
                    ? "Interrupt response"
                    : "Speak to Wallet-Voice"
              }
              onClick={() =>
                a.state === "RECORDING" ? a.stop() : void a.start()
              }
            />
            <div
              className="assistant-progress"
              role="status"
              aria-live="polite"
            >
              {status}
            </div>
            {a.state === "RECORDING" && (
              <small>Pause when you’re finished · {a.seconds}s</small>
            )}
          </div>
        )}
        {mode === "chat" && a.messages.length > 0 && (
          <div
            className="conversation-timeline"
            aria-label="Conversation history"
          >
            {a.messages.map((m, i) => (
              <div
                key={`${m.role}-${i}`}
                className={`conversation-message ${m.role}`}
              >
                <span>{m.role === "user" ? "You" : "Wallet-Voice"}</span>
                <p>{m.content}</p>
              </div>
            ))}
            <div ref={bottom} />
          </div>
        )}
        {mode === "chat" && (
          <p className="assistant-progress" role="status" aria-live="polite">
            {status}
          </p>
        )}
        {!a.messages.length &&
          !a.preview &&
          !a.busy &&
          a.state !== "RECORDING" && (
            <div className="assistant-welcome">
              <h3>A little help with your money.</h3>
              <p>Ask what’s due, review a payment, or check your balance.</p>
              <div className="conversation-suggestions">
                <button
                  className="secondary"
                  onClick={() => void a.ask("What payments need my attention?")}
                >
                  What needs attention?
                </button>
                <button
                  className="secondary"
                  onClick={() => void a.ask("What's my balance?")}
                >
                  My balance
                </button>
              </div>
            </div>
          )}
        {a.heard && a.state !== "RECORDING" && !a.busy && (
          <details
            className="heard-review"
            open={a.state === "TRANSCRIPT_READY"}
          >
            <summary>What I heard</summary>
            <div className="heard-transcript">
              <p>
                <strong>I heard:</strong> {a.heard}
              </p>
              <button
                className="text-button"
                onClick={() => {
                  a.stopVoice();
                  a.setPreview(undefined);
                  a.setText(a.heard);
                  a.setState("TRANSCRIPT_READY");
                  document.getElementById("wallet-command")?.focus();
                }}
              >
                Edit transcript
              </button>
            </div>
          </details>
        )}
        {a.state === "TRANSCRIPT_READY" && (
          <p className="transcript-hint">
            Check your words, then send when you’re ready.
          </p>
        )}
        {(mode === "voice" || a.error) && (
          <AssistantResponseCard assistant={a} />
        )}
        {mode === "chat" && a.reply && (
          <div className="chat-playback">
            <button
              className="text-button"
              disabled={a.busy || a.state === "RECORDING"}
              onClick={() =>
                a.state === "SPEAKING" ? a.stopVoice() : void a.speak(a.reply)
              }
            >
              {a.state === "SPEAKING" ? "Stop audio" : "Read aloud"}
            </button>
          </div>
        )}
        {a.dataRows.length > 0 &&
          !a.preview?.batch_id &&
          !a.error &&
          !a.busy &&
          a.state !== "RECORDING" && (
            <ConversationPayments
              items={a.dataRows}
              onReview={(id) => {
                a.stopVoice();
                a.setPreview({
                  kind: "payment",
                  payment_id: id,
                  payment_source: "AI_WALLET",
                  requires_confirmation: true,
                });
                a.setState("ACTION_PREVIEW");
              }}
            />
          )}
        <AssistantActionCard assistant={a} onChanged={onChanged} />
        <AssistantPreferences assistant={a} />
      </div>
      <AssistantComposer assistant={a} />
      <small className="assistant-footnote">
        You approve every payment securely.
      </small>
    </section>
  );
}
